/* Standalone compile/link harness for STM32F429ZI, not a replacement for the
 * team's working CubeIDE generated main.c. HSE comes from ST-LINK MCO (8 MHz).
 * Hardware execution of this harness has not been performed by the build check.
 */
#include "main.h"

#if defined(VC_BUILD_SERVO_TEST)
#include "servo_test.h"
#else
extern void sk_app_run(void);
#endif

UART_HandleTypeDef huart3;
RNG_HandleTypeDef hrng;

void Error_Handler(void) {
    __disable_irq();
    for (;;) { }
}

static void system_clock_config(void) {
    RCC_OscInitTypeDef oscillator = {0};
    RCC_ClkInitTypeDef clocks = {0};

    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
    oscillator.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    oscillator.HSEState = RCC_HSE_BYPASS;
    oscillator.PLL.PLLState = RCC_PLL_ON;
    oscillator.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    oscillator.PLL.PLLM = 8;
    oscillator.PLL.PLLN = 336;
    oscillator.PLL.PLLP = RCC_PLLP_DIV2;
    oscillator.PLL.PLLQ = 7;
    if (HAL_RCC_OscConfig(&oscillator) != HAL_OK) Error_Handler();

    clocks.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK |
                       RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clocks.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clocks.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clocks.APB1CLKDivider = RCC_HCLK_DIV4;
    clocks.APB2CLKDivider = RCC_HCLK_DIV2;
    if (HAL_RCC_ClockConfig(&clocks, FLASH_LATENCY_5) != HAL_OK) Error_Handler();
}

static void usart3_init(void) {
    GPIO_InitTypeDef gpio = {0};
    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_USART3_CLK_ENABLE();
    gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART3;
    HAL_GPIO_Init(GPIOD, &gpio);

    huart3.Instance = USART3;
    huart3.Init.BaudRate = 115200;
    huart3.Init.WordLength = UART_WORDLENGTH_8B;
    huart3.Init.StopBits = UART_STOPBITS_1;
    huart3.Init.Parity = UART_PARITY_NONE;
    huart3.Init.Mode = UART_MODE_TX_RX;
    huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart3.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart3) != HAL_OK) Error_Handler();
    HAL_NVIC_SetPriority(USART3_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(USART3_IRQn);
}

static void rng_init(void) {
    __HAL_RCC_RNG_CLK_ENABLE();
    hrng.Instance = RNG;
    if (HAL_RNG_Init(&hrng) != HAL_OK) Error_Handler();
}

void SysTick_Handler(void) { HAL_IncTick(); }
void USART3_IRQHandler(void) { HAL_UART_IRQHandler(&huart3); }

int main(void) {
    HAL_Init();
    system_clock_config();
    usart3_init();
    rng_init();
#if defined(VC_BUILD_SERVO_TEST)
    if (!servo_test_init()) Error_Handler();
    for (;;) servo_test_process();
#else
    sk_app_run();
    Error_Handler();
#endif
}
