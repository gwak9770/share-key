# 곽동규 작업 정리 — 1104 R1 수정판 재검토·PC 시험

> 날짜: 2026-11-04
> 기준: 00_master_design.md v0.3.9 및 기존 후보판 검토 보고서
> 검토 대상: stm32_vehicle_control_f429_v2_1103_R1수정_1104.zip
> **역할: 곽동규는 STM32 제어 코드·시험·결과 정리 담당이며, 발표자가 아님. 발표 담당 업무를 곽동규에게 배정한 것으로 해석하지 말 것.**

## 1. 한 일 (요약 3줄 이내)

- 다시 받은 R1 수정판을 검토하고, 이전에 지적한 오래된 HB 처리 문제와 적용 문서 보완 여부를 확인했다.
- Windows MSVC 호스트 시험 19개 구성 통과 및 추가 재현 검사에서 오래된 HB 차단·새 HB 이후 구동을 확인했다.
- 중단 후 남아 있던 결과 파일을 확인하여 재검토 보고서와 증빙 ZIP을 완성했다. 이번 마무리 작업에서는 생산 코드 수정이나 시험 재실행을 하지 않았다.

## 2. 결정한 것

| 항목 | 결정 | 이유 |
|---|---|---|
| 재검토 결론 | 이전 지적 사항은 수정됐으며 기본 설정으로 실물 시험 진행 가능 | 호스트 시험과 동일 조건의 HB 재현 검사 통과 |
| 첫 실물 시험 설정 | VC_DEMO_MODE_SELECT=0 유지 | 등록·문 열기·재잠금 반복을 먼저 확인 |
| A/C 전환 시험 | 기본 동작 확인 후 VC_DEMO_MODE_SELECT=1로 빌드하여 별도 확인 | 실물에서 USER 입력·표시·정책 전환 검증 필요 |
| 보드 적용 | sharekey_f429_OLED 전체 백업 후 지정된 8개 파일 적용 | 부분 복사로 인한 버전 혼합 방지 |
| 검토 범위 | PC 검증과 문서 검토 결과로 한정 | CubeIDE 빌드·업로드·실제 서보 동작은 미확인 |

## 3. 만든 파일 / 바꾼 파일

| 파일 | 생성/수정 | 역할 |
|---|---|---|
| 01_gwak_r1_recheck_20261104.md | 생성 | 본 재검토 보고서 |
| gwak_r1_recheck_20261104.zip | 생성 | 보고서·기존 실행 로그·추가 재현 코드·재검토용 해시 목록 |
| evidence/host/summary.json 및 19개 .log | 기존 결과 복사 | 수정판에서 실행한 호스트 시험 근거 |
| evidence/review/build-review/review_boundaries.log | 기존 결과 복사 | 오래된 HB 차단 및 새 HB 구동 결과 |
| evidence/review/test_review_boundaries.c, run_review.py | 기존 검토 파일 복사 | 수정판 기대 결과에 맞춘 추가 검사 및 실행 도구 |
| evidence/vendor/ARM_BUILD_RESULTS_1104.json | 전달받은 자료 복사 | 작성자 측 ARM 컴파일·링크 결과. 이번 검토의 직접 실행 결과와 구분 |
| evidence/source_hashes.json | 생성 | 확인한 수정판 Core 파일의 SHA-256 및 인증·판단 4개 파일 비교 |
| 후보판 생산 코드 및 원본 ZIP | 수정 없음 | 전달받은 코드 보존 |

보드에 적용할 8개 파일은 다음과 같다. **이 보고서 ZIP은 검토 증빙 묶음이며 보드용 소스 전체 묶음이 아니다. 소스는 전달받은 R1 수정판 ZIP을 사용한다.**

| 적용 위치 | 파일 |
|---|---|
| Core/Inc | config.h, board.h, vehicle_app.h, vehicle_platform.h |
| Core/Src | board.c, port_stm32.c, vehicle_app.c, oled.c |

## 4. 전체 설계와 다른 점 (중요)

이번 검토 작업에서 설계나 생산 코드를 변경하지 않았다. 이전 검토의 지적 사항에 대한 수정판 확인 결과는 다음과 같다.

| 이전 항목 | 수정 내용 및 확인 결과 | 판정 |
|---|---|---|
| R1: 모드 선택 중 받은 오래된 HB가 선택 후 새 신호로 처리됨 | 선택 중 UART 수신 바이트를 버리고, 종료 시 한 번 더 비움. 중간에 잘린 줄은 다음 줄 끝까지 버림. 추가 검사에서 fresh=0, LINK_STALE, moving=0 확인 | 재현 조건에서 해결 확인 |
| R2: 문서에 3~4개 파일만 복사하도록 안내 | KEYOK_1103_KO.md에 Inc 4개·Src 4개 전체 복사 및 백업·Clean Build 절차 반영 | 수정 확인 |
| 계속 누른 USER 버튼의 약 15초 자동 확정 설명 누락 | 제한 시간 후 당시 화면 모드로 확정한다고 문서와 config.h 주석에 명시 | 수정 확인 |

인증·판단 파일인 sharekey.c/h, sk_crypto.c/h는 직전 1103 후보판과 바이트 단위로 동일함을 확인했다. 이번 확인은 이전 재현 조건에서의 수정 효과를 확인한 것이며 모든 UART 타이밍 조건에 대한 무결함 보증은 아니다.

## 5. 테스트 결과

| 시험 | 결과 | 근거·범위 |
|---|---|---|
| Windows MSVC 호스트 시험 | 19/19 통과 | summary.json의 모든 compile=0, run=0 |
| A/C·재잠금·끝점·모터 구성 | 통과 | 각 app 및 control 로그. 가상 I/O 기반 |
| OLED·등록 표시·줄 파서·인증 벡터·PWM 계산 | 통과 | 대응 호스트 로그 |
| 모드 선택 중 오래된 HB | 구동 차단 | age=3930ms, fresh=0, ACT=LINK_STALE, moving=0, servo_us=0 |
| 선택 종료 후 새 HB | 정상 구동 | fresh=1, ACT=OK, moving=1, servo_us=1800 |
| USER 장시간 유지 | 약 15초에 당시 모드 확정 | TIMEOUT 로그. 가상 시각에는 초기화 시간이 포함됨 |
| MSVC 경고 | 38건 기록 | 중복 포함. 시험 통과를 경고 0으로 해석하지 않음 |
| ARM 컴파일·링크 | 작성자 제공 결과 5종 PASS | default/demo/policy-a/all-features/servo. 이번 검토에서는 직접 재실행하지 않음 |
| 채희 노트북 CubeIDE 빌드·보드 업로드 | 미실시 | 실물 담당 단계에서 확인 필요 |
| 실제 OLED·문 스위치·서보 | 미확인 | PC 결과와 분리하여 기록 |

추가 재현 검사 로그 원문:

```text
TIMEOUT: mode=C button_still_held_ms=4800 now=15230
BUFFERED_HB: received_at=100 now=4030 age=3930 fresh=0
BUFFERED_HB_ACT: LINK_STALE moving=0 servo_us=0
NEW_HB_ACT: fresh=1 act=OK moving=1 servo_us=1800
```

기존 19개 구성과 추가 재현 검사는 별도 집계한다. 추가 검사까지 합쳐 임의로 ‘20개 또는 21개 구성’이라고 표기하지 않는다.

추가 재현 검사를 다시 실행하려면 Visual Studio x64 Native Tools 명령 프롬프트에서 압축을 푼 검토 묶음 기준으로 실행한다.

```text
python evidence/review/run_review.py <R1_수정판_폴더_경로>
```

## 6. 막힌 점 / 질문

- 코드 검토 범위에서 이전 수정 요청을 막는 추가 결함은 발견하지 못했다. 보드에서의 동작은 아직 확인하지 않았다.
- 실제 스위치 극성, 서보 해제·잠금 위치, OLED 가독성 및 HB 단절 시 동작을 확인해야 한다.
- 모드 선택 중 들어오는 등록·요청도 폐기되므로 모드 확정 후 키 등록과 요청을 진행해야 한다.
- 키와 횟수는 현재 RAM 기반이므로 RESET 후 키를 다시 등록해야 한다.
- 이 문서에는 실물 시험 성공이나 최종 발표용 판 확정을 기록하지 않았다.

## 7. 다음에 할 일

1. 채희 노트북의 sharekey_f429_OLED 프로젝트를 통째로 백업한다.
2. 전달받은 R1 수정판에서 지정된 8개 파일을 복사한다. 기존 CubeMX 설정을 유지하고 VC_DEMO_MODE_SELECT=0을 확인한 뒤 Clean → Build → 업로드한다.
3. Pi 중계와 HB를 유지하며 키 등록 → OLED KEY OK → 문 열기 → 서보 해제를 확인한다.
4. 문 스위치로 실제 열림→닫힘 변화를 만들고 재잠금을 확인한다. 이어 다시 문 열기를 요청하여 서보가 재구동되는지 확인한다.
5. 부팅 직후 UNKNOWN에서 자동으로 잠기지 않는지, 재잠금 중 문을 열면 기존 안전 동작대로 멈추는지 확인한다.
6. 기본 반복 동작이 성공하면 VC_DEMO_MODE_SELECT=1로 다시 빌드하여 USER+RESET의 A/C 전환을 확인한다. 손을 떼면 확정되며 계속 누르면 약 15초에 당시 모드로 확정된다. 부팅 로그 MODE와 OLED를 함께 확인하고 RESET마다 키를 다시 등록한다.
7. 필요 시 모드 선택 중 HB를 중단한 조건에서 선택 종료 직후 구동이 차단되고, 새 HB 이후 구동되는지 실물 로그로 확인한다.
8. 11월 5일(목) 실물 확인 결과를 팀에 전달하여 적용 여부를 결정한다. 실패하면 팀 안내에 따라 백업한 기존 판으로 복귀한다.

**곽동규의 다음 업무는 코드·시험 결과 정리와 실물 테스트 지원이다. 발표자는 아니며, 발표 수행은 곽동규의 담당 업무에 포함하지 않는다.**

## 8. 참고 (참고한 자료, AI 대화에서 나온 중요한 내용)

- 1103 후보판 검토 보고서: 01_gwak_candidate_review_20261104.md.
- R1 수정판 docs/KEYOK_1103_KO.md, docs/R1_1104.patch, Core/Inc/config.h.
- R1 수정판 build-host/summary.json 및 19개 실행 로그.
- 재검토용 test_review_boundaries.c, run_review.py, compile.log, review_boundaries.log.
- 작성자 제공 build_support/ARM_BUILD_RESULTS_1104.json.
- 이전 재검토에서 코드 확인과 시험은 완료했으나 보고서 저장이 중단됨. 이번에는 잔존 결과 파일과 수정 설명·핵심 파일 동일성을 확인한 후 보고서 및 다운로드 묶음을 완성했다.
