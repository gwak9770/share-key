#ifndef SERVO_TEST_F429_H
#define SERVO_TEST_F429_H

#include <stdbool.h>
#include <stdint.h>

/* Bench-only pulse values. Calibrate with the latch mechanically disconnected. */
#ifndef SERVO_TEST_LOCK_US
#define SERVO_TEST_LOCK_US 1200u
#endif
#ifndef SERVO_TEST_UNLOCK_US
#define SERVO_TEST_UNLOCK_US 1800u
#endif
#ifndef SERVO_TEST_INTERVAL_MS
#define SERVO_TEST_INTERVAL_MS 2000u
#endif

/* Independent test module: owns TIM4, PD14 and the default USER button PC13.
 * Do not link this module into the integrated vehicle project. */
bool servo_test_init(void);
void servo_test_process(void);
bool servo_test_start(void);
void servo_test_stop(void);
bool servo_test_running(void);
uint16_t servo_test_pulse_us(void);

#endif
