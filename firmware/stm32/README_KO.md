> **2026-11-02 v0.3.5 반영: 재잠금 + OLED 큰 글자 갱신본**. [적용 안내](docs/RELOCK_1102_KO.md), [작업 보고서](docs/01_gwak_relock_20261102.md)를 먼저 읽으세요. 적용 대상은 **sharekey_f429_OLED**입니다.
> **곽동규는 발표자가 아닙니다.** 마스터에 남은 발표자 표기는 정정 대상입니다.
> RELOCK=1, OLED=1, LARGE_TEXT=1 기본. UNKNOWN 자동 잠금 제외. PC 17개 구성 통과; 이번 수정본의 ARM/CubeIDE 빌드·실물 동작은 미검증. 아래 10/28 기록은 이전 원본의 결과입니다.

# STM32F429ZI 차량 제어 코드 v2

2026-10-28의 `김채희_보드F429전환_Pi실물연결_1028.md`와 `00_master_design.md v0.3.1`을 기준으로 작성한 F429용 제어 통합 패키지다. 기존 팀 인증 코드를 통해 문열기 요청이 허용되면 PD14의 SG90 서보 제어로 연결된다. 끝점 센서 없이 시험하는 기본 모드와 실제 끝점 센서를 사용하는 모드를 모두 제공한다.

**기본 설정은 C 방식, 서보 활성화, 끝점 센서·모터·RTC·OLED 비활성이다.** 실제 ARM 컴파일·링크와 호스트 동작 검사는 통과했다. 실물 서보·배선 및 김채희 노트북의 CubeIDE 프로젝트 적용 시험은 남아 있다. 상세 결과는 [검증 기록](docs/VALIDATION_KO.md)에 있다.

## 먼저 사용할 경로

### 1. 서보만 먼저 시험

`examples/servo_test_f429/README_KO.md`를 따라 별도 `servo_test_f429` 프로젝트에 4개 파일을 넣는다. 전원을 준비한 뒤 B1 USER 버튼을 눌렀다 놓으면 1200↔1800µs 왕복이 시작되고, 다시 누르면 정지한다. 부팅 때는 자동으로 움직이지 않는다.

### 2. 기존 인증 프로젝트에 통합

정상 동작한 **F429용 `sharekey_f429`**를 복사한 뒤 적용한다. 아래 도구가 새 복사본을 만들고 소스와 HAL 드라이버 의존성을 넣어 준다. 실제 경로에 맞게 세 인자를 바꾼다.

```powershell
python tools/prepare_cubeide_copy.py --project "C:\work\sharekey_f429" --cube-f4-root "C:\Users\USER\STM32Cube\Repository\STM32Cube_FW_F4_V1.28.3" --output "C:\work\sharekey_f429_control_v2"
```

CubeIDE에서 `File → Import → Existing Projects into Workspace`로 새 폴더를 가져온다. `Clean → Build` 후 **새 프로젝트의 ELF를 선택한 Run 설정**으로 다운로드한다. 기존 main.c의 `sk_app_run()` 호출은 그대로 사용할 수 있다. 이 패키지의 `vehicle_app.c`가 인증·통신·제어를 함께 처리한다.

자동 복사 도구는 표준 F429 링커와 프로젝트 내부 경로 구성을 지원한다. 외부 연결 파일이나 사용자 정의 RAM 분할이 있으면 수동 검토를 요구한다.

도구를 사용하지 않는 경우와 중복 정의를 확인하는 방법은 [CubeIDE 적용 안내](docs/INTEGRATE_CUBEIDE_KO.md)를 따른다. `build_support`와 `tests`는 기존 CubeIDE의 `Core/Src`에 복사하지 않는다.

## 기본 설정

설정 파일은 `Core/Inc/config.h`다. 프로젝트 compiler define으로도 변경할 수 있다.

| 설정 | 기본값 | 의미 |
|---|---:|---|
| `APP_POLICY_MODE` | `'C'` | A/C 비교. A 시험 때 `'A'`로 빌드하고 끝나면 C로 복구 |
| `VC_ENABLE_SERVO` | 1 | PD14 서보 제어 |
| `CONTROL_USE_ENDPOINTS` | 0 | 센서 없이 500ms 후 위치를 추정. 1이면 PF13/PF14 끝점 검사 |
| `VC_ENABLE_MOTORS` | 0 | MDD3A 연결·문 상태·잠금 조건을 준비한 뒤 1 |
| `MOTOR_START_PERMILLE` | 300 | 시동 허용 시 임시 목표 출력 30%, 상한 60% |
| `VC_ENABLE_RTC` | 0 | DS3231 드라이버 활성화. A/C 판단에는 연결하지 않음 |
| `VC_ENABLE_OLED` | 0 | SSD1306 128×64 표시 활성화 |
| `VC_ENABLE_RETURN_BUTTON` | 0 | PG14 눌림 감지와 로컬 콜백. 반납 대상 KID 선택은 별도 |
| `VC_ENABLE_IWDG` | 0 | 선택적 watchdog. F4 형식의 초기화 제공 |
| `TEST_BUILD` | 0 | 1일 때만 로컬 `TEST ...` 시험 명령 허용 |
| `VC_DOOR_ACTIVE_LOW` | 1 | 문 닫힘 입력의 전기적 극성. 실제 Grove 모듈 출력과 대조 |

서보 잠금/해제 펄스는 1200/1800µs, 센서 없는 이동 시간은 500ms의 임시값이다. 실물 위치·부하를 보정해야 한다. 센서 없는 모드의 `ESTIMATED`는 모터가 실제 도착했음을 측정했다는 뜻이 아니다.

## 통합 후 실행

서버·앱·`pi_relay.py`는 기존 팀 파일을 사용한다. Pi에서 다음과 같이 중계한다.

```bash
python3 pi_relay.py --serial /dev/ttyACM0 --server <노트북IP>:9000
```

앱 실행에는 기존과 같이 `--vehicle <PiIP>:9100`을 지정한다. `pi_relay.py`가 보내는 250ms 간격 `RID|HB`를 받은 뒤 인증된 `open` 요청이 들어오면 서보를 해제 방향으로 움직인다. HB가 아직 없으면 정책 허용 결과는 유지되지만 물리 구동은 `LINK_STALE`로 거부한다. 실행 실패에도 사용 횟수는 환불하지 않는다.

인증 허용 응답 `RES|...|A|00|...`은 기존 의미를 유지한다. 구동 수락은 `# AUTH ALLOW ... ACT=OK`, 끝점 없는 이동 완료는 `# ACT DONE ... SOURCE=ESTIMATED`로 별도 표시한다. 오류는 `# CONTROL FAULT=...`에서 확인한다. 아래는 실제 보드 캡처가 아닌 로그 형식 예시다.

```text
# AUTH ALLOW CMD=01 LEFT=3 ACT=OK
# ACT DONE POSITION=UNLOCKED SOURCE=ESTIMATED
```

잠금 명령은 기존 팀 공식 메시지에 없으므로 새로운 네트워크 명령을 추가하지 않았다. `vehicle_app_request_lock()` 로컬 API와 `TEST_BUILD=1`의 `TEST LOCK`을 제공한다. 모터 시험에서는 먼저 문 닫힘 입력과 잠금 상태를 준비해야 한다. 부팅 직후 추정 잠금 상태는 UNKNOWN이다.

## 코드 구성

| 위치 | 역할 |
|---|---|
| `Core/Src/board.c`, `pwm_clock.c` | F4 GPIO·PWM·I²C, 실제 APB/TIMPRE 클록에 따른 분주 계산 |
| `Core/Src/control.c` | 끝점 on/off, 서보·모터 인터록, HB 오류 유지 |
| `Core/Src/vehicle_app.c` | 인증 허용→구동 연결, 공식 HB, 단일 메인 루프, 비차단 LED 표시 |
| `Core/Src/port_stm32.c` | 기존 Cube UART/RNG 핸들 사용, 단일 UART 콜백, 수신·송신 링버퍼 |
| `Core/Src/line_reader.c` | 512자 줄 조립, 과다 길이·중간 CR·데이터 손실 뒤 접미사 폐기 |
| `Core/Src/sharekey.c`, `sk_crypto.c` | 기존 팀 인증·판단 코드. 대응 헤더와 함께 원본 바이트 유지 |
| `Core/Src/rtc.c`, `oled.c` | 선택적 주변장치 드라이버 |
| `examples/servo_test_f429` | 인증 프로젝트와 분리된 서보 왕복 시험 |
| `tools` | 프로젝트 복사 적용, 호스트 시험, ARM 빌드 검사, 시험 콘솔 |
| `build_support` | F429 교차 빌드 검증용 main·링커·HAL 설정. Cube 프로젝트용 대체 파일이 아님 |
| `docs/WORKLOG_20261028.md` | 변경 내용, 팀 기준과의 관계, 남은 실물 작업 |

## 아직 완료되지 않은 범위

- 물리 서보·모터·스위치·RTC·OLED 시험 및 사용자 CubeIDE 프로젝트 최종 빌드.
- 내부 Flash 저장·재부팅 후 횟수 복원. 기존 인증 코드는 RAM 상태를 사용한다. 원본의 FRAM TODO 주석은 구형 표현이며 최신 계획은 내부 Flash다.
- B/D 기간 정책과 RTC 신뢰·시계 되돌림 방어 연결. 이 배포본은 A/C만 빌드할 수 있도록 제한했다.
- PG14 버튼으로 반납할 KID 선택 규칙. 기본 콜백은 눌림만 기록하며 어떤 키도 임의로 무효화하지 않는다. 인증된 앱 `return` 명령은 기존대로 동작한다.

실제 보드 설정·전원·펄스 보정은 [배선과 시험 순서](docs/WIRING_AND_TEST_KO.md)를 따른다.
