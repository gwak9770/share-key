#ifndef VEHICLE_CONFIG_H
#define VEHICLE_CONFIG_H

#ifndef VC_REAUTH_ENABLE
#define VC_REAUTH_ENABLE 1
#endif
#ifndef VC_REAUTH_PERIOD_S
#define VC_REAUTH_PERIOD_S 60u
#endif
#ifndef VC_REAUTH_GRACE_S
#define VC_REAUTH_GRACE_S 30u
#endif
#ifndef VC_STOP_CUTOFF_S
#define VC_STOP_CUTOFF_S 600u
#endif
/* Project demo only: USER toggles an assumed DRIVE/STOP, not measured speed. */
#ifndef VC_DEMO_DRIVE_INPUT
#define VC_DEMO_DRIVE_INPUT 1
#endif

/* Flash defaults ON on the target. Blank media requires authenticated recovery. */
#ifndef VC_ENABLE_FLASH
#define VC_ENABLE_FLASH 1
#endif

/* 1128 (김채희): DS3231 RTC feeds B/D period checks (00 §6 13·14). Needed before
 * the policy check below. RTC holds Korea local time; VC_RTC_UTC_OFFSET_S
 * converts it to the server's UTC Unix seconds. */
#ifndef VC_ENABLE_RTC
#define VC_ENABLE_RTC 0
#endif
#ifndef VC_RTC_UTC_OFFSET_S
#define VC_RTC_UTC_OFFSET_S 32400   /* KST = UTC+9 */
#endif

/* F429 v2, 2026-10-28. A/C need no clock. B/D need VC_ENABLE_RTC=1 (1128). */
#ifndef APP_POLICY_MODE
#define APP_POLICY_MODE 'C'
#endif
#if APP_POLICY_MODE != 'A' && APP_POLICY_MODE != 'B' && APP_POLICY_MODE != 'C' && APP_POLICY_MODE != 'D'
#error "APP_POLICY_MODE must be A, B, C or D."
#endif
#if (APP_POLICY_MODE == 'B' || APP_POLICY_MODE == 'D') && !VC_ENABLE_RTC
#error "B/D period policy needs VC_ENABLE_RTC=1 (no trusted clock otherwise)."
#endif
/* 1103 (권기백): demo-only boot mode selection with the Nucleo USER button
 * (B1, PC13, high while pressed). Hold USER while pressing RESET -> the next
 * mode after APP_POLICY_MODE in VC_DEMO_MODES; keep holding to step every
 * VC_MODE_STEP_MS; release to confirm. Not held -> APP_POLICY_MODE.
 * Still held after VC_MODE_SELECT_MAX_MS -> the mode on screen is confirmed.
 * 1104: UART bytes received while selecting are dropped (only HB that arrive
 * after selection make the link fresh).
 * Flash-enabled builds restore keys/counts after RESET. Only the explicit
 * VC_ENABLE_FLASH=0 demo discards them. Provision distinct keys for comparisons.
 * Default OFF: a real vehicle must not let a physical button pick a weaker
 * policy. B/D are accepted only when VC_ENABLE_RTC=1 (1128). With RTC the
 * default list is A -> B -> C -> D; set APP_POLICY_MODE 'A' for an A default. */
#ifndef VC_DEMO_MODE_SELECT
#define VC_DEMO_MODE_SELECT 0
#endif
#ifndef VC_DEMO_MODES
#if VC_ENABLE_RTC
#define VC_DEMO_MODES "ABCD"
#else
#define VC_DEMO_MODES "CA"
#endif
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
/* 1128 (권기백): passive buzzer on PA6 (TIM3_CH1, Zio D12), signal + GND.
 * Sounds only mirror results the policy core already decided (allow, deny,
 * engine off) and the reauth warning; they never grant or block anything.
 * Off by default until the board check; a buzzer setup failure only mutes it. */
#ifndef VC_ENABLE_BUZZER
#define VC_ENABLE_BUZZER 0
#endif
#ifndef VC_DOOR_ACTIVE_LOW
#define VC_DOOR_ACTIVE_LOW 1
#endif

#define DEBOUNCE_MS 30u
#define LINK_TIMEOUT_MS 2000u
#define SERVO_TIMEOUT_MS 1500u
#define SERVO_MIN_SETTLE_MS 100u
#define SERVO_TRAVEL_MS 500u
/* 11/28 (김채희): new SG90 on the 11/27 body. Lock arm touches the door,
 * unlock swings outward so the door opens. Bench TEST SERVO, 5 cycles, no buzz. */
#define SERVO_LOCK_US 2100u
#define SERVO_UNLOCK_US 1000u
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
/* Buzzer pitches (Hz). Allow high, deny low, engine off falls in three steps,
 * the reauth warning rises while driving -> stopped -> last third before cutoff. */
#define BUZZER_ALLOW_HZ 2500u
#define BUZZER_DENY_HZ 400u
#define BUZZER_OFF1_HZ 1500u
#define BUZZER_OFF2_HZ 1000u
#define BUZZER_OFF3_HZ 600u
#define BUZZER_WARN_DRIVE_HZ 1000u
#define BUZZER_WARN_STOP_HZ 2000u
#define BUZZER_WARN_CUTOFF_HZ 3000u

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
