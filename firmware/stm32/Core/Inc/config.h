#ifndef VEHICLE_CONFIG_H
#define VEHICLE_CONFIG_H

/* F429 v2, 2026-10-28. Main demo remains A/C; policy/wire format is unchanged. */
#ifndef APP_POLICY_MODE
#define APP_POLICY_MODE 'C'
#endif
#if APP_POLICY_MODE != 'A' && APP_POLICY_MODE != 'C'
#error "This integration release supports A/C only; RTC persistence policy needs separate integration."
#endif
/* 1103 (권기백): demo-only boot mode selection with the Nucleo USER button
 * (B1, PC13, high while pressed). Hold USER while pressing RESET -> the next
 * mode after APP_POLICY_MODE in VC_DEMO_MODES; keep holding to step every
 * VC_MODE_STEP_MS; release to confirm. Not held -> APP_POLICY_MODE.
 * Still held after VC_MODE_SELECT_MAX_MS -> the mode on screen is confirmed.
 * 1104: UART bytes received while selecting are dropped (only HB that arrive
 * after selection make the link fresh).
 * Keys/counts are RAM-only, so every RESET needs the key registered again.
 * Default OFF: a real vehicle must not let a physical button pick a weaker
 * policy. Only A/C are accepted until B/D are integrated with the RTC. */
#ifndef VC_DEMO_MODE_SELECT
#define VC_DEMO_MODE_SELECT 0
#endif
#ifndef VC_DEMO_MODES
#define VC_DEMO_MODES "CA"
#endif
#ifndef VC_MODE_STEP_MS
#define VC_MODE_STEP_MS 1500u
#endif
#ifndef VC_MODE_SELECT_MAX_MS
#define VC_MODE_SELECT_MAX_MS 15000u
#endif
#ifndef TEST_BUILD
#define TEST_BUILD 0
#endif
#ifndef CONTROL_USE_ENDPOINTS
#define CONTROL_USE_ENDPOINTS 0
#endif
#ifndef VC_ENABLE_SERVO
#define VC_ENABLE_SERVO 1
#endif
/* Only a qualified OPEN -> CLOSED edge after unlocking requests a relock.
 * Set to 0 to restore the original v2 behaviour. No movement at boot. */
#ifndef VC_RELOCK_ON_DOOR_CLOSE
#define VC_RELOCK_ON_DOOR_CLOSE 1
#endif
#if VC_RELOCK_ON_DOOR_CLOSE != 0 && VC_RELOCK_ON_DOOR_CLOSE != 1
#error "VC_RELOCK_ON_DOOR_CLOSE must be 0 or 1."
#endif
#ifndef VC_ENABLE_MOTORS
#define VC_ENABLE_MOTORS 0
#endif
#ifndef VC_ENABLE_RTC
#define VC_ENABLE_RTC 0
#endif
#ifndef VC_ENABLE_OLED
#define VC_ENABLE_OLED 1
#endif
/* v0.3.5 demo view; set 0 to retain the original eight-line diagnostic view. */
#ifndef VC_OLED_LARGE_TEXT
#define VC_OLED_LARGE_TEXT 1
#endif
#ifndef VC_ENABLE_RETURN_BUTTON
#define VC_ENABLE_RETURN_BUTTON 0
#endif
#ifndef VC_ENABLE_IWDG
#define VC_ENABLE_IWDG 0
#endif
#ifndef VC_DOOR_ACTIVE_LOW
#define VC_DOOR_ACTIVE_LOW 1
#endif

#define DEBOUNCE_MS 30u
#define LINK_TIMEOUT_MS 2000u
#define SERVO_TIMEOUT_MS 1500u
#define SERVO_MIN_SETTLE_MS 100u
#define SERVO_TRAVEL_MS 500u
#define SERVO_LOCK_US 1200u
#define SERVO_UNLOCK_US 1800u
#define SERVO_PWM_HZ 50u
#define MOTOR_PWM_HZ 10000u
#define MOTOR_MAX_PERMILLE 600
#define MOTOR_START_PERMILLE 300
#define MOTOR_RAMP_STEP 20
#define MOTOR_RAMP_MS 10u
#define MOTOR_REVERSE_DEAD_MS 100u
#define VC_LED_PULSE_MS 1000u
#define VC_UART_RX_SIZE 2048u
#define VC_UART_TX_SIZE 4096u
#define VC_RX_BUDGET 128u
#define OLED_ADDRESS 0x3Cu
#define RTC_ADDRESS 0x68u

#if SERVO_TRAVEL_MS >= SERVO_TIMEOUT_MS
#error "SERVO_TRAVEL_MS must be less than SERVO_TIMEOUT_MS."
#endif
#if MOTOR_START_PERMILLE > MOTOR_MAX_PERMILLE || MOTOR_START_PERMILLE <= 0
#error "MOTOR_START_PERMILLE must be positive and within MOTOR_MAX_PERMILLE."
#endif
#if (VC_UART_RX_SIZE & (VC_UART_RX_SIZE - 1u)) || (VC_UART_TX_SIZE & (VC_UART_TX_SIZE - 1u))
#error "UART ring sizes must be powers of two."
#endif

#endif
