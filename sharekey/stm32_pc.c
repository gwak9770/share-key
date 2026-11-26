/* STM32 판단 코드의 PC 실행판 (demo.py --relay-c 용, macOS·Linux·Pi).
 * firmware/stm32/Core 의 sharekey.c·sk_crypto.c·sk_store.c 를 그대로 링크하고
 * 포트 함수(시간·난수·송신)만 PC용으로 둔다. 판단 코드 사본을 두지 않는다.
 * stm32_sim.py 와 같은 역할: TCP 로 Pi 중계(pi_relay.py --sim)를 받아 한 줄씩 처리.
 * 빌드: python3 stm32_pc_build.py  →  build/stm32_pc
 * 실행: build/stm32_pc <A|B|C|D> [port=9200] [sync_ms=2000] */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "sharekey.h"

static int client = -1;

void sk_port_send_line(const char *line) {
    if (client < 0) return;
    char buf[SK_LINE_MAX + 2];
    int n = snprintf(buf, sizeof buf, "%s\n", line);
    if (n > 0 && write(client, buf, (size_t)n) < 0) { /* 연결 끊김은 main 루프가 처리 */ }
}
void sk_port_log(const char *msg) { fprintf(stderr, "[STM32-C] %s\n", msg); }
uint32_t sk_port_millis(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)((uint64_t)ts.tv_sec * 1000u + (uint64_t)ts.tv_nsec / 1000000u);
}
uint32_t sk_port_unix_time(void) { return (uint32_t)time(NULL); }
void sk_port_random(uint8_t *out, size_t n) {
    FILE *f = fopen("/dev/urandom", "rb");
    if (!f || fread(out, 1, n, f) != n) { fprintf(stderr, "난수 실패\n"); exit(1); }
    fclose(f);
}
void sk_port_actuate(int cmd, int remaining) { fprintf(stderr, "[STM32-C] 실행 cmd=%d left=%d\n", cmd, remaining); }
void sk_port_deny(int cmd, const char *reason) { fprintf(stderr, "[STM32-C] 거부 cmd=%d why=%s\n", cmd, reason); }

int main(int argc, char **argv) {
    char mode = argc > 1 ? argv[1][0] : 'C';
    int port = argc > 2 ? atoi(argv[2]) : 9200;
    unsigned sync_ms = argc > 3 ? (unsigned)atoi(argv[3]) : 2000u;
    sk_init(mode);
    sk_set_sync_period(sync_ms);

    int srv = socket(AF_INET, SOCK_STREAM, 0), one = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in a; memset(&a, 0, sizeof a);
    a.sin_family = AF_INET; a.sin_port = htons((unsigned short)port); a.sin_addr.s_addr = inet_addr("127.0.0.1");
    if (bind(srv, (struct sockaddr *)&a, sizeof a) < 0 || listen(srv, 1) < 0) { perror("bind"); return 1; }
    fprintf(stderr, "[STM32-C] 시작 mode=%c port=%d sync=%ums, Pi 연결 대기\n", mode, port, sync_ms);

    char line[SK_LINE_MAX + 2]; size_t len = 0;
    for (;;) {
        if (client < 0) {
            client = accept(srv, NULL, NULL);
            if (client < 0) continue;
            len = 0;
            fprintf(stderr, "[STM32-C] Pi 연결됨\n");
        }
        fd_set rd; FD_ZERO(&rd); FD_SET(client, &rd);
        struct timeval tv = {0, 10000};                 /* 10ms 마다 sk_poll */
        int r = select(client + 1, &rd, NULL, NULL, &tv);
        if (r > 0) {
            char c;
            ssize_t got = read(client, &c, 1);
            if (got <= 0) { close(client); client = -1; fprintf(stderr, "[STM32-C] Pi 연결 끊김\n"); continue; }
            if (c == '\n') {
                line[len] = 0;
                if (len && line[len - 1] == '\r') line[len - 1] = 0;
                sk_handle_line(line);
                len = 0;
            } else if (len < SK_LINE_MAX) {
                line[len++] = c;
            }
        }
        sk_poll();
    }
}
