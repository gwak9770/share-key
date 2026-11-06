/* SHA-256 / HMAC-SHA256 (FIPS 180-4, RFC 2104). 외부 라이브러리 없이 동작.
 * mbedTLS 등 라이브러리로 바꿔도 되며, 그 경우 이 두 함수만 감싸면 됨. */
#ifndef SK_CRYPTO_H
#define SK_CRYPTO_H
#include <stdint.h>
#include <stddef.h>

void sk_sha256(const uint8_t *msg, size_t len, uint8_t out[32]);
void sk_hmac_sha256(const uint8_t *key, size_t klen,
                    const uint8_t *msg, size_t mlen, uint8_t out[32]);
int  sk_ct_equal(const uint8_t *a, const uint8_t *b, size_t n);  /* 상수 시간 비교, 같으면 1 */
#endif
