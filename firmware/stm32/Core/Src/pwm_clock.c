#include "pwm_clock.h"
#include <stddef.h>
#include <limits.h>

bool pwm_timer_input_hz(uint32_t hclk_hz, uint32_t pclk_hz,
                        bool timpre, uint32_t *timer_hz) {
    if (timer_hz == NULL || pclk_hz == 0u || hclk_hz == 0u ||
        hclk_hz % pclk_hz != 0u) return false;
    uint32_t divider = hclk_hz / pclk_hz;
    if (divider != 1u && divider != 2u && divider != 4u &&
        divider != 8u && divider != 16u) return false;
    uint64_t value;
    if (timpre) value = divider <= 4u ? hclk_hz : (uint64_t)pclk_hz * 4u;
    else value = divider == 1u ? pclk_hz : (uint64_t)pclk_hz * 2u;
    if (value == 0u || value > UINT32_MAX) return false;
    *timer_hz = (uint32_t)value;
    return true;
}

bool pwm_servo_settings(uint32_t timer_hz, uint32_t pwm_hz, PwmSettings *out) {
    const uint32_t tick_hz = 1000000u;
    if (out == NULL || timer_hz < tick_hz || timer_hz % tick_hz != 0u ||
        pwm_hz == 0u || tick_hz % pwm_hz != 0u) return false;
    uint32_t divider = timer_hz / tick_hz;
    uint32_t period = tick_hz / pwm_hz;
    if (divider > 65536u || period == 0u || period > 65536u) return false;
    out->prescaler = (uint16_t)(divider - 1u);
    out->autoreload = (uint16_t)(period - 1u);
    out->counter_hz = tick_hz;
    out->pwm_hz = pwm_hz;
    return true;
}

bool pwm_motor_settings(uint32_t timer_hz, uint32_t pwm_hz, PwmSettings *out) {
    if (out == NULL || timer_hz == 0u || pwm_hz == 0u ||
        timer_hz % pwm_hz != 0u) return false;
    uint32_t total_divider = timer_hz / pwm_hz;
    if (total_divider < 2u) return false;
    uint32_t first = (uint32_t)(((uint64_t)total_divider + 65535u) / 65536u);
    for (uint32_t divider = first; divider <= 65536u; ++divider) {
        if (total_divider % divider != 0u) continue;
        uint32_t period = total_divider / divider;
        if (period < 2u || period > 65536u) continue;
        out->prescaler = (uint16_t)(divider - 1u);
        out->autoreload = (uint16_t)(period - 1u);
        out->counter_hz = timer_hz / divider;
        out->pwm_hz = pwm_hz;
        return true;
    }
    return false;
}

uint32_t pwm_compare_permille(uint16_t autoreload, uint32_t permille) {
    if (permille > 1000u) permille = 1000u;
    uint32_t result = ((uint32_t)autoreload + 1u) * permille / 1000u;
    return result > 65535u ? 65535u : result;
}
