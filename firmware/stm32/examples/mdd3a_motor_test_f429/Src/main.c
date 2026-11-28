/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "string.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

ETH_TxPacketConfig TxConfig;
ETH_DMADescTypeDef  DMARxDscrTab[ETH_RX_DESC_CNT]; /* Ethernet Rx DMA Descriptors */
ETH_DMADescTypeDef  DMATxDscrTab[ETH_TX_DESC_CNT]; /* Ethernet Tx DMA Descriptors */

ETH_HandleTypeDef heth;

I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim4;

UART_HandleTypeDef huart3;

PCD_HandleTypeDef hpcd_USB_OTG_FS;

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ETH_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_USB_OTG_FS_PCD_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM4_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

static uint8_t rtc_frame[1025];

// 숫자 및 기호, 문자 폰트
static const char rtc_chars[] =
    "0123456789-: RT CIMEOKNG";

static const uint8_t rtc_font[][5] = {
    {0x3E,0x41,0x41,0x41,0x3E}, // 0
    {0x00,0x42,0x7F,0x40,0x00}, // 1
    {0x62,0x51,0x49,0x49,0x46}, // 2
    {0x22,0x41,0x49,0x49,0x36}, // 3
    {0x18,0x14,0x12,0x7F,0x10}, // 4
    {0x27,0x45,0x45,0x45,0x39}, // 5
    {0x3E,0x49,0x49,0x49,0x32}, // 6
    {0x01,0x71,0x09,0x05,0x03}, // 7
    {0x36,0x49,0x49,0x49,0x36}, // 8
    {0x26,0x49,0x49,0x49,0x3E}, // 9
    {0x08,0x08,0x08,0x08,0x08}, // -
    {0x00,0x36,0x36,0x00,0x00}, // :
    {0x00,0x00,0x00,0x00,0x00}, // Space
    {0x7F,0x09,0x19,0x29,0x46}, // R
    {0x01,0x01,0x7F,0x01,0x01}, // T
    {0x00,0x00,0x00,0x00,0x00}, // Space
    {0x3E,0x41,0x41,0x41,0x22}, // C
    {0x00,0x41,0x7F,0x41,0x00}, // I
    {0x7F,0x02,0x0C,0x02,0x7F}, // M
    {0x7F,0x49,0x49,0x49,0x41}, // E
    {0x3E,0x41,0x41,0x41,0x3E}, // O
    {0x7F,0x08,0x14,0x22,0x41}, // K
    {0x7F,0x02,0x04,0x08,0x7F}, // N
    {0x3E,0x41,0x49,0x49,0x7A}  // G
};

// BCD -> Decimal
static uint8_t RTC_BCD(uint8_t value)
{
    return ((value >> 4) * 10)
           + (value & 0x0F);
}

// OLED 문자 그리기
static void RTC_DrawText(
    uint8_t x,
    uint8_t y,
    const char *text,
    uint8_t scale)
{
    while (*text)
    {
        const char *p = strchr(rtc_chars, *text);

        if (p != NULL)
        {
            uint8_t index = p - rtc_chars;

            for (uint8_t col = 0; col < 5; col++)
            {
                for (uint8_t row = 0; row < 7; row++)
                {
                    if (rtc_font[index][col] & (1U << row))
                    {
                        for (uint8_t dx = 0; dx < scale; dx++)
                        {
                            for (uint8_t dy = 0; dy < scale; dy++)
                            {
                                uint16_t px =
                                    x + col * scale + dx;

                                uint16_t py =
                                    y + row * scale + dy;

                                if (px < 128 && py < 64)
                                {
                                    rtc_frame[
                                        1 + (py / 8) * 128 + px
                                    ] |= (1U << (py % 8));
                                }
                            }
                        }
                    }
                }
            }
        }

        x += 6 * scale;
        text++;
    }
}

// RTC 날짜 및 시간 읽기, OLED 출력
static HAL_StatusTypeDef RTC_ShowTime(uint8_t addr)
{
    uint8_t data[7];
    uint8_t flags = 0;

    char date[16];
    char time[16];

    memset(rtc_frame, 0, sizeof(rtc_frame));
    rtc_frame[0] = 0x40;

    RTC_DrawText(25, 2, "RTC TIME TEST", 1);

    HAL_StatusTypeDef result = HAL_I2C_Mem_Read(
        &hi2c1,
        (0x68 << 1),
        0x00,
        I2C_MEMADD_SIZE_8BIT,
        data,
        sizeof(data),
        100
    );

    if (result == HAL_OK)
    {
        uint8_t sec = RTC_BCD(data[0] & 0x7F);
        uint8_t min = RTC_BCD(data[1] & 0x7F);
        uint8_t hour = RTC_BCD(data[2] & 0x3F);

        uint8_t day = RTC_BCD(data[4] & 0x3F);
        uint8_t month = RTC_BCD(data[5] & 0x1F);
        uint8_t year = RTC_BCD(data[6]);

        snprintf(date, sizeof(date),
                 "20%02u-%02u-%02u",
                 year, month, day);

        snprintf(time, sizeof(time),
                 "%02u:%02u:%02u",
                 hour, min, sec);

        RTC_DrawText(4, 15, date, 2);
        RTC_DrawText(0, 32, time, 2);

        result = HAL_I2C_Mem_Read(
            &hi2c1,
            (0x68 << 1),
            0x0F,
            I2C_MEMADD_SIZE_8BIT,
            &flags,
            1,
            100
        );

        if (result == HAL_OK && !(flags & 0x80))
        {
            RTC_DrawText(46, 55, "RTC OK", 1);
        }
        else
        {
            RTC_DrawText(46, 55, "RTC NG", 1);
        }
    }
    else
    {
        RTC_DrawText(46, 28, "RTC NG", 1);
    }

    uint8_t window[] = {
        0x00,
        0x21, 0x00, 0x7F,
        0x22, 0x00, 0x07
    };

    if (HAL_I2C_Master_Transmit(
            &hi2c1,
            (addr << 1),
            window,
            sizeof(window),
            200) != HAL_OK)
    {
        return HAL_ERROR;
    }

    return HAL_I2C_Master_Transmit(
        &hi2c1,
        (addr << 1),
        rtc_frame,
        sizeof(rtc_frame),
        500
    );
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_ETH_Init();
  MX_USART3_UART_Init();
  MX_USB_OTG_FS_PCD_Init();
  MX_I2C1_Init();
  MX_TIM4_Init();
  /* USER CODE BEGIN 2 */


  // ===== RTC 날짜 및 시간 설정 =====

  // 1: 시간 설정 실행
  // 0: 시간 설정 안 함
  #define RTC_SET_TIME 0

  #if RTC_SET_TIME

  // 아래 값을 실제 현재 시간으로 변경
  uint8_t set_year   = 26;
  uint8_t set_month  = 11;
  uint8_t set_date   = 27;
  uint8_t set_day    = 6;
  uint8_t set_hour   = 19;
  uint8_t set_minute = 2;
  uint8_t set_second = 0;

  // 십진수 → BCD 변환
  uint8_t rtc_set[7] = {
      ((set_second / 10) << 4) | (set_second % 10),
      ((set_minute / 10) << 4) | (set_minute % 10),
      ((set_hour / 10) << 4) | (set_hour % 10),
      set_day,
      ((set_date / 10) << 4) | (set_date % 10),
      ((set_month / 10) << 4) | (set_month % 10),
      ((set_year / 10) << 4) | (set_year % 10)
  };

  volatile HAL_StatusTypeDef rtc_set_result;

  HAL_Delay(200);

  // DS3231 시간 레지스터에 기록
  rtc_set_result = HAL_I2C_Mem_Write(
      &hi2c1,
      (0x68 << 1),
      0x00,
      I2C_MEMADD_SIZE_8BIT,
      rtc_set,
      sizeof(rtc_set),
      100
  );

  // RTC 시간 설정 실패 확인
  if (rtc_set_result != HAL_OK)
  {
      HAL_GPIO_WritePin(GPIOB,
          GPIO_PIN_14, GPIO_PIN_SET);

      while (1)
      {
          HAL_Delay(100);
      }
  }

  #endif

  // ===== RTC 날짜 및 시간 설정 끝 =====

  // RTC 시험용 LED 초기화
  __HAL_RCC_GPIOB_CLK_ENABLE();

  GPIO_InitTypeDef rtc_led = {0};
  rtc_led.Pin = GPIO_PIN_0 | GPIO_PIN_14;
  rtc_led.Mode = GPIO_MODE_OUTPUT_PP;
  rtc_led.Pull = GPIO_NOPULL;
  rtc_led.Speed = GPIO_SPEED_FREQ_LOW;

  HAL_GPIO_Init(GPIOB, &rtc_led);

  HAL_GPIO_WritePin(GPIOB,
      GPIO_PIN_0 | GPIO_PIN_14,
      GPIO_PIN_RESET);

  HAL_Delay(200);

  uint8_t rtc_first = 0;
  uint8_t rtc_second = 0;

  HAL_StatusTypeDef status1;
  HAL_StatusTypeDef status2;

  // 첫 번째 초 데이터 읽기
  status1 = HAL_I2C_Mem_Read(
      &hi2c1,
      (0x68 << 1),
      0x00,
      I2C_MEMADD_SIZE_8BIT,
      &rtc_first,
      1,
      100
  );

  // 2초 대기
  HAL_Delay(2000);

  // 두 번째 초 데이터 읽기
  status2 = HAL_I2C_Mem_Read(
      &hi2c1,
      (0x68 << 1),
      0x00,
      I2C_MEMADD_SIZE_8BIT,
      &rtc_second,
      1,
      100
  );

  // BCD 데이터를 십진수로 변환
  uint8_t sec1 =
      ((rtc_first >> 4) & 0x07) * 10
      + (rtc_first & 0x0F);

  uint8_t sec2 =
      ((rtc_second >> 4) & 0x07) * 10
      + (rtc_second & 0x0F);

  uint8_t diff = (sec2 + 60 - sec1) % 60;

  uint8_t rtc_flags = 0;

  HAL_StatusTypeDef flag_status;

  flag_status = HAL_I2C_Mem_Read(
      &hi2c1,
      (0x68 << 1),
      0x0F,
      I2C_MEMADD_SIZE_8BIT,
      &rtc_flags,
      1,
      100
  );

  // OSF 비트 확인
  uint8_t rtc_osf = (rtc_flags & 0x80) != 0;

  // 읽기 성공 및 시간 증가 확인
  if (status1 == HAL_OK &&
      status2 == HAL_OK &&
	  flag_status == HAL_OK &&
      sec1 < 60 &&
      sec2 < 60 &&
      diff >= 1 &&
      diff <= 3)
  {
      HAL_GPIO_WritePin(GPIOB,
          GPIO_PIN_0, GPIO_PIN_SET);

      if (rtc_osf)
          {
              HAL_GPIO_WritePin(GPIOB,
                  GPIO_PIN_14, GPIO_PIN_SET);
          }
  }
  else
  {
      HAL_GPIO_WritePin(GPIOB,
          GPIO_PIN_14, GPIO_PIN_SET);
  }


  // ===== OLED I2C 통신 시험 =====

  // 파란색 LD2 초기화 (PB7)
  __HAL_RCC_GPIOB_CLK_ENABLE();

  GPIO_InitTypeDef oled_led = {0};

  oled_led.Pin = GPIO_PIN_7;
  oled_led.Mode = GPIO_MODE_OUTPUT_PP;
  oled_led.Pull = GPIO_NOPULL;
  oled_led.Speed = GPIO_SPEED_FREQ_LOW;

  HAL_GPIO_Init(GPIOB, &oled_led);

  HAL_GPIO_WritePin(GPIOB,
      GPIO_PIN_7, GPIO_PIN_RESET);

  // OLED 하드웨어 리셋
  HAL_GPIO_WritePin(
      OLED_RST_GPIO_Port,
      OLED_RST_Pin,
      GPIO_PIN_RESET
  );

  HAL_Delay(20);

  // OLED 리셋 해제
  HAL_GPIO_WritePin(
      OLED_RST_GPIO_Port,
      OLED_RST_Pin,
      GPIO_PIN_SET
  );

  HAL_Delay(100);

  // OLED I2C 주소 확인
  uint8_t oled_addr = 0;

  if (HAL_I2C_IsDeviceReady(
          &hi2c1, (0x3C << 1), 3, 100)
          == HAL_OK)
  {
      oled_addr = 0x3C;
  }
  else if (HAL_I2C_IsDeviceReady(
          &hi2c1, (0x3D << 1), 3, 100)
          == HAL_OK)
  {
      oled_addr = 0x3D;
  }

  // OLED 통신 결과 표시
  if (oled_addr != 0)
  {
      HAL_GPIO_WritePin(GPIOB,
          GPIO_PIN_7, GPIO_PIN_SET);
  }
  else
  {
      HAL_GPIO_WritePin(GPIOB,
          GPIO_PIN_14, GPIO_PIN_SET);
  }

  // ===== OLED I2C 통신 시험 끝 =====

  // ===== SSD1309 문자 출력 시험 =====

  if (oled_addr != 0)
  {
      uint8_t oled_init[] = {
          0x00,
          0xAE,
          0xD5, 0x80,
          0xA8, 0x3F,
          0xD3, 0x00,
          0x40,
          0x20, 0x00,
          0xA1,
          0xC8,
          0xDA, 0x12,
          0x81, 0x40,
          0xD9, 0x22,
          0xDB, 0x34,
          0xA4,
          0xA6,
          0x2E,
          0xAF
      };

      HAL_StatusTypeDef oled_result;

      oled_result = HAL_I2C_Master_Transmit(
          &hi2c1,
          (oled_addr << 1),
          oled_init,
          sizeof(oled_init),
          200
      );

      // 5x7 문자 비트맵
      const uint8_t font[8][5] = {
          {0x7F,0x08,0x14,0x22,0x41}, // K
          {0x7F,0x49,0x49,0x49,0x41}, // E
          {0x07,0x08,0x70,0x08,0x07}, // Y
          {0x00,0x00,0x00,0x00,0x00}, // Space
          {0x3E,0x41,0x41,0x41,0x3E}, // O
          {0x7F,0x02,0x04,0x08,0x7F}, // N
          {0x3E,0x41,0x49,0x49,0x7A}, // G
          {0x7F,0x08,0x14,0x22,0x41}  // K
      };

      const uint8_t messages[2][6] = {
          {0, 1, 2, 3, 4, 7}, // KEY OK
          {0, 1, 2, 3, 5, 6}  // KEY NG
      };

      static uint8_t frame[1025];

      // KEY OK / KEY NG 각각 3회 출력
      for (uint8_t trial = 0;
           trial < 6 && oled_result == HAL_OK;
           trial++)
      {
          frame[0] = 0x40;

          // 화면 초기화
          for (uint16_t i = 1; i < 1025; i++)
          {
              frame[i] = 0x00;
          }

          // 문자를 3배 크기로 확대
          for (uint8_t ch = 0; ch < 6; ch++)
          {
              for (uint8_t col = 0; col < 5; col++)
              {
                  uint8_t bits =
                      font[messages[trial % 2][ch]][col];

                  for (uint8_t row = 0; row < 7; row++)
                  {
                      if (bits & (1U << row))
                      {
                          for (uint8_t dx = 0; dx < 3; dx++)
                          {
                              for (uint8_t dy = 0; dy < 3; dy++)
                              {
                                  uint8_t x =
                                      10 + ch * 18 + col * 3 + dx;

                                  uint8_t y =
                                      21 + row * 3 + dy;

                                  frame[1 + (y / 8) * 128 + x]
                                      |= (1U << (y % 8));
                              }
                          }
                      }
                  }
              }
          }

          uint8_t window[] = {
              0x00,
              0x21, 0x00, 0x7F,
              0x22, 0x00, 0x07
          };

          oled_result = HAL_I2C_Master_Transmit(
              &hi2c1,
              (oled_addr << 1),
              window,
              sizeof(window),
              200
          );

          if (oled_result == HAL_OK)
          {
              oled_result = HAL_I2C_Master_Transmit(
                  &hi2c1,
                  (oled_addr << 1),
                  frame,
                  sizeof(frame),
                  500
              );
          }

          HAL_Delay(2000);
      }

      if (oled_result != HAL_OK)
      {
          HAL_GPIO_WritePin(GPIOB,
              GPIO_PIN_7, GPIO_PIN_RESET);

          HAL_GPIO_WritePin(GPIOB,
              GPIO_PIN_14, GPIO_PIN_SET);
      }
  }

  // ===== SSD1309 화면 출력 시험 끝 =====


  // ===== SG90 서보모터 독립 시험 =====

  // 전원 연결 준비 시간 확보
  HAL_Delay(5000);

  // 중앙 위치 설정
  __HAL_TIM_SET_COMPARE(
      &htim4,
      TIM_CHANNEL_3,
      1500
  );

  // PWM 출력 시작
  if (HAL_TIM_PWM_Start(
          &htim4,
          TIM_CHANNEL_3) == HAL_OK)
  {
      HAL_Delay(2000);

      for (uint8_t i = 0; i < 2; i++)
      {
          // 잠금 위치
          __HAL_TIM_SET_COMPARE(
              &htim4,
              TIM_CHANNEL_3,
              1000
          );

          HAL_Delay(2000);

          // 중앙 위치
          __HAL_TIM_SET_COMPARE(
              &htim4,
              TIM_CHANNEL_3,
              1500
          );

          HAL_Delay(2000);
      }

      // PWM 출력 정지
      HAL_TIM_PWM_Stop(
          &htim4,
          TIM_CHANNEL_3
      );
  }
  else
  {
      // PWM 시작 실패 시 빨간색 LED
      HAL_GPIO_WritePin(
          GPIOB,
          GPIO_PIN_14,
          GPIO_PIN_SET
      );
  }

  // ===== SG90 서보모터 독립 시험 끝 =====

  // 서보모터 시험 종료 후 RTC 시간 출력
  if (oled_addr != 0)
  {
      if (RTC_ShowTime(oled_addr) != HAL_OK)
      {
          HAL_GPIO_WritePin(
              GPIOB,
              GPIO_PIN_14,
              GPIO_PIN_SET
          );
      }
  }

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */


	  /* Test sequence: M1 -> M2 -> ALL */
	  static uint8_t test_step = 0;

	  uint16_t motor_pins =
	      GPIO_PIN_9 | GPIO_PIN_11 |
	      GPIO_PIN_13 | GPIO_PIN_14;

	  uint16_t active_pins = 0;

	  /* Stop all motors */
	  HAL_GPIO_WritePin(GPIOE, motor_pins,
	                    GPIO_PIN_RESET);

	  /* Wait for stable button release */
	  do
	  {
	      while (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13)
	             == GPIO_PIN_SET)
	      {
	          HAL_Delay(1);
	      }

	      HAL_Delay(30);

	  } while (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13)
	           == GPIO_PIN_SET);

	  /* Wait for a new button press */
	  while (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13)
	         == GPIO_PIN_RESET)
	  {
	      HAL_Delay(1);
	  }

	  HAL_Delay(30);

	  if (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13)
	      == GPIO_PIN_SET)
	  {

		  switch (test_step)
		  {
		      case 0:
		          active_pins = GPIO_PIN_9;
		          break;

		      case 1:
		          active_pins = GPIO_PIN_13;
		          break;

		      case 2:
		          active_pins = GPIO_PIN_9 |
		                        GPIO_PIN_13;
		          break;

		      default:
		          active_pins = 0;
		          break;
		  }


	      uint32_t start = HAL_GetTick();

	      /* 60% software PWM, maximum 500 ms */
	      while ((HAL_GetTick() - start < 500U) &&
	             (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13)
	              == GPIO_PIN_SET))
	      {
	          uint32_t elapsed = HAL_GetTick() - start;

	          HAL_GPIO_WritePin(
	              GPIOE,
	              active_pins,
	              (elapsed % 10U < 6U)
	                  ? GPIO_PIN_SET
	                  : GPIO_PIN_RESET
	          );

	          HAL_Delay(1);
	      }

	      /* Stop all motors */
	      HAL_GPIO_WritePin(GPIOE, motor_pins,
	                        GPIO_PIN_RESET);

	      /* Select next test */
	      test_step = (test_step + 1U) % 3U;
	  }


  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_BYPASS;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 168;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ETH Initialization Function
  * @param None
  * @retval None
  */
static void MX_ETH_Init(void)
{

  /* USER CODE BEGIN ETH_Init 0 */

  /* USER CODE END ETH_Init 0 */

   static uint8_t MACAddr[6];

  /* USER CODE BEGIN ETH_Init 1 */

  /* USER CODE END ETH_Init 1 */
  heth.Instance = ETH;
  MACAddr[0] = 0x00;
  MACAddr[1] = 0x80;
  MACAddr[2] = 0xE1;
  MACAddr[3] = 0x00;
  MACAddr[4] = 0x00;
  MACAddr[5] = 0x00;
  heth.Init.MACAddr = &MACAddr[0];
  heth.Init.MediaInterface = HAL_ETH_RMII_MODE;
  heth.Init.TxDesc = DMATxDscrTab;
  heth.Init.RxDesc = DMARxDscrTab;
  heth.Init.RxBuffLen = 1524;

  /* USER CODE BEGIN MACADDRESS */

  /* USER CODE END MACADDRESS */

  if (HAL_ETH_Init(&heth) != HAL_OK)
  {
    Error_Handler();
  }

  memset(&TxConfig, 0 , sizeof(ETH_TxPacketConfig));
  TxConfig.Attributes = ETH_TX_PACKETS_FEATURES_CSUM | ETH_TX_PACKETS_FEATURES_CRCPAD;
  TxConfig.ChecksumCtrl = ETH_CHECKSUM_IPHDR_PAYLOAD_INSERT_PHDR_CALC;
  TxConfig.CRCPadCtrl = ETH_CRC_PAD_INSERT;
  /* USER CODE BEGIN ETH_Init 2 */

  /* USER CODE END ETH_Init 2 */

}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 100000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Analogue filter
  */
  if (HAL_I2CEx_ConfigAnalogFilter(&hi2c1, I2C_ANALOGFILTER_ENABLE) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Digital filter
  */
  if (HAL_I2CEx_ConfigDigitalFilter(&hi2c1, 0) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief TIM4 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM4_Init(void)
{

  /* USER CODE BEGIN TIM4_Init 0 */

  /* USER CODE END TIM4_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM4_Init 1 */

  /* USER CODE END TIM4_Init 1 */
  htim4.Instance = TIM4;
  htim4.Init.Prescaler = 83;
  htim4.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim4.Init.Period = 19999;
  htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
  if (HAL_TIM_Base_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim4, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim4) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim4, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim4, &sConfigOC, TIM_CHANNEL_3) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM4_Init 2 */

  /* USER CODE END TIM4_Init 2 */
  HAL_TIM_MspPostInit(&htim4);

}

/**
  * @brief USART3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART3_UART_Init(void)
{

  /* USER CODE BEGIN USART3_Init 0 */

  /* USER CODE END USART3_Init 0 */

  /* USER CODE BEGIN USART3_Init 1 */

  /* USER CODE END USART3_Init 1 */
  huart3.Instance = USART3;
  huart3.Init.BaudRate = 115200;
  huart3.Init.WordLength = UART_WORDLENGTH_8B;
  huart3.Init.StopBits = UART_STOPBITS_1;
  huart3.Init.Parity = UART_PARITY_NONE;
  huart3.Init.Mode = UART_MODE_TX_RX;
  huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart3.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart3) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART3_Init 2 */

  /* USER CODE END USART3_Init 2 */

}

/**
  * @brief USB_OTG_FS Initialization Function
  * @param None
  * @retval None
  */
static void MX_USB_OTG_FS_PCD_Init(void)
{

  /* USER CODE BEGIN USB_OTG_FS_Init 0 */

  /* USER CODE END USB_OTG_FS_Init 0 */

  /* USER CODE BEGIN USB_OTG_FS_Init 1 */

  /* USER CODE END USB_OTG_FS_Init 1 */
  hpcd_USB_OTG_FS.Instance = USB_OTG_FS;
  hpcd_USB_OTG_FS.Init.dev_endpoints = 4;
  hpcd_USB_OTG_FS.Init.speed = PCD_SPEED_FULL;
  hpcd_USB_OTG_FS.Init.dma_enable = DISABLE;
  hpcd_USB_OTG_FS.Init.phy_itface = PCD_PHY_EMBEDDED;
  hpcd_USB_OTG_FS.Init.Sof_enable = ENABLE;
  hpcd_USB_OTG_FS.Init.low_power_enable = DISABLE;
  hpcd_USB_OTG_FS.Init.lpm_enable = DISABLE;
  hpcd_USB_OTG_FS.Init.vbus_sensing_enable = ENABLE;
  hpcd_USB_OTG_FS.Init.use_dedicated_ep1 = DISABLE;
  if (HAL_PCD_Init(&hpcd_USB_OTG_FS) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USB_OTG_FS_Init 2 */

  /* USER CODE END USB_OTG_FS_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOG_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, LD1_Pin|LD3_Pin|LD2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9|GPIO_PIN_11|GPIO_PIN_13|GPIO_PIN_14, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(OLED_RST_GPIO_Port, OLED_RST_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(USB_PowerSwitchOn_GPIO_Port, USB_PowerSwitchOn_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : PC13 */
  GPIO_InitStruct.Pin = GPIO_PIN_13;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pins : LD1_Pin LD3_Pin LD2_Pin */
  GPIO_InitStruct.Pin = LD1_Pin|LD3_Pin|LD2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pins : PE9 PE11 PE13 PE14 */
  GPIO_InitStruct.Pin = GPIO_PIN_9|GPIO_PIN_11|GPIO_PIN_13|GPIO_PIN_14;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

  /*Configure GPIO pin : OLED_RST_Pin */
  GPIO_InitStruct.Pin = OLED_RST_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(OLED_RST_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : USB_PowerSwitchOn_Pin */
  GPIO_InitStruct.Pin = USB_PowerSwitchOn_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(USB_PowerSwitchOn_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : USB_OverCurrent_Pin */
  GPIO_InitStruct.Pin = USB_OverCurrent_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(USB_OverCurrent_GPIO_Port, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
