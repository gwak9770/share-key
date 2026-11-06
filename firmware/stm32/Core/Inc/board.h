#ifndef VEHICLE_BOARD_H
#define VEHICLE_BOARD_H

#include "config.h"
#include "control.h"
#include "stm32f4xx_hal.h"
#include <stdbool.h>

#if !defined(STM32F429xx)
#error "This adapter targets STM32F429xx. Keep the F429 CubeIDE startup and linker files."
#endif

/* NUCLEO-F429ZI, MB1137. Inputs are dry contacts to GND unless configured otherwise. */
#define DOOR_PORT GPIOF
#define DOOR_PIN GPIO_PIN_12
#define LOCK_PORT GPIOF
#define LOCK_PIN GPIO_PIN_13
#define UNLOCK_PORT GPIOF
#define UNLOCK_PIN GPIO_PIN_14
#define STOP_PORT GPIOF
#define STOP_PIN GPIO_PIN_15

#if VC_ENABLE_RTC || VC_ENABLE_OLED
extern I2C_HandleTypeDef vc_hi2c1;
#endif

/* Call once after the Cube-generated clock, GPIO, USART3 and RNG initialization.
 * This adapter owns TIM4, optional TIM1/I2C1 and the documented control pins.
 * It does not own USART3, RNG, IRQ handlers, HAL callbacks or SystemClock_Config. */
bool board_init(void);
Inputs board_inputs(void);
void board_apply(Outputs output);
void board_kill(void);
bool board_faulted(void);
bool board_return_pressed(void);
bool board_mode_button(void);
void board_leds(bool allow, bool online, bool deny);

#endif
