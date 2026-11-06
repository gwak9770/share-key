/* 공유 차 키 - 차량 측 판단 모듈 (STM32 / PC 공용).
 * 판단 규칙은 core.py 와 동일. 플랫폼 의존 부분은 아래 sk_port_* 함수로 분리.
 *
 * 사용법 (STM32 main 루프):
 *   sk_init('C');
 *   while (1) {
 *     UART 로 한 줄이 완성되면  sk_handle_line(line);
 *     sk_poll();                          // 동기화 주기 처리
 *   }
 */
#ifndef SHAREKEY_H
#define SHAREKEY_H
#include <stdint.h>
#include <stddef.h>

#define SK_VID              0x0000CAFEu
#define SK_MAX_KEYS         8
#define SK_MAX_SYNC_ENTRIES 16
#define SK_NONCE_LIFE_MS    5000u
#define SK_LINE_MAX         512

/* ---- 플랫폼이 구현해야 하는 함수 (port_stm32.c / main_pc.c) ---- */
void     sk_port_send_line(const char *line);      /* 줄 끝 \n 은 포트가 붙임 */
void     sk_port_log(const char *msg);             /* 디버그 로그 (STM32: "#..." 줄로 송신) */
uint32_t sk_port_millis(void);                     /* 부팅 후 ms (HAL_GetTick) */
uint32_t sk_port_unix_time(void);                  /* RTC 유닉스 초 (B/D 방식에서만 사용) */
void     sk_port_random(uint8_t *out, size_t n);   /* 하드웨어 RNG */
void     sk_port_actuate(int cmd, int remaining);  /* 허용 시 실행: 1문열기 2시동 3반납, remaining -1=제한없음 */
void     sk_port_deny(int cmd, const char *reason);/* 거부 표시 (LED/LCD) */

/* ---- 모듈 API ---- */
void sk_init(char mode);                 /* 'A' 서버 취소만, 'B' +기간, 'C' +오프라인 횟수, 'D' +기간·횟수 */
void sk_set_sync_period(uint32_t ms);    /* 기본 2000ms */
void sk_handle_line(char *line);         /* "RID|종류|..." 한 줄 (\r\n 제거된 상태). line 은 수정됨 */
void sk_poll(void);                      /* 주기적으로 호출 (SYNCREQ 송신, 오프라인 판단) */

/* Read-only UI snapshot. No nonce, count, state or authorization mutation.
 * remaining is the raw policy counter (-1 for policies without a count).
 * blocked_reason reports permanent state only: 03 revoked / 09 returned / 00.
 * Returns 0 for an unknown KID or NULL output. Never use this to grant actions. */
typedef struct { int remaining; char blocked_reason[3]; } sk_key_view_t;
int sk_get_key_view(uint32_t kid, sk_key_view_t *view);

/* ---- 테스트용으로 공개 ---- */
void sk_derive(uint32_t kid, uint8_t ki[32]);
void sk_auth_tag(const uint8_t ki[32], uint32_t kid, uint8_t cmd, const uint8_t nonce[16], uint8_t tag[32]);
void sk_key_tag(uint32_t kid, uint32_t exp, uint8_t limit, uint8_t sit, uint8_t perm, uint8_t tag[32]);
void sk_sync_tag(uint32_t ver, const uint8_t nonce[16], const uint32_t *kids, const uint8_t *states,
                 int count, uint8_t tag[32]);
#endif
