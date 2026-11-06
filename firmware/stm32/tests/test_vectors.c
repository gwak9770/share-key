/* HMAC 정답표(hmac_vectors.txt) 자동 확인. PC: cc -o test_vectors test_vectors.c sharekey.c sk_crypto.c
 * STM32 에서도 이 main 내용을 그대로 옮겨 UART 로 PASS/FAIL 을 찍으면 10/26 점검 증거가 됨. */
#include <stdio.h>
#include <string.h>
#include "sharekey.h"
#include "sk_crypto.h"

/* 링크용 빈 포트 함수 */
void sk_port_send_line(const char *l) { (void)l; }
void sk_port_log(const char *m) { (void)m; }
uint32_t sk_port_millis(void) { return 0; }
uint32_t sk_port_unix_time(void) { return 0; }
void sk_port_random(uint8_t *o, size_t n) { memset(o, 0, n); }
void sk_port_actuate(int c, int r) { (void)c; (void)r; }
void sk_port_deny(int c, const char *r) { (void)c; (void)r; }

static void hex(const uint8_t *b, size_t n, char *o) { for (size_t i = 0; i < n; i++) sprintf(o + 2*i, "%02X", b[i]); }
static int fails = 0;
static void check(const char *name, const uint8_t *got, const char *want) {
    char g[65]; hex(got, 32, g);
    int ok = strcmp(g, want) == 0;
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) { printf("  want %s\n  got  %s\n", want, g); fails++; }
}

int main(void) {
    uint8_t ki[32], t[32], n1[16], n0[16] = {0}, a5[16];
    const char *n1h = "00112233445566778899AABBCCDDEEFF";
    for (int i = 0; i < 16; i++) { sscanf(n1h + 2*i, "%2hhx", &n1[i]); a5[i] = 0xA5; }

    /* RFC 4231 Test Case 2: SHA-256 구현 자체 확인 */
    sk_hmac_sha256((const uint8_t *)"Jefe", 4, (const uint8_t *)"what do ya want for nothing?", 28, t);
    check("RFC4231 case 2", t, "5BDCC146BF60754E6A042426089575C75A003F089D2739839DEC58B964EC3843");

    sk_derive(7, ki);  check("k_i KID 7", ki, "712CB1E57A7611E949342E32317CFA6D6A2083FA2126A0B4E62A9D5B2819A559");
    sk_derive(8, t);   check("k_i KID 8", t,  "DC6C92F4B4175412E3520D1C3447F0793FB89ED559939BF49F90FBC3AFF51D4E");
    sk_auth_tag(ki, 7, 1, n0, t); check("V1 open nonce0", t, "547FCC9F4A56C966D90707F166A33377DA85B65652A84B6F49D93FFF65847E6F");
    sk_auth_tag(ki, 7, 1, n1, t); check("V2 open",        t, "96646B5A5364C5A40850B48EEBE6979E315F731C8CF0B3C884DF5F66BC604D90");
    sk_auth_tag(ki, 7, 2, n1, t); check("V3 start",       t, "0D3B3F3698D89B65EFAA0B65623D717100F1B006E335C647F2CF7CAFA205B6B3");
    sk_auth_tag(ki, 7, 3, n1, t); check("V4 return",      t, "F169A789141AC534A35C7FC1412EFDAD90573B848E4E5A570B9D40B32EF4F1E5");
    sk_derive(8, ki); sk_auth_tag(ki, 8, 1, n1, t); check("V5 KID 8", t, "B137A978C564A9C6DE4814813872AF1CD6283F5AD00C785A210156F28C412C6C");
    sk_derive(7, ki); sk_auth_tag(ki, 7, 1, a5, t); check("V6 nonce A5", t, "5E7E97B3C831E1A120608F2BE902BD7C8E6B22133576D27A8773CE5A4093C6CF");
    sk_key_tag(7, 1798761600u, 4, 2, 3, t); check("KEY", t, "8E46DEC63E4EE344A1D61AD1C576877DE789D07E3CBADB712AC983C3B9045012");
    { uint32_t kids[2] = {7, 8}; uint8_t st[2] = {1, 0};
      sk_sync_tag(2, a5, kids, st, 2, t); check("SYNC", t, "A2C45F0E7263E56D08ED50134C97BE2BF112DF20D6F5EE8EB93B146274F8EFF9"); }

    printf(fails ? "\n%d FAIL\n" : "\nALL PASS\n", fails);
    return fails != 0;
}
