/* 직접 구현한 SHA-256·HMAC을 표준 시험값(FIPS 180-4, RFC 4231 Case 1~7)과 비교하고,
 * 프로젝트 정답표(hmac_vectors.txt)를 자동 확인한다.
 * PC: python3 tools/run_host_tests.py (auth_vectors) 또는 cc -o test_vectors test_vectors.c sharekey.c sk_crypto.c sk_store.c
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
/* 앞부분만 비교 (RFC 4231 Case 5: 출력 128비트로 자름) */
static void check_prefix(const char *name, const uint8_t *got, const char *want) {
    char g[65]; hex(got, 32, g);
    int ok = strncmp(g, want, strlen(want)) == 0;
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) { printf("  want %s...\n  got  %s\n", want, g); fails++; }
}

int main(void) {
    uint8_t ki[32], t[32], n1[16], n0[16] = {0}, a5[16];
    const char *n1h = "00112233445566778899AABBCCDDEEFF";
    for (int i = 0; i < 16; i++) { sscanf(n1h + 2*i, "%2hhx", &n1[i]); a5[i] = 0xA5; }

    /* ---- 표준 문서 시험값: 직접 구현한 SHA-256·HMAC이 표준과 같은지 확인 ----
     * SHA-256: FIPS 180-4 예시(NIST CSRC "Examples with Intermediate Values"의 SHA256.pdf)와
     *          빈 문자열 값. 448비트 메시지는 패딩이 두 블록으로 넘어가는 경우다.
     * HMAC-SHA256: RFC 4231 §4.2~4.8 Test Case 1~7. Case 5는 앞 128비트만 비교(RFC 그대로).
     *              Case 6·7은 키가 블록(64바이트)보다 길어 키를 먼저 해시하는 경로다. */
    sk_sha256((const uint8_t *)"", 0, t);
    check("FIPS180 SHA256 empty", t, "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855");
    sk_sha256((const uint8_t *)"abc", 3, t);
    check("FIPS180 SHA256 abc", t, "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD");
    { const char *m = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
      sk_sha256((const uint8_t *)m, strlen(m), t);
      check("FIPS180 SHA256 448bit 2block", t, "248D6A61D20638B8E5C026930C3E6039A33CE45964FF2167F6ECEDD419DB06C1"); }
#if !defined(STM32F429xx)   /* 1MB 버퍼라 PC에서만 */
    { static uint8_t mil[1000000]; memset(mil, 'a', sizeof mil);
      sk_sha256(mil, sizeof mil, t);
      check("FIPS180 SHA256 million a", t, "CDC76E5C9914FB9281A1C7E284D73E67F1809A48A497200E046D39CCC7112CD0"); }
#endif
    { uint8_t k[131], d[50];
      memset(k, 0x0B, 20);
      sk_hmac_sha256(k, 20, (const uint8_t *)"Hi There", 8, t);
      check("RFC4231 case 1", t, "B0344C61D8DB38535CA8AFCEAF0BF12B881DC200C9833DA726E9376C2E32CFF7");
      sk_hmac_sha256((const uint8_t *)"Jefe", 4, (const uint8_t *)"what do ya want for nothing?", 28, t);
      check("RFC4231 case 2", t, "5BDCC146BF60754E6A042426089575C75A003F089D2739839DEC58B964EC3843");
      memset(k, 0xAA, 20); memset(d, 0xDD, 50);
      sk_hmac_sha256(k, 20, d, 50, t);
      check("RFC4231 case 3", t, "773EA91E36800E46854DB8EBD09181A72959098B3EF8C122D9635514CED565FE");
      for (int i = 0; i < 25; i++) k[i] = (uint8_t)(i + 1);
      memset(d, 0xCD, 50);
      sk_hmac_sha256(k, 25, d, 50, t);
      check("RFC4231 case 4", t, "82558A389A443C0EA4CC819899F2083A85F0FAA3E578F8077A2E3FF46729665B");
      memset(k, 0x0C, 20);
      sk_hmac_sha256(k, 20, (const uint8_t *)"Test With Truncation", 20, t);
      check_prefix("RFC4231 case 5 (128bit)", t, "A3B6167473100EE06E0C796C2955552B");
      memset(k, 0xAA, 131);
      { const char *m = "Test Using Larger Than Block-Size Key - Hash Key First";
        sk_hmac_sha256(k, 131, (const uint8_t *)m, strlen(m), t);
        check("RFC4231 case 6", t, "60E431591EE0B67F0D8A26AACBF5B77F8E0BC6213728C5140546040F0EE37F54"); }
      { const char *m = "This is a test using a larger than block-size key and a larger than block-size data."
                        " The key needs to be hashed before being used by the HMAC algorithm.";
        sk_hmac_sha256(k, 131, (const uint8_t *)m, strlen(m), t);
        check("RFC4231 case 7", t, "9B09FFA71B942FCB27635FBCD5B0E944BFDC63644F0713938A7F51535C3A35E2"); } }
    { /* 상수 시간 비교 함수: 같으면 1, 한 비트만 달라도(앞·끝) 0 */
      uint8_t a[32], b[32]; memset(a, 0x5A, 32); memcpy(b, a, 32);
      int ok = sk_ct_equal(a, b, 32) == 1;
      b[0] ^= 0x01; ok &= sk_ct_equal(a, b, 32) == 0; b[0] ^= 0x01;
      b[31] ^= 0x80; ok &= sk_ct_equal(a, b, 32) == 0;
      printf("%s ct_equal same/first-bit/last-bit\n", ok ? "PASS" : "FAIL"); fails += !ok; }

    /* ---- 프로젝트 정답표(hmac_vectors.txt, Python hmac로 생성): 메시지 형식이 서버와 같은지 확인 ---- */

    sk_derive(7, ki);  check("k_i KID 7", ki, "712CB1E57A7611E949342E32317CFA6D6A2083FA2126A0B4E62A9D5B2819A559");
    sk_derive(8, t);   check("k_i KID 8", t,  "DC6C92F4B4175412E3520D1C3447F0793FB89ED559939BF49F90FBC3AFF51D4E");
    sk_auth_tag(ki, 7, 1, n0, t); check("V1 open nonce0", t, "547FCC9F4A56C966D90707F166A33377DA85B65652A84B6F49D93FFF65847E6F");
    sk_auth_tag(ki, 7, 1, n1, t); check("V2 open",        t, "96646B5A5364C5A40850B48EEBE6979E315F731C8CF0B3C884DF5F66BC604D90");
    sk_auth_tag(ki, 7, 2, n1, t); check("V3 start",       t, "0D3B3F3698D89B65EFAA0B65623D717100F1B006E335C647F2CF7CAFA205B6B3");
    sk_auth_tag(ki, 7, 3, n1, t); check("V4 return",      t, "F169A789141AC534A35C7FC1412EFDAD90573B848E4E5A570B9D40B32EF4F1E5");
    sk_auth_tag(ki, 7, 4, n1, t); check("V7 reauth", t, "8923C2392AD82E1A1D3B4B07FC891643A1CA468C5404D0527ABAFD5017B4E00C");
    sk_auth_tag(ki, 7, 5, n1, t); check("V8 stop", t, "FC01C58FFB6E18D85D6CA903F1D8656D2D4C3EAE40A8E945B236F7A6323A1770");
    sk_derive(8, ki); sk_auth_tag(ki, 8, 1, n1, t); check("V5 KID 8", t, "B137A978C564A9C6DE4814813872AF1CD6283F5AD00C785A210156F28C412C6C");
    sk_derive(7, ki); sk_auth_tag(ki, 7, 1, a5, t); check("V6 nonce A5", t, "5E7E97B3C831E1A120608F2BE902BD7C8E6B22133576D27A8773CE5A4093C6CF");
    sk_key_tag(7, 1798761600u, 4, 2, 3, t); check("KEY", t, "8E46DEC63E4EE344A1D61AD1C576877DE789D07E3CBADB712AC983C3B9045012");
    { uint32_t kids[2] = {7, 8}; uint8_t st[2] = {1, 0};
      sk_sync_tag(2, a5, kids, st, 2, t); check("SYNC", t, "A2C45F0E7263E56D08ED50134C97BE2BF112DF20D6F5EE8EB93B146274F8EFF9"); }

    printf(fails ? "\n%d FAIL\n" : "\nALL PASS\n", fails);
    return fails != 0;
}
