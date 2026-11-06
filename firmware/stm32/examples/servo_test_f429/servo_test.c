#include "servo_test.h"
#include "pwm_clock.h"
#include "stm32f4xx_hal.h"
#include <string.h>

#if !defined(STM32F429xx)
#error "Create this test as an STM32F429ZI project."
#endif
#if !defined(HAL_TIM_MODULE_ENABLED)
#error "Enable HAL_TIM_MODULE_ENABLED and compile STM32F4 TIM/TIMEx HAL sources."
#endif
#if SERVO_TEST_LOCK_US < 500u || SERVO_TEST_LOCK_US > 2500u || \
    SERVO_TEST_UNLOCK_US < 500u || SERVO_TEST_UNLOCK_US > 2500u
#error "Servo test pulses must be between 500 and 2500 microseconds."
#endif

static TIM_HandleTypeDef test_tim4;
static bool initialized, running, high_position;
static bool button_candidate, button_stable, button_qualified;
static bool ready_for_press, press_seen;
static uint32_t button_since, changed_at;
static uint16_t current_pulse;

static bool button_pressed(void) {
    /* Default MB1137 USER button on PC13, high while pressed. */
    return HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13) == GPIO_PIN_SET;
}

bool servo_test_init(void) {
    GPIO_InitTypeDef gpio = {0};
    uint32_t input_hz;
    PwmSettings pwm;
    initialized = false;
    running = false;
    current_pulse = 0u;
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_14, GPIO_PIN_RESET);
    gpio.Pin = GPIO_PIN_14;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_PULLDOWN;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOD, &gpio);

    gpio.Pin = GPIO_PIN_13;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(GPIOC, &gpio);
    bool timpre = (RCC->DCKCFGR & RCC_DCKCFGR_TIMPRE) != 0u;
    if (!pwm_timer_input_hz(HAL_RCC_GetHCLKFreq(), HAL_RCC_GetPCLK1Freq(),
                            timpre, &input_hz) ||
        !pwm_servo_settings(input_hz, 50u, &pwm)) return false;

    __HAL_RCC_TIM4_CLK_ENABLE();
    __HAL_RCC_TIM4_FORCE_RESET();
    __HAL_RCC_TIM4_RELEASE_RESET();
    memset(&test_tim4, 0, sizeof(test_tim4));
    test_tim4.Instance = TIM4;
    test_tim4.Init.Prescaler = pwm.prescaler;
    test_tim4.Init.CounterMode = TIM_COUNTERMODE_UP;
    test_tim4.Init.Period = pwm.autoreload;
    test_tim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    test_tim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_PWM_Init(&test_tim4) != HAL_OK) return false;
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0u;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    if (HAL_TIM_PWM_ConfigChannel(&test_tim4, &oc, TIM_CHANNEL_3) != HAL_OK) return false;
    TIM4->CCR3 = 0u;
    TIM4->EGR = TIM_EGR_UG;
    if (HAL_TIM_PWM_Start(&test_tim4, TIM_CHANNEL_3) != HAL_OK) return false;
    gpio.Pin = GPIO_PIN_14;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLDOWN;
    gpio.Alternate = GPIO_AF2_TIM4;
    HAL_GPIO_Init(GPIOD, &gpio);

    button_candidate = button_stable = button_pressed();
    button_qualified = false;
    ready_for_press = press_seen = false;
    button_since = changed_at = HAL_GetTick();
    initialized = true;
    return true;
}

bool servo_test_start(void) {
    if (!initialized) return false;
    high_position = false;
    current_pulse = SERVO_TEST_LOCK_US;
    changed_at = HAL_GetTick();
    TIM4->CCR3 = current_pulse;
    TIM4->EGR = TIM_EGR_UG;
    running = true;
    return true;
}

void servo_test_stop(void) {
    running = false;
    current_pulse = 0u;
    if (initialized) {
        TIM4->CCR3 = 0u;
        TIM4->EGR = TIM_EGR_UG;
    }
}

void servo_test_process(void) {
    if (!initialized) return;
    uint32_t now = HAL_GetTick();
    bool raw = button_pressed();
    if (raw != button_candidate) {
        button_candidate = raw;
        button_since = now;
    }
    if ((uint32_t)(now - button_since) >= 30u &&
        (!button_qualified || button_stable != button_candidate)) {
        button_stable = button_candidate;
        button_qualified = true;
        if (!button_stable) {
            if (press_seen) {
                if (running) servo_test_stop();
                else (void)servo_test_start();
            }
            press_seen = false;
            ready_for_press = true;
        } else if (ready_for_press) {
            press_seen = true;
            ready_for_press = false;
        }
    }
    if (running && (uint32_t)(now - changed_at) >= SERVO_TEST_INTERVAL_MS) {
        changed_at = now;
        high_position = !high_position;
        current_pulse = high_position ? SERVO_TEST_UNLOCK_US : SERVO_TEST_LOCK_US;
        /* Leave the timer running; the compare preload changes on its next period. */
        TIM4->CCR3 = current_pulse;
    }
}

bool servo_test_running(void) { return running; }
uint16_t servo_test_pulse_us(void) { return current_pulse; }
