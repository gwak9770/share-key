#include "pwm_clock.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>

static void timer_clocks(void) {
    const uint32_t hclk = 168000000u;
    const uint32_t dividers[] = {1u, 2u, 4u, 8u, 16u};
    const uint32_t expected_default[] = {168000000u, 168000000u, 84000000u,
                                         42000000u, 21000000u};
    const uint32_t expected_timpre[] = {168000000u, 168000000u, 168000000u,
                                        84000000u, 42000000u};
    uint32_t actual = 0u;
    for (unsigned i = 0; i < sizeof(dividers) / sizeof(dividers[0]); ++i) {
        assert(pwm_timer_input_hz(hclk, hclk / dividers[i], false, &actual));
        assert(actual == expected_default[i]);
        assert(pwm_timer_input_hz(hclk, hclk / dividers[i], true, &actual));
        assert(actual == expected_timpre[i]);
    }
    assert(pwm_timer_input_hz(16000000u, 16000000u, false, &actual));
    assert(actual == 16000000u);
    assert(!pwm_timer_input_hz(hclk, 0u, false, &actual));
    assert(!pwm_timer_input_hz(0u, 1u, false, &actual));
    assert(!pwm_timer_input_hz(168000000u, 56000000u, false, &actual));
    assert(!pwm_timer_input_hz(168000001u, 42000000u, false, &actual));
    assert(!pwm_timer_input_hz(hclk, 42000000u, false, NULL));
}

static void settings(void) {
    PwmSettings s;
    const uint32_t clocks[] = {16000000u, 84000000u, 168000000u};
    const uint16_t prescalers[] = {15u, 83u, 167u};
    for (unsigned i = 0; i < sizeof(clocks) / sizeof(clocks[0]); ++i) {
        assert(pwm_servo_settings(clocks[i], 50u, &s));
        assert(s.prescaler == prescalers[i] && s.autoreload == 19999u);
        assert(s.counter_hz == 1000000u && s.pwm_hz == 50u);
        assert(clocks[i] / ((uint32_t)s.prescaler + 1u) == 1000000u);
        assert(1000000u / ((uint32_t)s.autoreload + 1u) == 50u);
        assert(pwm_motor_settings(clocks[i], 10000u, &s));
        assert(s.prescaler == 0u && s.autoreload == clocks[i] / 10000u - 1u);
        assert(pwm_compare_permille(s.autoreload, 600u) ==
               ((uint32_t)s.autoreload + 1u) * 6u / 10u);
    }
    assert(!pwm_servo_settings(84100000u, 50u, &s));
    assert(!pwm_servo_settings(84000000u, 60u, &s));
    assert(!pwm_servo_settings(84000000u, 10u, &s));
    assert(!pwm_servo_settings(84000000u, 0u, &s));
    assert(!pwm_servo_settings(84000000u, 50u, NULL));
    assert(!pwm_motor_settings(168000001u, 10000u, &s));
    assert(!pwm_motor_settings(0u, 10000u, &s));
    assert(!pwm_motor_settings(10000u, 10000u, &s));
    assert(!pwm_motor_settings(168000000u, 0u, &s));
    assert(pwm_motor_settings(168000000u, 1000u, &s));
    assert((uint64_t)((uint32_t)s.prescaler + 1u) *
           ((uint32_t)s.autoreload + 1u) * 1000u == 168000000u);
    assert(pwm_compare_permille(16799u, 0u) == 0u);
    assert(pwm_compare_permille(16799u, 600u) == 10080u);
    assert(pwm_compare_permille(16799u, 1001u) == 16800u);
    assert(pwm_compare_permille(65535u, 1000u) == 65535u);
}

int main(void) {
    timer_clocks();
    settings();
    puts("PASS PWM clocks: APB ratios, TIMPRE, exact 50Hz/1us and 10kHz, duty scaling, invalid clocks");
    return 0;
}
