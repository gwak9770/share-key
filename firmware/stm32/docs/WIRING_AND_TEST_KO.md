# F429 배선과 시험 순서

## 핀

| 기능 | MCU 핀 | Nucleo 위치 또는 주변장치 |
|---|---|---|
| Pi 통신 | PD8 TX / PD9 RX | CN1 ST-LINK USB, USART3 |
| 서보 신호 | PD14 | D10, CN7 16번, TIM4 CH3 |
| 모터 M1A / M1B | PE9 / PE11 | D6 / D5, TIM1 CH1 / CH2 |
| 모터 M2A / M2B | PE13 / PE14 | D3 / D38, TIM1 CH3 / CH4 |
| 문 닫힘 | PF12 | D8 |
| 잠금 / 해제 끝점 | PF13 / PF14 | D7 / D4, 기본 비활성 |
| 시험 정지 | PF15 | D2, GND에 연결되면 정지 |
| 반납 버튼 | PG14 | D1, 선택 기능 |
| I2C | PB8 / PB9 | D15 SCL / D14 SDA |
| 허용 / 온라인 / 거부 LED | PB0 / PB7 / PB14 | LD1 / LD2 / LD3 |

서보 신호는 PD14이며 PA6 또는 PC7을 사용하던 구형 후보 핀표와 혼합하지 않는다. 핀·커넥터 대조 근거는 [ST UM1974](https://www.st.com/resource/en/user_manual/dm00244518-stm32-nucleo-144-boards-mb1137-stmicroelectronics.pdf)와 [F429 데이터시트](https://www.st.com/resource/en/datasheet/stm32f429ie.pdf)다.

## 전원

서보 빨강은 정격에 맞춘 외부 전원 +, 갈색/검정은 외부 전원 -, 주황/노랑은 PD14다. **외부 전원 -와 Nucleo GND를 공통으로 연결한다.** 서보 동력 전원은 Nucleo 5V에서 공급하지 않는다.

최신 MD의 6구 홀더에 AA 6개를 넣은 9V 구성은 사용하지 않는다. 4구 AA 홀더를 쓰더라도 실제 서보의 정격과 전압을 확인한다. [TowerPro SG90 안내](https://towerpro.com.tw/product/sg90-7/)의 사양 표는 4.8V, 제조사 답변은 4.8~6V 범위를 제시하지만 실물 제품의 정격을 확인해야 한다. 전원 준비 전에는 빌드·통신 시험까지 진행한다.

MDD3A에는 모터 전원과 논리 입력을 구분해 연결한다. MCU 초기 리셋 구간에도 출력 입력이 뜨지 않게 외부 풀다운을 적용한다. 모터 2개 병렬 여부·전류·배선은 팀의 실제 부품 기준을 따른다. 코드가 출력 상한 60%를 제한해도 모터 구속 전류를 측정한 것은 아니다.

## 센서 없는 기본 모드

`CONTROL_USE_ENDPOINTS=0`에서는 PF13/PF14를 잠금 확인에 사용하지 않는다. 부팅 위치는 UNKNOWN이고, 1200µs 잠금 명령 또는 1800µs 해제 명령을 500ms 동안 유지한 뒤 위치를 ESTIMATED로 표시한다. 정지·오류로 PWM을 끄면 추정 위치를 무효화한다. 모터는 문 닫힘과 잠금 추정 또는 센서 확인이 필요하다.

Grove 문 센서는 모듈마다 출력 극성과 배선이 다를 수 있다. 기본 PF12는 active-low, 내부 pull-up이다. 실제 문 닫힘 신호가 high인 모듈이면 `VC_DOOR_ACTIVE_LOW=0`으로 바꾸며 이때 입력 pull-down을 사용한다. 설정 변경 전 실제 출력 전압이 MCU 입력 조건에 맞는지 확인한다.

## 단계별 실행

1. `servo_test_f429`에서 독립 왕복 시험. 처음에는 걸쇠 부하를 분리하고 방향·전원·펄스를 확인한다.
2. `sharekey_f429_control_v2` 기본 C 모드에서 Pi HB와 인증 open → 서보 해제를 확인한다.
3. 필요하면 끝점 센서를 설치한 뒤 `CONTROL_USE_ENDPOINTS=1`로 빌드한다. 두 끝점 동시 입력과 1.5초 미도달 시 오류가 유지되는지 확인한다.
4. 모터 시험에서는 바퀴를 띄우고 문 닫힘 입력 및 잠금 상태를 준비한다. `VC_ENABLE_MOTORS=1`로 빌드한 뒤 시동 승인과 인터록을 확인한다.
5. RTC/OLED를 연결하고 각각의 옵션을 켠다. 기본 펌웨어의 A/C 정책은 RTC 시간이 필요하지 않다.

## 로컬 부품 시험 명령

`TEST_BUILD=1` 전용이다. 일반 통합 빌드의 `TEST_BUILD=0`에서는 아래 명령으로 구동할 수 없다. Pi 중계와 시험 콘솔이 같은 시리얼 포트를 동시에 열지 않도록 한다.

```powershell
python -m pip install pyserial
python tools/bench_console.py --port COM4
```

Pi에서는 `--port /dev/ttyACM0`을 사용한다. 콘솔이 250ms마다 HB를 전송한다.

| 입력 | 동작 |
|---|---|
| `STATUS` | 상태 조회 |
| `LOCK` / `UNLOCK` | 서보 잠금 / 해제 |
| `MOTOR 300` / `MOTOR 0` | 모터 목표 30% / 모터 정지 |
| `STOP` | 모든 출력 중지, arming 및 추정 위치 해제 |
| `CLEAR` | 원인 제거 후 오류 해제. 자동으로 arm하거나 움직이지 않음 |
| `QUIT` | STOP 전송 후 콘솔 종료 |

모터 시험의 한 예는 `LOCK` → 500ms 이상 대기 → `MOTOR 300` → `MOTOR 0` → `UNLOCK`이다. 문 닫힘 입력이 없으면 LOCK과 MOTOR가 거부될 수 있다. 부품 시험이 끝나면 `TEST_BUILD=0`으로 다시 빌드한다.
