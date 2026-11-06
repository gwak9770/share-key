#include "sharekey.h"
#include "sk_crypto.h"
#include <string.h>
#include <stdio.h>

/* 개발용 마스터키 00 01 ... 1F  (실제 사용 금지. 서버 common.py 의 K_V 와 같아야 함) */
static const uint8_t K_V[32] = {
    0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
    0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F};

enum { ST_VALID = 0, ST_REVOKED = 1, ST_RETURNED = 2 };

typedef struct {
    uint8_t  used;
    uint32_t kid, exp;
    uint8_t  limit, remaining, sit, perm, state;
    uint8_t  nonce[16];
    uint8_t  nonce_valid;
    uint32_t nonce_ms;
} sk_key_t;

static sk_key_t keys[SK_MAX_KEYS];
static int      use_exp, use_cnt;
static uint32_t ver;
static uint32_t sync_period = 2000, last_sync;
static uint8_t  sync_nonce[16];
static char     sync_rid[3];
static int      sync_pending;
static int      online = -1;              /* -1 모름, 0 오프라인, 1 온라인 */
static char     out[SK_LINE_MAX], msgbuf[96];

/* ---------- 작은 도구 ---------- */
static void put_u32(uint8_t *p, uint32_t v) { p[0]=v>>24; p[1]=v>>16; p[2]=v>>8; p[3]=(uint8_t)v; }

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
static int parse_hex(const char *s, uint8_t *o, size_t n) {   /* 정확히 2n 글자여야 함 */
    if (strlen(s) != 2 * n) return 0;
    for (size_t i = 0; i < n; i++) {
        int h = hexval(s[2*i]), l = hexval(s[2*i+1]);
        if (h < 0 || l < 0) return 0;
        o[i] = (uint8_t)(h << 4 | l);
    }
    return 1;
}
static int parse_u32(const char *s, uint32_t *v) {
    uint8_t b[4]; if (!parse_hex(s, b, 4)) return 0;
    *v = (uint32_t)b[0]<<24 | (uint32_t)b[1]<<16 | (uint32_t)b[2]<<8 | b[3]; return 1;
}
static int parse_u8(const char *s, uint8_t *v) { return parse_hex(s, v, 1); }
static void to_hex(const uint8_t *b, size_t n, char *o) {
    static const char d[] = "0123456789ABCDEF";
    for (size_t i = 0; i < n; i++) { o[2*i] = d[b[i] >> 4]; o[2*i+1] = d[b[i] & 15]; }
    o[2*n] = 0;
}
static int split(char *s, char **f, int max) {
    int n = 0; f[n++] = s;
    for (; *s && n < max; s++) if (*s == '|') { *s = 0; f[n++] = s + 1; }
    return n;
}
static sk_key_t *find(uint32_t kid) {
    for (int i = 0; i < SK_MAX_KEYS; i++) if (keys[i].used && keys[i].kid == kid) return &keys[i];
    return NULL;
}
int sk_get_key_view(uint32_t kid, sk_key_view_t *view) {
    const sk_key_t *k = find(kid);
    if (!k || !view) return 0;
    view->remaining = use_cnt ? (int)k->remaining : -1;
    memcpy(view->blocked_reason, k->state == ST_REVOKED ? "03" :
           k->state == ST_RETURNED ? "09" : "00", 3u);
    return 1;
}

static void logf_(const char *m) { sk_port_log(m); }

/* ---------- 인증값 계산 (Python common.py 와 동일) ---------- */
void sk_derive(uint32_t kid, uint8_t ki[32]) {            /* HMAC(K_v, "user" ‖ KID) */
    uint8_t m[8] = {'u','s','e','r'}; put_u32(m + 4, kid);
    sk_hmac_sha256(K_V, 32, m, 8, ki);
}
void sk_auth_tag(const uint8_t ki[32], uint32_t kid, uint8_t cmd, const uint8_t nonce[16], uint8_t tag[32]) {
    uint8_t m[25];                                        /* VID ‖ KID ‖ CMD ‖ NONCE */
    put_u32(m, SK_VID); put_u32(m + 4, kid); m[8] = cmd; memcpy(m + 9, nonce, 16);
    sk_hmac_sha256(ki, 32, m, 25, tag);
}
void sk_key_tag(uint32_t kid, uint32_t exp, uint8_t limit, uint8_t sit, uint8_t perm, uint8_t tag[32]) {
    uint8_t m[18] = {'K','E','Y'};                        /* "KEY" ‖ VID ‖ KID ‖ EXP ‖ LIMIT ‖ SIT ‖ PERM */
    put_u32(m + 3, SK_VID); put_u32(m + 7, kid); put_u32(m + 11, exp);
    m[15] = limit; m[16] = sit; m[17] = perm;
    sk_hmac_sha256(K_V, 32, m, 18, tag);
}
void sk_sync_tag(uint32_t v, const uint8_t nonce[16], const uint32_t *kids, const uint8_t *states,
                 int count, uint8_t tag[32]) {
    uint8_t m[4 + 4 + 4 + 16 + 1 + 5 * SK_MAX_SYNC_ENTRIES] = {'S','Y','N','C'};
    size_t n = 4;
    put_u32(m + n, SK_VID); n += 4; put_u32(m + n, v); n += 4;
    memcpy(m + n, nonce, 16); n += 16; m[n++] = (uint8_t)count;
    for (int i = 0; i < count; i++) { put_u32(m + n, kids[i]); n += 4; m[n++] = states[i]; }
    sk_hmac_sha256(K_V, 32, m, n, tag);
}

/* ---------- 판단: 등록 → 인증값 → nonce → 취소/반납 → 기간 → (반납) → 권한 → 횟수 → 실행 ---------- */
static const char *decide(sk_key_t *k, uint32_t kid, uint8_t cmd, const uint8_t nonce[16], const uint8_t tag[32]) {
    uint8_t ki[32], expect[32];
    int pend_ok = 0;
    if (!k) return "08";
    /* nonce 는 성공/실패 관계없이 1회용: 먼저 꺼내 놓고 무효화 */
    if (k->nonce_valid && memcmp(k->nonce, nonce, 16) == 0 &&
        (uint32_t)(sk_port_millis() - k->nonce_ms) <= SK_NONCE_LIFE_MS) pend_ok = 1;
    k->nonce_valid = 0;

    sk_derive(kid, ki);
    sk_auth_tag(ki, kid, cmd, nonce, expect);
    if (!sk_ct_equal(expect, tag, 32)) return "01";
    if (!pend_ok)                       return "02";
    if (k->state == ST_REVOKED)         return "03";
    if (k->state == ST_RETURNED)        return "09";
    if (use_exp && sk_port_unix_time() > k->exp) return "04";
    if (cmd == 3) {                     /* 반납: 차량 내부 즉시 무효화, 횟수 차감 없음 */
        k->state = ST_RETURNED;
        /* TODO(11/16): FRAM 에 상태 저장 */
        return "00";
    }
    if (!((cmd == 1 && (k->perm & 0x01)) || (cmd == 2 && (k->perm & 0x02)))) return "06";
    if (use_cnt) {
        if (k->remaining == 0) return "05";
        k->remaining--;                 /* 차감 → (11/16: FRAM 저장) → 실행 순서 유지 */
    }
    return "00";
}

static void on_resp(char **f, int nf) {     /* RID|RESP|KID|CMD|NONCE|TAG */
    uint32_t kid; uint8_t cmd, nonce[16], tag[32];
    if (nf != 6 || !parse_u32(f[2], &kid) || !parse_u8(f[3], &cmd) ||
        !parse_hex(f[4], nonce, 16) || !parse_hex(f[5], tag, 32)) {
        snprintf(out, sizeof out, "%s|ERR|FF", f[0]); sk_port_send_line(out); return;
    }
    sk_key_t *k = find(kid);
    const char *why = decide(k, kid, cmd, nonce, tag);
    char rem[3] = "FF";
    if (k && use_cnt) snprintf(rem, sizeof rem, "%02X", k->remaining);
    int ok = (why[0] == '0' && why[1] == '0');
    if (ok) sk_port_actuate(cmd, (k && use_cnt && cmd != 3) ? k->remaining : -1);
    else {
        snprintf(msgbuf, sizeof msgbuf, "DENY kid=%08lX cmd=%u reason=%s", (unsigned long)kid, cmd, why);
        logf_(msgbuf); sk_port_deny(cmd, why);
    }
    snprintf(out, sizeof out, "%s|RES|%08lX|%c|%s|%s", f[0], (unsigned long)kid, ok ? 'A' : 'D', why, rem);
    sk_port_send_line(out);
}

static void on_req(char **f, int nf) {      /* RID|REQ|KID|CMD */
    uint32_t kid; uint8_t cmd; char nh[33];
    if (nf != 4 || !parse_u32(f[2], &kid) || !parse_u8(f[3], &cmd)) {
        snprintf(out, sizeof out, "%s|ERR|FF", f[0]); sk_port_send_line(out); return;
    }
    sk_key_t *k = find(kid);
    if (!k) { snprintf(out, sizeof out, "%s|RES|%08lX|D|08|00", f[0], (unsigned long)kid); sk_port_send_line(out); return; }
    sk_port_random(k->nonce, 16);
    k->nonce_valid = 1; k->nonce_ms = sk_port_millis();
    to_hex(k->nonce, 16, nh);
    snprintf(out, sizeof out, "%s|CHAL|%08lX|%s", f[0], (unsigned long)kid, nh);
    sk_port_send_line(out);
}

static void on_key(char **f, int nf) {      /* RID|KEY|KID|EXP|LIMIT|SIT|PERM|TAG */
    uint32_t kid, exp; uint8_t limit, sit, perm, tag[32], expect[32];
    if (nf != 8 || !parse_u32(f[2], &kid) || !parse_u32(f[3], &exp) || !parse_u8(f[4], &limit) ||
        !parse_u8(f[5], &sit) || !parse_u8(f[6], &perm) || !parse_hex(f[7], tag, 32)) {
        snprintf(out, sizeof out, "%s|ERR|FF", f[0]); sk_port_send_line(out); return;
    }
    sk_key_tag(kid, exp, limit, sit, perm, expect);
    if (!sk_ct_equal(expect, tag, 32)) {
        logf_("KEY rejected (bad tag)");
        snprintf(out, sizeof out, "%s|KEYNG|%08lX|01", f[0], (unsigned long)kid); sk_port_send_line(out); return;
    }
    sk_key_t *k = find(kid);
    if (!k) {                               /* 같은 KID 재등록은 기존 기록 유지 */
        for (int i = 0; i < SK_MAX_KEYS; i++) if (!keys[i].used) { k = &keys[i]; break; }
        if (!k) { snprintf(out, sizeof out, "%s|KEYNG|%08lX|FF", f[0], (unsigned long)kid); sk_port_send_line(out); return; }
        memset(k, 0, sizeof *k);
        k->used = 1; k->kid = kid; k->exp = exp; k->limit = limit; k->remaining = limit;
        k->sit = sit; k->perm = perm; k->state = ST_VALID;
    }
    snprintf(msgbuf, sizeof msgbuf, "KEY ok kid=%08lX limit=%u", (unsigned long)kid, limit); logf_(msgbuf);
    snprintf(out, sizeof out, "%s|KEYOK|%08lX", f[0], (unsigned long)kid); sk_port_send_line(out);
}

static void on_sync(char **f, int nf) {     /* RID|SYNC|VID|VER|NONCE|COUNT|entries|TAG */
    uint32_t vid, nv, kids[SK_MAX_SYNC_ENTRIES]; uint8_t sts[SK_MAX_SYNC_ENTRIES];
    uint8_t rn[16], tag[32], expect[32], cnt;
    int n = 0, ok = 0;
    if (!sync_pending || strcmp(f[0], sync_rid) != 0) return;   /* 내가 보낸 요청의 응답만 */
    sync_pending = 0;
    if (nf == 8 && parse_u32(f[2], &vid) && parse_u32(f[3], &nv) && parse_hex(f[4], rn, 16) &&
        parse_u8(f[5], &cnt) && parse_hex(f[7], tag, 32) && cnt <= SK_MAX_SYNC_ENTRIES) {
        ok = 1;
        if (strcmp(f[6], "-") != 0) {       /* KKKKKKKK:SS,KKKKKKKK:SS,... */
            char *p = f[6];
            while (*p && n < SK_MAX_SYNC_ENTRIES) {
                char kb[9], sb[3];
                if (strlen(p) < 11 || p[8] != ':') { ok = 0; break; }
                memcpy(kb, p, 8); kb[8] = 0; memcpy(sb, p + 9, 2); sb[2] = 0;
                if (!parse_u32(kb, &kids[n]) || !parse_u8(sb, &sts[n])) { ok = 0; break; }
                n++; p += 11;
                if (*p == ',') p++; else if (*p) { ok = 0; break; }
            }
        }
        if (ok && n != cnt) ok = 0;
        if (ok) {
            sk_sync_tag(nv, rn, kids, sts, n, expect);
            ok = memcmp(rn, sync_nonce, 16) == 0 && nv >= ver && sk_ct_equal(expect, tag, 32);
        }
    }
    if (!ok) { logf_("SYNC rejected (nonce/ver/tag)"); return; }
    for (int i = 0; i < n; i++) {
        sk_key_t *k = find(kids[i]);
        if (!k) continue;
        if (sts[i] == ST_REVOKED) k->state = ST_REVOKED;
        else if (k->state == ST_VALID) k->remaining = k->limit;   /* 인증된 동기화만 횟수 복구 */
    }
    if (nv > ver) { snprintf(msgbuf, sizeof msgbuf, "SYNC applied ver %lu -> %lu", (unsigned long)ver, (unsigned long)nv); logf_(msgbuf); }
    ver = nv;
    if (online != 1) { online = 1; logf_("server sync ok -> ONLINE"); }
    snprintf(out, sizeof out, "%s|SYNCACK|%08lX|%08lX", f[0], (unsigned long)SK_VID, (unsigned long)ver);
    sk_port_send_line(out);
}

/* ---------- 공개 함수 ---------- */
void sk_init(char mode) {
    memset(keys, 0, sizeof keys);
    use_exp = (mode == 'B' || mode == 'D');
    use_cnt = (mode == 'C' || mode == 'D');
    ver = 0; sync_pending = 0; online = -1;
    last_sync = sk_port_millis() - sync_period;     /* 시작 직후 바로 동기화 */
}

void sk_set_sync_period(uint32_t ms) { sync_period = ms; }

void sk_handle_line(char *line) {
    char *f[10];
    if (!line[0] || line[0] == '#') return;
    int nf = split(line, f, 10);
    if (nf < 2 || strlen(f[0]) != 2) return;
    if      (!strcmp(f[1], "RESP")) on_resp(f, nf);
    else if (!strcmp(f[1], "REQ"))  on_req(f, nf);
    else if (!strcmp(f[1], "KEY"))  on_key(f, nf);
    else if (!strcmp(f[1], "SYNC")) on_sync(f, nf);
    else if (!strcmp(f[1], "OK"))   ;                       /* SYNCACK 응답, 무시 */
    else if (!strcmp(f[1], "HB"))   ;                       /* Pi 생존 신호: 응답 없음 (제어 계층이 시각만 갱신) */
    else { snprintf(out, sizeof out, "%s|ERR|FF", f[0]); sk_port_send_line(out); }
}

void sk_poll(void) {
    uint32_t now = sk_port_millis();
    uint8_t r; char nh[33];
    if ((uint32_t)(now - last_sync) < sync_period) return;
    last_sync = now;
    if (sync_pending && online != 0) { online = 0; logf_("no server response -> OFFLINE"); }
    sk_port_random(&r, 1);
    snprintf(sync_rid, sizeof sync_rid, "%02X", r);
    sk_port_random(sync_nonce, 16);
    sync_pending = 1;
    to_hex(sync_nonce, 16, nh);
    snprintf(out, sizeof out, "%s|SYNCREQ|%08lX|%s|%08lX", sync_rid, (unsigned long)SK_VID, nh, (unsigned long)ver);
    sk_port_send_line(out);
}
