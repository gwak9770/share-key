#ifndef VEHICLE_PWM_CLOCK_H
#define VEHICLE_PWM_CLOCK_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint16_t prescaler;
    uint16_t autoreload;
    uint32_t counter_hz;
    uint32_t pwm_hz;
} PwmSettings;

/* STM32F429 timer clock, using the current HCLK/PCLK ratio and TIMPRE.
 * Returns false for an invalid APB ratio or an unrepresentable clock. */
bool pwm_timer_input_hz(uint32_t hclk_hz, uint32_t pclk_hz,
                        bool timpre, uint32_t *timer_hz);

/* Servo compares are in microseconds: the counter is exactly 1 MHz. */
bool pwm_servo_settings(uint32_t timer_hz, uint32_t pwm_hz, PwmSettings *out);

/* Finds an exact frequency using a 16-bit prescaler and 16-bit period.
 * The smallest usable prescaler preserves the greatest duty resolution. */
bool pwm_motor_settings(uint32_t timer_hz, uint32_t pwm_hz, PwmSettings *out);

/* Saturates permille to 1000 and the result to a 16-bit compare value. */
uint32_t pwm_compare_permille(uint16_t autoreload, uint32_t permille);

#endif
