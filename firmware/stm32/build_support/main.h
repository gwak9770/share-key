#ifndef VC_BUILD_CHECK_MAIN_H
#define VC_BUILD_CHECK_MAIN_H

/* Standalone ARM build-check harness only. The CubeIDE application keeps its
 * own generated main.h, startup, linker script and interrupt handlers. */
#include "stm32f4xx_hal.h"

extern UART_HandleTypeDef huart3;
extern RNG_HandleTypeDef hrng;
void Error_Handler(void);

#endif
