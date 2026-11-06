# F429ZI 서보 단독 시험

2026-10-28 작업 MD의 다음 단계인 `servo_test_f429`용 모듈이다. PD14(D10)의 TIM4 채널 3으로 50Hz PWM을 내보내며, 시험을 시작하면 1200µs와 1800µs를 2초마다 번갈아 출력한다. 부팅 직후에는 출력이 0이고 서보를 자동으로 움직이지 않는다.

## 새 CubeIDE 프로젝트에 넣는 순서

1. CubeIDE 1.19.0에서 **NUCLEO-F429ZI** 프로젝트 `servo_test_f429`를 만든다. STM32CubeF4 1.28.3을 사용한다. 정상 동작한 `sharekey_f429` 프로젝트는 그대로 둔다.
2. F429용 Cube 생성 startup, linker, `SystemClock_Config()`, `SysTick_Handler()`를 사용한다. HSE 8MHz 기반 SYSCLK 168MHz 설정을 사용할 수 있다. 이 모듈은 시스템 클록을 바꾸지 않고 실제 HCLK/PCLK1/TIMPRE를 읽어 서보 분주값을 계산한다.
3. 아래 파일 4개만 복사한다.

   | 배포 파일 | Cube 프로젝트 위치 |
   |---|---|
   | `examples/servo_test_f429/servo_test.c` | `Core/Src/servo_test.c` |
   | `examples/servo_test_f429/servo_test.h` | `Core/Inc/servo_test.h` |
   | `Core/Src/pwm_clock.c` | `Core/Src/pwm_clock.c` |
   | `Core/Inc/pwm_clock.h` | `Core/Inc/pwm_clock.h` |

4. `stm32f4xx_hal_conf.h`에서 `HAL_TIM_MODULE_ENABLED`가 활성화되어 있고, F4 HAL의 `stm32f4xx_hal_tim.c`, `stm32f4xx_hal_tim_ex.c`가 빌드되는지 확인한다. CubeMX에서 TIM4 채널 3을 PWM으로 선택하면 TIM 의존성을 포함시킬 수 있다. 그 경우 생성된 `MX_TIM4_Init()`은 호출하지 않는다. 이 모듈이 TIM4와 PD14를 초기화한다.
5. `main.c`의 `USER CODE BEGIN Includes` 구간에 `#include "servo_test.h"`를 추가한다.
6. Cube 생성 초기화 호출들이 끝난 `USER CODE BEGIN 2` 구간에 다음을 넣는다.

   ```c
   if (!servo_test_init()) {
       Error_Handler();
   }
   ```

7. 기존 `while (1)`의 사용자 구간에서 다음을 반복 호출한다.

   ```c
   servo_test_process();
   ```

통합 패키지의 `board.c`, `control.c`, `port_stm32.c`, 인증 코드는 이 단독 시험에 넣지 않는다. `servo_test.c`와 `board.c`는 모두 TIM4를 사용하므로 같은 프로그램에서 실행하지 않는다. 모듈은 자체 `main`, UART 콜백, IRQ 핸들러를 정의하지 않는다.

## 배선과 실행

| SG90 선 | 연결 |
|---|---|
| 주황 또는 노랑 신호선 | F429ZI **PD14 / D10 / CN7 16번** |
| 빨강 전원선 | 서보 정격에 맞춘 외부 전원 + |
| 갈색 또는 검정 접지선 | 외부 전원 - |
| 공통 접지 | 외부 전원 -와 Nucleo GND 연결 |

최신 MD대로 전원 준비 전에는 소스 생성·빌드·업로드까지만 진행한다. 6개 AA를 넣은 9V 전원은 서보에 직접 연결하지 않는다. 4개 AA를 쓸 때도 실제 서보 정격과 공급 전압을 확인한다. 서보 동력 전원은 Nucleo 5V에서 공급하지 않는다.

보드의 기본 **B1 USER 버튼(PC13)을 한 번 누르고 놓으면** 왕복 시험이 시작된다. 다시 누르고 놓으면 PWM이 0으로 바뀐다. 부팅 때 버튼을 누르고 있어도 그 상태만으로 시작하지 않으며, 놓은 뒤 다시 눌렀다 놓아야 시작한다. 기본 MB1137의 PC13 버튼 배선을 전제로 하므로 점퍼를 PA0로 바꾼 보드는 버튼 입력을 맞춰야 한다.

프로그램에서 직접 제어하려면 `servo_test_start()`와 `servo_test_stop()`을 호출할 수 있다. `servo_test_running()`과 `servo_test_pulse_us()`로 시험 상태를 읽는다. `servo_test_start()`를 초기화 직후 자동 호출하면 전원 인가 후 자동 동작하게 되므로, 기본 예제는 USER 버튼을 기다린다.

처음에는 걸쇠를 분리한 상태에서 1200↔1800µs 동작과 외부 전원을 확인한다. 두 값은 확정 각도가 아니라 현재 설계의 임시 펄스값이다. 실제 잠금·해제 방향과 위치를 확인한 뒤 보정한다. PWM을 끄면 서보의 위치 유지 토크가 사라질 수 있다.

## 계산과 확인 범위

- TIM4 입력이 84MHz이면 PSC=83, ARR=19999로 설정된다. TIMPRE 때문에 168MHz이면 PSC=167이 된다. 1µs 카운터와 50Hz가 정확히 만들어지지 않는 클록은 초기화 실패로 처리한다.
- 전체 F429 펌웨어 빌드 결과는 패키지의 검증 문서를 따른다. 이 설명 자체는 실물 서보 왕복 성공 기록이 아니다.
- 버튼 배선과 서보 핀: ST UM1974의 MB1137 버튼·F429ZI 핀표를 기준으로 했다. [UM1974](https://www.st.com/resource/en/user_manual/dm00244518-stm32-nucleo-144-boards-mb1137-stmicroelectronics.pdf)
