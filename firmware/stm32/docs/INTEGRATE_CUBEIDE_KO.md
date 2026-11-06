# CubeIDE의 F429 프로젝트에 적용

기준 환경은 CubeIDE 1.19.0, STM32CubeF4 1.28.3, 정상 동작한 `sharekey_f429`다. 현재 패키지는 그 프로젝트에 넣을 소스와 적용 도구이며, 김채희 노트북의 실제 `.ioc`와 `.cproject`를 대신 복원한 프로젝트는 아니다.

## 자동 복사 적용

README의 `prepare_cubeide_copy.py`는 다음을 수행한다.

1. 원본 `.ioc`가 STM32F429ZI인지 확인한다.
2. 출력 폴더가 없는 경우에만 새 프로젝트 복사본을 만든다. 원본 프로젝트는 편집하지 않는다.
3. `Core/Inc`, `Core/Src`의 v2 파일을 적용한다. 기존 `port_stm32.c`는 복사본에서 v2로 교체한다.
4. TIM·I²C·IWDG HAL 모듈과 드라이버 소스를 준비한다. 선택 기능의 실제 활성화는 `config.h`가 결정한다.
5. `main.c`에 `sk_app_run()` 호출이 없으면 `USER CODE BEGIN 2`에 추가한다.
6. 기존 Debug/Release 산출물과 `.launch` 파일은 복사하지 않는다. 새 프로젝트에서 Run 설정을 만든다.

프로젝트를 가져온 뒤 Core 소스가 모두 빌드 대상인지 확인하고 Clean/Build한다. `.ioc`를 다시 Generate Code 하면 HAL 선택이나 main 호출 위치가 바뀔 수 있으므로 해당 항목을 다시 대조한다.

## 수동 적용

1. CubeIDE에서 기존 F429 프로젝트를 복사한다. F767 프로젝트는 사용하지 않는다.
2. 배포본의 `Core/Inc` 파일을 대상 `Core/Inc`에, `Core/Src` 파일을 대상 `Core/Src`에 넣는다.
3. 기존 `port_stm32.c`와 새 `port_stm32.c`를 동시에 남기지 않는다. `main_pc.c`, `test_vectors.c`와 `tests`의 파일은 펌웨어 빌드에서 제외한다.
4. F429용 생성 `main.c`, `system_stm32f4xx.c`, `startup_stm32f429xx.s`, `stm32f4xx_it.c`, 링커와 `SystemClock_Config()`는 현재 프로젝트의 것을 사용한다.
5. Cube 생성 초기화가 끝난 `USER CODE BEGIN 2`에 다음 호출을 한 번만 둔다.

   ```c
   extern void sk_app_run(void);
   sk_app_run();
   ```

   이 함수는 돌아오지 않고 인증·제어 메인 루프를 수행한다. 그 뒤에 추가하는 while 루프에 제어 코드를 넣지 않는다.

6. `stm32f4xx_hal_conf.h`에서 `HAL_TIM_MODULE_ENABLED`를 활성화하고, 같은 CubeF4 1.28.3의 `stm32f4xx_hal_tim.c`, `stm32f4xx_hal_tim_ex.c`를 빌드에 넣는다. RTC/OLED 활성화 시 I²C 모듈·드라이버도 필요하다. IWDG 사용 시 해당 모듈·드라이버도 필요하다.
7. C11 이상으로 컴파일한다. 장치 심볼은 `STM32F429xx`, HAL은 `USE_HAL_DRIVER`, CPU는 Cortex-M4, FPU는 `fpv4-sp-d16`이다.

## 현재 Cube 설정과 맞출 부분

| 항목 | 설정 |
|---|---|
| USART3 | PD8/PD9, 115200, 8N1, TX/RX, NVIC USART3 interrupt ON |
| RNG | Activated, 유효한 48MHz 클록 |
| SYSCLK | 이미 시험한 HSE 8MHz 기반 168MHz PLL 설정 유지 |
| ETH·USB_OTG_FS | 최신 MD대로 Disable |
| TIM4·PD14 | v2 `board.c`가 초기화·구동 |
| TIM1·PE9/11/13/14 | 모터 옵션을 켠 경우 v2 `board.c`가 초기화·구동 |
| I2C1·PB8/PB9 | RTC/OLED 옵션을 켠 경우 v2 `board.c`가 초기화 |
| PF12/PF15 | 문 닫힘·시험 정지 입력 |
| PF13/PF14 | `CONTROL_USE_ENDPOINTS=1`일 때만 끝점 입력 |

HAL 드라이버를 생성시키려고 CubeMX에서 TIM/I²C를 활성화했다면, 해당 `MX_TIM*_Init()`/`MX_I2C1_Init()`의 중복 실행을 정리한다. 이 패키지는 자체 `vc_` 핸들과 설정으로 해당 주변장치를 소유한다. GPIO·USART3·RNG 생성 초기화 후 `sk_app_run()`을 호출하는 흐름을 사용한다.

## 중복 정의 확인

- `HAL_UART_RxCpltCallback`, `HAL_UART_ErrorCallback`, `HAL_UART_TxCpltCallback`의 구현은 v2 `port_stm32.c` 한 곳에 둔다.
- `huart3`, `hrng`의 정의는 Cube 생성 코드에 둔다. v2는 extern으로 참조한다.
- `USART3_IRQHandler()`는 Cube 생성 `stm32f4xx_it.c`에서 `HAL_UART_IRQHandler(&huart3)`를 호출해야 한다.
- `SysTick_Handler()`는 HAL tick이 증가하도록 기존 생성 코드를 사용한다.
- `build_support/main_f429.c`, `build_support/stm32f429zi.ld`와 F7 v1의 main·링커·HAL 설정은 기존 Cube 프로젝트에 추가하지 않는다.

## 첫 통합 시험

1. 동력 전원 없이 새 프로젝트 Build/Run으로 부팅과 `# boot F429 vehicle control v2`, `SYNCREQ`를 확인한다.
2. 기존 server/app/pi_relay로 KEY 등록·정상 허용·변조 01·재전송 02·C 횟수 05·동기화 후 취소 03을 다시 확인한다.
3. 서보 전원과 공통 GND를 준비한 뒤 인증된 `open`을 보낸다. `ACT=OK`와 실제 움직임을 각각 확인한다.
4. `ACT=LINK_STALE`이면 Pi HB 수신을 확인한다. 제어 오류가 유지된 경우 원인을 제거한 뒤 RESET한다. 기본 통합 모드는 네트워크 `CLEAR` 명령을 받지 않는다.
5. 서보 움직임과 `ESTIMATED` 로그를 실제 위치에 대조한다. 이후 모터·센서·RTC·OLED 옵션을 하나씩 켠다.

업로드 시 Run 설정이 새 F429 프로젝트 ELF를 가리키는지 확인한다. CubeIDE 화면의 기존 ▶ 설정이 이전 프로젝트를 가리키는 문제는 최신 MD에서도 주의 항목이었다.
