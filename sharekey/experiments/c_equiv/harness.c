/* C 동등성 확인용 PC 하네스 (docs/02_final_roadmap.md §5.5, 00 §10 D6).
 * firmware/stm32/Core 의 sharekey.c 판단 코드를 그대로 링크하고, 포트 함수만 PC용으로 둔다.
 * 판단 코드는 바꾸지 않는다. c_equiv.py 가 빌드·실행한다.
 *
 * 표준 입력 한 줄마다:
 *   T <millis> <unix>   가짜 시계 설정 (sk_port_millis / sk_port_unix_time)
 *   INIT <A|B|C|D>      sk_init
 *   POLL                sk_poll (동기화 주기가 지났으면 SYNCREQ 줄 송신)
 *   그 밖의 줄          sk_handle_line 에 그대로 전달 ("RID|KEY|..." 등)
 * 처리 뒤 송신한 줄들을 출력하고, 끝에 "." 한 줄을 출력한다. 로그는 표준 오류. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sharekey.h"

static uint32_t now_ms, now_unix, rng = 0x12345678u;

void sk_port_send_line(const char *line) { printf("%s\n", line); }
void sk_port_log(const char *msg) { fprintf(stderr, "# %s\n", msg); }
uint32_t sk_port_millis(void) { return now_ms; }
uint32_t sk_port_unix_time(void) { return now_unix; }
void sk_port_random(uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++) { rng = rng * 1103515245u + 12345u; out[i] = (uint8_t)(rng >> 16); }
}
void sk_port_actuate(int cmd, int remaining) { (void)cmd; (void)remaining; }
void sk_port_deny(int cmd, const char *reason) { (void)cmd; (void)reason; }

int main(void) {
    char line[SK_LINE_MAX + 2];
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        if (!strncmp(line, "T ", 2)) {
            unsigned long ms, ux;
            if (sscanf(line + 2, "%lu %lu", &ms, &ux) == 2) { now_ms = (uint32_t)ms; now_unix = (uint32_t)ux; }
        } else if (!strncmp(line, "INIT ", 5)) {
            sk_init(line[5]);
            sk_set_sync_period(1);
        } else if (!strcmp(line, "POLL")) {
            sk_poll();
        } else if (line[0]) {
            sk_handle_line(line);
        }
        printf(".\n");
        fflush(stdout);
    }
    return 0;
}
