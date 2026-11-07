/* F429 platform adapter. Use CubeIDE-generated USART3, RNG, clock and IRQ files.
 * This file owns the one set of UART callbacks; remove the previous port_stm32.c.
 * No main(), USART3_IRQHandler(), SysTick_Handler(), or UART/RNG handle definition.
 */
#include "stm32f4xx_hal.h"
#include "board.h"
#include "config.h"
#include "vehicle_platform.h"
#include "peripherals.h"
#include <string.h>

extern UART_HandleTypeDef huart3;
extern RNG_HandleTypeDef hrng;
static uint8_t rx_byte, rx_buffer[VC_UART_RX_SIZE], tx_buffer[VC_UART_TX_SIZE];
static volatile uint16_t rx_head, rx_tail, tx_head, tx_tail, tx_active;
static volatile bool rx_fault, rx_restart, tx_fault;
#if VC_ENABLE_IWDG
static IWDG_HandleTypeDef vc_iwdg;
#endif
#if VC_ENABLE_RTC || VC_ENABLE_OLED
static RtcTime rtc_time;
static uint32_t last_rtc, last_retry;
#endif

static uint32_t critical_enter(void) { uint32_t p = __get_PRIMASK(); __disable_irq(); return p; }
static void critical_leave(uint32_t p) { __set_PRIMASK(p); }

static void tx_kick(void) {
    uint32_t mask = critical_enter();
    if (!tx_active && tx_tail != tx_head) {
        uint16_t n = tx_head > tx_tail ? (uint16_t)(tx_head - tx_tail) : (uint16_t)(VC_UART_TX_SIZE - tx_tail);
        tx_active = n;
        if (HAL_UART_Transmit_IT(&huart3, tx_buffer + tx_tail, n) != HAL_OK) {
            tx_active = 0; tx_fault = true;
        }
    }
    critical_leave(mask);
}

static void send_line(const char *prefix, const char *line) {
    size_t a = strlen(prefix), n = strlen(line);
    /* Reserve all bytes first: a full ring must not emit a partial protocol line. */
    if (n > 512u || a + n + 1u >= VC_UART_TX_SIZE) { tx_fault = true; return; }
    for (size_t i = 0; i < n; ++i) {
        if (line[i] == '\r' || line[i] == '\n') { tx_fault = true; return; }
    }
    uint16_t head = tx_head;
    uint16_t tail = tx_tail;
    size_t free_space = (tail - head - 1u) & (VC_UART_TX_SIZE - 1u);
    if (free_space < a + n + 1u) { tx_fault = true; return; }
    for (size_t i = 0; i < a; ++i) { tx_buffer[head] = (uint8_t)prefix[i]; head = (uint16_t)((head + 1u) & (VC_UART_TX_SIZE - 1u)); }
    for (size_t i = 0; i < n; ++i) { tx_buffer[head] = (uint8_t)line[i]; head = (uint16_t)((head + 1u) & (VC_UART_TX_SIZE - 1u)); }
    tx_buffer[head] = '\n'; head = (uint16_t)((head + 1u) & (VC_UART_TX_SIZE - 1u));
    __DMB(); tx_head = head;
    tx_kick();
}

bool vc_platform_init(void) {
    rx_head = rx_tail = tx_head = tx_tail = tx_active = 0;
    rx_fault = rx_restart = tx_fault = false;
    if (huart3.Instance != USART3 || hrng.Instance != RNG ||
        huart3.Init.BaudRate != 115200u || huart3.Init.WordLength != UART_WORDLENGTH_8B ||
        huart3.Init.StopBits != UART_STOPBITS_1 || huart3.Init.Parity != UART_PARITY_NONE ||
        huart3.Init.Mode != UART_MODE_TX_RX) return false;
    if (!board_init()) return false;
    if (HAL_UART_Receive_IT(&huart3, &rx_byte, 1u) != HAL_OK) { board_kill(); return false; }
#if VC_ENABLE_IWDG
    vc_iwdg.Instance = IWDG;
    vc_iwdg.Init.Prescaler = IWDG_PRESCALER_64;
    vc_iwdg.Init.Reload = 999u; /* ~2 seconds at nominal 32kHz LSI, no F7 Window field. */
    if (HAL_IWDG_Init(&vc_iwdg) != HAL_OK) { board_kill(); return false; }
#endif
#if VC_ENABLE_RTC || VC_ENABLE_OLED
    memset(&rtc_time, 0, sizeof(rtc_time));
    last_rtc = HAL_GetTick() - 1000u; last_retry = HAL_GetTick();
#endif
#if VC_ENABLE_OLED
    oled_init();
#endif
    return true;
}
uint32_t vc_platform_millis(void) { return HAL_GetTick(); }
Inputs vc_platform_inputs(void) { return board_inputs(); }
void vc_platform_apply(Outputs out) { board_apply(out); }
void vc_platform_indicators(bool a, bool o, bool d) { board_leds(a, o, d); }
bool vc_platform_return_pressed(void) { return board_return_pressed(); }
bool vc_platform_mode_button(void) { return board_mode_button(); }

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *h) {
    if (h != &huart3) return;
    uint16_t next = (uint16_t)((rx_head + 1u) & (VC_UART_RX_SIZE - 1u));
    if (next == rx_tail) rx_fault = true;
    else { rx_buffer[rx_head] = rx_byte; __DMB(); rx_head = next; }
    if (HAL_UART_Receive_IT(h, &rx_byte, 1u) != HAL_OK) { rx_fault = true; rx_restart = true; }
}
void HAL_UART_ErrorCallback(UART_HandleTypeDef *h) {
    if (h == &huart3) { rx_fault = true; rx_restart = true; }
}
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h) {
    if (h != &huart3) return;
    tx_tail = (uint16_t)((tx_tail + tx_active) & (VC_UART_TX_SIZE - 1u));
    tx_active = 0;
    /* Foreground starts the next chunk; shared callbacks never run policy code. */
}
int vc_platform_rx_get(void) {
    if (rx_head == rx_tail) return -1;
    int c = rx_buffer[rx_tail];
    rx_tail = (uint16_t)((rx_tail + 1u) & (VC_UART_RX_SIZE - 1u));
    return c;
}
bool vc_platform_take_io_fault(void) {
    uint32_t mask = critical_enter();
    bool bad = rx_fault || tx_fault;
    bool restart = rx_restart;
    if (rx_fault) rx_tail = rx_head;
    rx_fault = rx_restart = tx_fault = false;
    critical_leave(mask);
    if (restart) {
        if (HAL_UART_AbortReceive(&huart3) != HAL_OK ||
            HAL_UART_Receive_IT(&huart3, &rx_byte, 1u) != HAL_OK) rx_restart = true;
    }
    return bad || restart || board_faulted();
}
void vc_platform_send_line(const char *line) { send_line("", line); }
void vc_platform_log(const char *line) { send_line("# ", line); }
void vc_platform_random(uint8_t *out, size_t n) {
    while (n) {
        uint32_t word;
        if (HAL_RNG_GenerateRandomNumber(&hrng, &word) != HAL_OK) vc_platform_panic();
        for (unsigned i = 0; i < 4u && n; ++i, --n) { *out++ = (uint8_t)word; word >>= 8; }
    }
}
void vc_platform_service(const Controller *c, const VehicleDisplay *display) {
    (void)c; (void)display;
    tx_kick();
#if VC_ENABLE_RTC || VC_ENABLE_OLED
    uint32_t now = HAL_GetTick();
#if VC_ENABLE_RTC
    if ((uint32_t)(now - last_rtc) >= 1000u) { last_rtc = now; (void)rtc_read(&rtc_time); }
#endif
#if VC_ENABLE_OLED
    oled_status(c, &rtc_time, display); /* 1106 (곽동규): changed frames start without a 500ms gate. */
    if (!oled_online() && (uint32_t)(now - last_retry) >= 5000u) {
        last_retry = now; (void)board_i2c_recover(); oled_init(); /* 1104: free a stuck bus first */
    }
    oled_service(); /* A bounded small I2C chunk, never a full-screen busy loop. */
#endif
#endif
#if VC_ENABLE_IWDG
    (void)HAL_IWDG_Refresh(&vc_iwdg);
#endif
}
void vc_platform_panic(void) {
    board_kill();
    board_leds(false, false, true);
    __disable_irq();
    for (;;) { __NOP(); } /* No weak/predictable fallback if RNG or platform init fails. */
}
