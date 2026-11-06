/* Host-test declarations only. Never copy this header into a CubeIDE project. */
#ifndef TEST_OLED_HAL_H
#define TEST_OLED_HAL_H
#include <stdint.h>
typedef struct { int unused; } I2C_HandleTypeDef;
typedef enum { HAL_OK=0, HAL_ERROR=1 } HAL_StatusTypeDef;
HAL_StatusTypeDef HAL_I2C_Master_Transmit(I2C_HandleTypeDef *handle,
    uint16_t address,uint8_t *bytes,uint16_t length,uint32_t timeout);
#endif
