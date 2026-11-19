# MDD3A 독립 모터 시험판 — NUCLEO-F429ZI

판 ID: `motor-bench-20261119-v1` · 작업일 2026-11-19 · 사용자 제공 프로젝트 원본: `C:/STM32/MDD3A_Motor_Test`.
반입 기반: `e957bd95c443cfdab6124c0df2d69fdaf05c664e` · 시험 코드의 원본 Git Commit·작성·업로드 시각: 미상.

## 용도와 출처

이 폴더는 실제 사용했다고 보고된 별도 프로젝트의 현재 파일을 그대로 반입한 것이다. 팀 디지털키 `Core/`와 판단 코드를 공유하거나 복제하지 않는다. 인증·키·문·서보·HB 인터록 없이 USER 버튼으로 모터만 시험하므로 실제 차량·통합 디지털키 펌웨어로 사용하지 않는다.

[IMPORT_MANIFEST.json](IMPORT_MANIFEST.json)에 원본 파일 105개의 바이트 SHA-256, 반입 시각, 기존 Debug ELF의 해시만 기록했다. 원본·사본 바이트 일치를 확인했다. ELF·BIN·백업·Debug·워크스페이스·launch·.settings는 복사하지 않았다. 현재 파일의 존재·기존 ELF 해시만으로 실제 업로드판을 확정하지 않는다. M2 전용 과거 시험판은 확보하지 못했다.

원본의 `Src/`, `Inc/`, `Startup/`, `Drivers/` 구조를 유지했다. 버전·날짜는 본 문서와 매니페스트로 관리하며 원본 소스에 주석을 추가하지 않았다. `.project`, `.cproject`, `.mxproject`, `.ioc`, FLASH/RAM 링커는 사용자 명시 요청에 따라 보존한다. 원본 드라이버 라이선스와 저작권 헤더도 유지했다.

## 실제 코드와 설정

- PE9/11/13/14 출력, 초기 LOW, PC13 USER 입력(HIGH=누름).
- M1(PE9)→M2(PE13)→둘 동시, 반대 입력 PE11/PE14는 LOW.
- HAL 틱 기준 약 100Hz·40% 소프트웨어 PWM. 누름 해제 또는 약 500ms 후 LOW, 다시 놓았다 눌러야 다음 단계.
- 30ms 버튼 안정화 대기. 조기 해제해도 다음 단계로 넘어간다. 파형·정확한 시간은 미계측.
- IOC: CubeMX 6.19.0, STM32Cube FW_F4 V1.28.3. HAL 소스 버전 V1.8.5.
- 원본 설치 제품 정보: CubeIDE 2.3.0. 팀 표준 1.19.0·2.x 금지와 차이가 있다.
- HSE bypass 8MHz, PLLM=4/N=168/P=2/Q=7, 목표 SYSCLK 168MHz.
- ETH·USART3·USB_OTG_FS 초기화가 남아 있다. 모터 시험에 필요한 최소 구성이라고 주장하지 않는다.
- FLASH 링커 길이는 2048K로 팀 저장 영역용 1792K와 다르다. 이 링커·프로젝트 설정을 통합 디지털키에 복사하지 않는다. 통합 저장 데이터 보존·복귀 절차는 별도 확인이 필요하다.

## 재빌드

### CubeIDE

원본 외부 폴더 대신 이 예제를 별도 작업 사본으로 가져온다. `File → Import → General → Existing Projects into Workspace`에서 이 폴더를 선택한다. 프로젝트 이름은 원본과 같은 `MDD3A_Motor_Test`이므로 다른 워크스페이스를 사용해 원본과 혼동하지 않는다. `.cproject`는 상대 include 경로와 workspace 기반 FLASH 링커 경로를 사용한다. `Debug` 설정으로 빌드한다. 이번 반입에서는 CubeIDE GUI 빌드·재생성·1.19.0 호환성을 확인하지 않았다. IOC 재생성은 실제 시험 코드를 바꿀 수 있으므로 별도 사본에서 diff를 검토해야 한다.

### 명령줄 ARM 검사

Python 3와 Arm GNU C 컴파일러가 필요하다. 저장소 루트에서:

```powershell
python firmware/stm32/examples/mdd3a_motor_test_f429/build.py --cc "<실제 arm-none-eabi-gcc.exe 경로>"
```

`build.py`는 이번 기록 작업에서 새로 만든 빌드 도구다. 원본의 C 26개와 startup assembly 1개를 `Debug`의 Cortex-M4/FPU hard ABI, DEBUG/USE_HAL_DRIVER/STM32F429xx, O0·nano/nosys 설정으로 재빌드한다. IDE의 디버그 부가 옵션·디버그 경로까지 동일한 비트 재현 빌드는 아니다. 원본 Debug makefile의 소스 목록과 일치한다.

산출물은 기존 `.gitignore`의 `build-*` 규칙으로 제외되는 `build-motor/`에만 만든다. 원본 프로젝트를 수정하지 않으며 업로드·자동 지우기를 하지 않는다. 실행 명령·도구 버전·실제 빌드 시각·ELF 해시는 `build-motor/build_result.json`에 남긴다.

이번 검사: GNU Tools for STM32 14.3.rel1 / GCC 14.3.1, 27개 단위 컴파일·링크 PASS(1회), 경고 출력 없음. 원본 프로젝트의 GUI 빌드 성공을 대신 증명하지 않는다. 통합판 호스트 시험·보드 업로드·실물 재시험은 미수행이다.

## 실물 결과와 배선

[작업 일지](../../../../docs/history/2026-11-19_motor_bench/work_log.md), [결과·재시험](../../../../docs/history/2026-11-19_motor_bench/test_results.md), [배선](../../../../docs/history/2026-11-19_motor_bench/wiring.md), [트러블슈팅](../../../../docs/history/2026-11-19_motor_bench/troubleshooting.md).

채널별 2개 구동은 사용자 성공 보고(횟수 미상), 4개 동시 구동은 불안정·미완료다. 모터·전원 정격과 업로드판 식별, 전원 개선 후 재시험이 남았다.
