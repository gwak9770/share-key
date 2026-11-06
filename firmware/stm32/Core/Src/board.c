#include "board.h"
#include "pwm_clock.h"
#include <string.h>

#if !defined(HAL_TIM_MODULE_ENABLED)
#error "Enable HAL_TIM_MODULE_ENABLED and compile the STM32F4 HAL TIM drivers."
#endif
#if (VC_ENABLE_RTC || VC_ENABLE_OLED) && !defined(HAL_I2C_MODULE_ENABLED)
#error "RTC/OLED requires HAL_I2C_MODULE_ENABLED and the STM32F4 HAL I2C drivers."
#endif

#if VC_ENABLE_SERVO
static TIM_HandleTypeDef vc_htim4;
static bool servo_ready;
#endif
#if VC_ENABLE_MOTORS
static TIM_HandleTypeDef vc_htim1;
static bool motor_ready;
static uint16_t motor_arr;
#endif
#if VC_ENABLE_RTC || VC_ENABLE_OLED
I2C_HandleTypeDef vc_hi2c1;
#endif
static bool initialized;
static bool failed;

static void gpio(GPIO_TypeDef *port, uint32_t pins, uint32_t mode,
                 uint32_t pull, uint32_t alternate) {
    GPIO_InitTypeDef g = {0};
    g.Pin = pins;
    g.Mode = mode;
    g.Pull = pull;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Alternate = alternate;
    HAL_GPIO_Init(port, &g);
}

#if VC_ENABLE_SERVO || VC_ENABLE_MOTORS
static bool timer_clock(bool apb2, uint32_t *hz) {
    bool timpre = (RCC->DCKCFGR & RCC_DCKCFGR_TIMPRE) != 0u;
    uint32_t pclk = apb2 ? HAL_RCC_GetPCLK2Freq() : HAL_RCC_GetPCLK1Freq();
    return pwm_timer_input_hz(HAL_RCC_GetHCLKFreq(), pclk, timpre, hz);
}

static bool timer_base(TIM_HandleTypeDef *timer, TIM_TypeDef *instance,
                       const PwmSettings *settings) {
    memset(timer, 0, sizeof(*timer));
    timer->Instance = instance;
    timer->Init.Prescaler = settings->prescaler;
    timer->Init.CounterMode = TIM_COUNTERMODE_UP;
    timer->Init.Period = settings->autoreload;
    timer->Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    timer->Init.RepetitionCounter = 0u;
    timer->Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    return HAL_TIM_PWM_Init(timer) == HAL_OK;
}

static bool timer_channel(TIM_HandleTypeDef *timer, uint32_t channel) {
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0u;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCNPolarity = TIM_OCNPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    oc.OCIdleState = TIM_OCIDLESTATE_RESET;
    oc.OCNIdleState = TIM_OCNIDLESTATE_RESET;
    return HAL_TIM_PWM_ConfigChannel(timer, &oc, channel) == HAL_OK;
}
#endif

void board_kill(void) {
    /* Update events immediately latch zero into the PWM preload registers.
     * No interrupt, clock, UART or MCU-reset state is changed here. */
#if VC_ENABLE_MOTORS
    if (motor_ready) {
        TIM1->CCR1 = 0u;
        TIM1->CCR2 = 0u;
        TIM1->CCR3 = 0u;
        TIM1->CCR4 = 0u;
        TIM1->EGR = TIM_EGR_UG;
    }
#endif
#if VC_ENABLE_SERVO
    if (servo_ready) {
        TIM4->CCR3 = 0u;
        TIM4->EGR = TIM_EGR_UG;
    }
#endif
}

static bool fail(void) {
    failed = true;
    board_kill();
    return false;
}

bool board_init(void) {
    if (initialized) return !failed;
    initialized = true;
    failed = false;
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOE_CLK_ENABLE();
    __HAL_RCC_GPIOF_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_7 | GPIO_PIN_14, GPIO_PIN_RESET);
    gpio(GPIOB, GPIO_PIN_0 | GPIO_PIN_7 | GPIO_PIN_14,
         GPIO_MODE_OUTPUT_PP, GPIO_NOPULL, 0u);
#if VC_DOOR_ACTIVE_LOW
    gpio(GPIOF, DOOR_PIN, GPIO_MODE_INPUT, GPIO_PULLUP, 0u);
#else
    gpio(GPIOF, DOOR_PIN, GPIO_MODE_INPUT, GPIO_PULLDOWN, 0u);
#endif
    gpio(GPIOF, STOP_PIN, GPIO_MODE_INPUT, GPIO_PULLUP, 0u);
#if CONTROL_USE_ENDPOINTS
    gpio(GPIOF, LOCK_PIN | UNLOCK_PIN, GPIO_MODE_INPUT, GPIO_PULLUP, 0u);
#endif
#if VC_DEMO_MODE_SELECT
    __HAL_RCC_GPIOC_CLK_ENABLE();          /* B1 USER on PC13, high while pressed */
    gpio(GPIOC, GPIO_PIN_13, GPIO_MODE_INPUT, GPIO_PULLDOWN, 0u);
#endif
#if VC_ENABLE_RETURN_BUTTON
    __HAL_RCC_GPIOG_CLK_ENABLE();
    gpio(GPIOG, GPIO_PIN_14, GPIO_MODE_INPUT, GPIO_PULLUP, 0u);
#endif

    /* Hold all actuator signals low before assigning any timer alternate function.
     * External pulldowns are still needed while the MCU is held in reset. */
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_14, GPIO_PIN_RESET);
    gpio(GPIOD, GPIO_PIN_14, GPIO_MODE_OUTPUT_PP, GPIO_PULLDOWN, 0u);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9 | GPIO_PIN_11 | GPIO_PIN_13 | GPIO_PIN_14,
                     GPIO_PIN_RESET);
    gpio(GPIOE, GPIO_PIN_9 | GPIO_PIN_11 | GPIO_PIN_13 | GPIO_PIN_14,
         GPIO_MODE_OUTPUT_PP, GPIO_PULLDOWN, 0u);

#if VC_ENABLE_SERVO
    uint32_t servo_clock;
    PwmSettings servo_settings;
    if (!timer_clock(false, &servo_clock) ||
        !pwm_servo_settings(servo_clock, SERVO_PWM_HZ, &servo_settings)) return fail();
    __HAL_RCC_TIM4_CLK_ENABLE();
    __HAL_RCC_TIM4_FORCE_RESET();
    __HAL_RCC_TIM4_RELEASE_RESET();
    if (!timer_base(&vc_htim4, TIM4, &servo_settings)) return fail();
    servo_ready = true;
    if (!timer_channel(&vc_htim4, TIM_CHANNEL_3)) return fail();
    TIM4->CCR3 = 0u;
    TIM4->EGR = TIM_EGR_UG;
    if (HAL_TIM_PWM_Start(&vc_htim4, TIM_CHANNEL_3) != HAL_OK) return fail();
    gpio(GPIOD, GPIO_PIN_14, GPIO_MODE_AF_PP, GPIO_PULLDOWN, GPIO_AF2_TIM4);
#endif

#if VC_ENABLE_MOTORS
    uint32_t motor_clock;
    PwmSettings motor_settings;
    if (!timer_clock(true, &motor_clock) ||
        !pwm_motor_settings(motor_clock, MOTOR_PWM_HZ, &motor_settings)) return fail();
    __HAL_RCC_TIM1_CLK_ENABLE();
    __HAL_RCC_TIM1_FORCE_RESET();
    __HAL_RCC_TIM1_RELEASE_RESET();
    if (!timer_base(&vc_htim1, TIM1, &motor_settings)) return fail();
    motor_ready = true;
    motor_arr = motor_settings.autoreload;
    const uint32_t channels[] = {TIM_CHANNEL_1, TIM_CHANNEL_2, TIM_CHANNEL_3, TIM_CHANNEL_4};
    for (unsigned i = 0; i < 4u; ++i) {
        if (!timer_channel(&vc_htim1, channels[i])) return fail();
    }
    board_kill();
    for (unsigned i = 0; i < 4u; ++i) {
        if (HAL_TIM_PWM_Start(&vc_htim1, channels[i]) != HAL_OK) return fail();
    }
    gpio(GPIOE, GPIO_PIN_9 | GPIO_PIN_11 | GPIO_PIN_13 | GPIO_PIN_14,
         GPIO_MODE_AF_PP, GPIO_PULLDOWN, GPIO_AF1_TIM1);
#endif

#if VC_ENABLE_RTC || VC_ENABLE_OLED
    __HAL_RCC_I2C1_CLK_ENABLE();
    __HAL_RCC_I2C1_FORCE_RESET();
    __HAL_RCC_I2C1_RELEASE_RESET();
    gpio(GPIOB, GPIO_PIN_8 | GPIO_PIN_9, GPIO_MODE_AF_OD, GPIO_NOPULL, GPIO_AF4_I2C1);
    memset(&vc_hi2c1, 0, sizeof(vc_hi2c1));
    vc_hi2c1.Instance = I2C1;
    vc_hi2c1.Init.ClockSpeed = 100000u;
    vc_hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
    vc_hi2c1.Init.OwnAddress1 = 0u;
    vc_hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    vc_hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    vc_hi2c1.Init.OwnAddress2 = 0u;
    vc_hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    vc_hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
    if (HAL_I2C_Init(&vc_hi2c1) != HAL_OK) return fail();
#endif
    board_kill();
    return true;
}

Inputs board_inputs(void) {
    Inputs in = {0};
#if VC_DOOR_ACTIVE_LOW
    in.door_closed = HAL_GPIO_ReadPin(DOOR_PORT, DOOR_PIN) == GPIO_PIN_RESET;
#else
    in.door_closed = HAL_GPIO_ReadPin(DOOR_PORT, DOOR_PIN) == GPIO_PIN_SET;
#endif
#if CONTROL_USE_ENDPOINTS
    in.locked = HAL_GPIO_ReadPin(LOCK_PORT, LOCK_PIN) == GPIO_PIN_RESET;
    in.unlocked = HAL_GPIO_ReadPin(UNLOCK_PORT, UNLOCK_PIN) == GPIO_PIN_RESET;
#endif
    in.estop = HAL_GPIO_ReadPin(STOP_PORT, STOP_PIN) == GPIO_PIN_RESET;
    return in;
}

void board_apply(Outputs output) {
    if (!initialized || failed) {
        board_kill();
        return;
    }
    /* Invalid servo values are rejected, not converted into another motion. */
    if (output.servo_us != 0u && (output.servo_us < 500u || output.servo_us > 2500u)) {
        (void)fail();
        return;
    }
#if !VC_ENABLE_SERVO
    if (output.servo_us != 0u) { (void)fail(); return; }
#endif
#if !VC_ENABLE_MOTORS
    if (output.motor != 0) { (void)fail(); return; }
#endif
#if VC_ENABLE_MOTORS
    int motor = output.motor;
    if (motor > MOTOR_MAX_PERMILLE) motor = MOTOR_MAX_PERMILLE;
    if (motor < -MOTOR_MAX_PERMILLE) motor = -MOTOR_MAX_PERMILLE;
    uint32_t duty = pwm_compare_permille(motor_arr, (uint32_t)(motor < 0 ? -motor : motor));
    /* Write the inactive input low first. control.c enforces reversal deadtime. */
    if (motor >= 0) {
        TIM1->CCR2 = 0u;
        TIM1->CCR4 = 0u;
        TIM1->CCR1 = duty;
        TIM1->CCR3 = duty;
    } else {
        TIM1->CCR1 = 0u;
        TIM1->CCR3 = 0u;
        TIM1->CCR2 = duty;
        TIM1->CCR4 = duty;
    }
    if (motor == 0) TIM1->EGR = TIM_EGR_UG;
#endif
#if VC_ENABLE_SERVO
    TIM4->CCR3 = output.servo_us;
    if (output.servo_us == 0u) TIM4->EGR = TIM_EGR_UG;
#endif
}

bool board_faulted(void) { return failed; }

bool board_mode_button(void) {
#if VC_DEMO_MODE_SELECT
    return HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13) == GPIO_PIN_SET;
#else
    return false;
#endif
}
bool board_return_pressed(void) {
#if VC_ENABLE_RETURN_BUTTON
    return HAL_GPIO_ReadPin(GPIOG, GPIO_PIN_14) == GPIO_PIN_RESET;
#else
    return false;
#endif
}

void board_leds(bool allow, bool online, bool deny) {
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, allow ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, online ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, deny ? GPIO_PIN_SET : GPIO_PIN_RESET);
}
