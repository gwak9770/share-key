# MDD3A·OLED·RTC·SG90 독립 시험판 — NUCLEO-F429ZI

판 ID `oled-rtc-servo-bench-20261127-v3` · 작업일 2026-11-27 · 프로젝트 `MDD3A_Motor_Test`.
반입 기반 `30c031a`(00 v0.3.26) · 원본 Git 커밋·작성·시험·업로드 시각 미상.

## 용도와 출처

사용자가 실물 시험에 사용했다고 보고한 독립 프로젝트를 반입했다. 부팅 중 RTC·OLED·SG90을 시험하고 이후 USER 버튼으로 DC모터를 시험한다. 통합 디지털키 펌웨어는 별도 `Core/`에 있다.

**부팅 단계에서 SG90이 자동으로 움직인다. 문이나 서보 링크를 조립할 때는 서보 전원을 분리한다.**

[11/27 반입 목록](IMPORT_MANIFEST_20261127.json)에 원본 111개 파일의 SHA-256, 줄바꿈을 LF로 통일한 SHA-256, 반입 시각 및 ELF 검증 결과를 기록했다. 변경 6개와 추가 1개를 원본 바이트 그대로 복사했고, 111개 모두 줄바꿈을 통일한 원본·사본이 일치했다. ELF·BIN·백업·Debug·워크스페이스·launch·.settings는 반입 대상에서 제외했다.

기존 예제의 소스·설정·링커·라이선스 구조를 유지했다. 이전 판의 소스와 검증은 각 Git 트리와 반입 목록에서 확인할 수 있다. [11/26 소스·빌드 기록](https://github.com/gwak9770/share-key/tree/e5503bd234d9ea800ff7d573ff3f12a5448b5408/firmware/stm32/examples/mdd3a_motor_test_f429) · [11/26 반입 목록](IMPORT_MANIFEST_20261126.json) · [11/19 반입 목록](IMPORT_MANIFEST.json)

## 실제 코드와 설정

- PE9/11/13/14 출력, 초기 LOW, PC13 USER 입력(HIGH=누름).
- M1(PE9)→M2(PE13)→둘 동시, 반대 입력 PE11/PE14는 LOW.
- HAL 틱 기준 약 100Hz·60% 소프트웨어 펄스 폭 변조(PWM). `elapsed % 10U < 6U`를 1ms마다 확인한다. 11/27 원본 주석도 60%로 갱신됐다. 누름 해제 또는 약 500ms 후 LOW, 다시 놓았다 눌러야 다음 단계.
- 30ms 버튼 안정화 대기. 조기 해제해도 다음 단계로 넘어간다. 파형·정확한 시간은 미계측.
- I²C1 PB8(SCL)/PB9(SDA), 100kHz, 7비트, 오픈드레인(AF4), 내부 풀업·풀다운 없음. DS3231 주소 0x68에서 초·상태 레지스터를 읽는다. 부팅 시 OSF(발진기 정지 플래그)는 읽기만 한다. `RTC_SET_TIME=0`을 유지해 날짜·시간 쓰기 블록을 빌드에서 제외한다.
- JMD2.42IIC SSD1309 OLED는 PD15(D9)에서 LOW 20ms·HIGH 100ms 리셋 시퀀스를 거쳐 0x3C→0x3D 주소를 탐색한다. 실물 응답 주소는 미기록이다. 128×64 화면에 `KEY OK`/`KEY NG` 문자를 약 2초 간격으로 각 3회 표시한다.
- SG90 PD14(D10)/TIM4 CH3를 50Hz로 설정한다. 5초 대기 뒤 1500µs에서 시작해 1000µs와 1500µs를 2회 오가고 PWM을 정지한다. OLED가 응답했으면 `RTC_ShowTime()`을 한 번 호출한다.
- PF12 택트 스위치는 차체에 배선했으며 이 시험판에 GPIO 설정은 없다. PF15는 미사용이다.
- IOC: CubeMX 6.19.0, STM32Cube FW_F4 V1.28.3. HAL 소스 버전 V1.8.5.
- 확보한 환경에 CubeIDE 2.3.0이 설치되어 있다. 팀 표준은 1.19.0이며 2.x를 금지한다. 1.19.0 호환 빌드는 미수행이다.
- HSE bypass 8MHz, PLLM=4/N=168/P=2/Q=7, 목표 SYSCLK 168MHz.
- 이 예제에는 ETH·USART3·USB_OTG_FS 초기화도 포함된다. 독립 시험판의 모터 제어는 GPIO 소프트웨어 PWM이며, 00 §8의 통합 모터 출력은 TIM1 10kHz다. RTC 핀 위치는 00 §8과 일치한다.
- 시험판 FLASH 링커는 2048K이며 통합판은 저장 영역을 위해 1792K를 사용한다. 통합 보드에 다시 적용할 때 저장 데이터 보존·복원 및 플래시 지우기 범위를 확인한다.

## 재빌드

### CubeIDE

원본 외부 폴더 대신 이 예제를 별도 작업 사본으로 가져온다. `File → Import → General → Existing Projects into Workspace`에서 이 폴더를 선택한다. 프로젝트 이름은 원본과 같은 `MDD3A_Motor_Test`이므로 다른 워크스페이스를 사용해 원본과 혼동하지 않는다. `.cproject`는 상대 include 경로와 workspace 기반 FLASH 링커 경로를 사용한다. `Debug` 설정으로 빌드한다. 이번 반입에서는 CubeIDE GUI 빌드·재생성·1.19.0 호환성을 확인하지 않았다. IOC 재생성은 실제 시험 코드를 바꿀 수 있으므로 별도 사본에서 diff를 검토해야 한다.

### 명령줄 ARM 검사

Python 3와 Arm GNU C 컴파일러가 필요하다. 저장소 루트에서:

```powershell
python firmware/stm32/examples/mdd3a_motor_test_f429/build.py --cc "<실제 arm-none-eabi-gcc.exe 경로>"
```

`build.py`는 11/19에 추가한 명령줄 빌드 도구다. C 28개와 시작 어셈블리 1개를 Cortex-M4, 하드웨어 부동소수점 호출 규약, DEBUG/USE_HAL_DRIVER/STM32F429xx, O0, nano/nosys 설정으로 재빌드한다. 컴파일 대상 29개를 원본 `Debug/objects.list`와 대조했다. 명령줄 도구는 원본 Debug의 추가 플래그와 링크 순서를 재현하지 않는다.

산출물은 기존 `.gitignore`의 `build-*` 규칙으로 제외되는 `build-motor/`에만 만든다. 원본 프로젝트를 수정하지 않으며 업로드·자동 지우기를 하지 않는다. 실행 명령·도구 버전·실제 빌드 시각·ELF 해시는 `build-motor/build_result.json`에 남긴다.

| 재빌드 확인(2026-11-28, Asia/Seoul) | 결과 |
|---|---|
| `build.py`, GNU Tools for STM32 14.3.rel1 / GCC 14.3.1 | 29개 단위 컴파일·링크 PASS(1회), 오류·경고 출력 0. |
| 원본 Debug 주요 컴파일 플래그와 `objects.list` 순서로 별도 명령줄 재빌드 | 29개 단위 컴파일·링크 PASS(1회). 원본 로컬 ELF와 재빌드 ELF의 로드 세그먼트 3개가 주소·크기·내용까지 일치했다. ELF 전체 해시는 서로 다르며 반입 목록에 기록했다. |

별도 검사에는 원본 Debug의 C 옵션 `-fstack-usage -fcyclomatic-complexity -ftls-model=local-exec`와 시작 어셈블리 옵션 `-x assembler-with-cpp`를 적용했다. 원본 목록 순서인 HAL → Src → Startup으로 링크한 뒤 ELF의 `PT_LOAD` 항목에서 주소·크기·파일에 기록된 바이트를 비교했다.

11/27 CubeIDE 빌드(0 Errors, 0 Warnings)와 업로드는 사용자 보고다. 기록 작업의 CubeIDE 그래픽 화면 빌드, 보드 재업로드·읽기, 실물 재시험은 미수행이다. 실제 보드 적용판은 업로드 로그 또는 보드 대조가 필요하다.

## 실물 결과와 배선

11/27 사용자 보고에서 RTC와 스톱워치가 각각 41초 경과(전원 차단부터 재연결·화면 확인까지 포함, 1회)했고, 서보 전용 전원으로 SG90 회전·복귀 2/2를 확인했다. 최종 공용 전원 구동과 PF12 입력은 미검증이다. [11/27 작업 일지·배선표](../../../../docs/history/2026-11-27_oled_rtc_servo_wiring/work_log.md) · [11/26 작업 일지](../../../../docs/history/2026-11-26_motor_rtc_bench/work_log.md) · [11/19 작업 일지](../../../../docs/history/2026-11-19_motor_bench/work_log.md)
