# F429 v2 검증 범위와 결과

검증일은 2026-10-28이다. 호스트에서의 실제 C 코드 실행과 STM32F429ZI 대상 ARM 컴파일·링크를 수행했다. 실물에서 서보가 움직였다고 기록하지 않는다.

## 호스트 실행 검사

`python tools/run_host_tests.py`는 GCC/Clang C11에서 실행한다. 애플리케이션 소스는 `-Wall -Wextra -Werror`로 검사한다.

| 검사 | 내용 |
|---|---|
| control_no_endpoints | 부팅 UNKNOWN, 실제 HB 필요, 시간 기반 추정, 정지 후 추정 무효화 |
| control_endpoints | 끝점 디바운스·모순·타임아웃, deadline 경계, 모터 인터록 |
| pwm_clock | APB 분주1/2/4/8/16, TIMPRE0/1, 16/84/168MHz, 50Hz·10kHz·듀티 계산 |
| line_reader | CRLF, 512자 경계, 긴 줄·중간 CR·바이너리·손실 뒤 접미사 폐기 |
| auth_vectors | 팀 인증 정답표 11개 |
| app_c / app_a | 실제 인증 소스+앱+제어 연결, 공식 KEY/RESP 길이, A/C 정책, HB 연결 |
| app_c_motor | 물리 조건 거부 후에도 횟수 유지, 잠금 뒤 모터 시작, 문 열림 정지 |

세부 동작에는 C의4회 허용 뒤05 거부, 변조01, nonce재사용02, 인증된 동기화 복구·취소03, 같은 KEY 재등록으로 횟수 리셋 금지, 취소 상태 복구 금지, TEST_BUILD=0 시험 명령 거부가 포함된다. 상세 stdout은 `HOST_TEST_RESULTS.json`에 있다.

UART 인터럽트·실제 신호 타이밍·전원·전류·기계 부하는 호스트 검사 대상이 아니다. 단일 producer/ISR consumer 송신 큐와 수신 오류 처리는 코드 검토를 수행했으며 실제 시리얼 부하 시험은 남아 있다.

## ARM 컴파일과 링크

- 공식 Arm GNU Toolchain 14.2.Rel1, GCC14.2.1.
- STM32CubeF4 1.28.3의 고정 HAL/CMSIS 의존성.
- Cortex-M4, Thumb, fpv4-sp-d16, hard-float.
- 검증용 F429 main·startup·링커와 실제 배포 소스를 컴파일·링크.
- 기본 C, A, 모든 선택 기능, 독립 서보 시험 변형을 검사.
- 모든 변형의 초기 스택 벡터 `0x20030000` 확인.

최종 결과·경고 수·메모리 사용량·소스와 ELF 해시는 `build_support/ARM_BUILD_RESULTS.json`을 따른다. 이 JSON과 일치하는 소스만 최종 ZIP에 포함한다.

## CubeIDE 복사 도구

`tests/test_installer.py`는 표준 F429 fixture에 적용되는지, F7 혼합 타깃·잘못된 링커·기존 출력 폴더를 거부하는지 확인한다. 실제 사용자의 `.cproject`나 CubeIDE UI를 실행한 결과는 아니다.

## 실물에서 확인할 항목

1. 실제 `sharekey_f429` 복사본의 Clean/Build, IRQ와 HAL tick, 정상 부팅.
2. Pi↔STM32의 줄 손상·과부하·끊김 및 기존 A/C 시연 결과 재확인.
3. 서보50Hz, 실제1200/1800µs, 전원과 방향·걸쇠 도착 위치.
4. 센서 on/off 각각의 완료·오류, 문 열림·정지·통신 끊김 반응.
5. 모터·OLED·RTC의 실제 하드웨어와 옵션 설정 일치.

내부 Flash 저장과 B/D 시간 정책은 이번 배포의 구현·검증 범위가 아니다. 인증 원본은 RAM 상태를 사용하며 보드 RESET 후 상태가 유지되지 않는다.
