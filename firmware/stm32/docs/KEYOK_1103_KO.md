# 등록 시 OLED 표시 (KEY OK / KEY NG) — 권기백 1103

> 기준: 00 v0.3.9 (1104 갱신) · 바탕: 곽동규 1102 판(다시 잠그기·OLED 큰 글자, `stm32_vehicle_control_f429_v2 2`)
> 판단 코드(sharekey.c/h, sk_crypto.c/h)·메시지 형식·통신 줄은 **바꾸지 않음**. 보드 빌드·실물은 **미확인**.

## 바뀐 것
| 파일 | 내용 |
|---|---|
| Core/Inc/vehicle_platform.h | `VehicleDisplay`에 `kid[9]` 추가, `policy`에 'K'(KEYOK)·'N'(KEYNG) 값 추가 |
| Core/Src/vehicle_app.c | `sk_port_send_line()`에서 판단 코드가 보내는 `RR|KEYOK|KID`(17자)·`RR|KEYNG|KID|CC`(20자)를 알아보고 **화면 상태만** 바꿈. 보내는 줄은 그대로 전달 |
| Core/Src/oled.c | 큰 글자 화면: 2줄 `KEY OK` 또는 `KEY NG 01`, 3줄 `KEY 7`(앞 0 생략). 다음 문 열기·시동 결과가 오면 평소 화면으로 |
| tests/test_app.c, tests/test_oled.c | 등록 성공·위조 등록(01)·다음 RES로 덮어쓰기, OLED 픽셀 검사 |

## 시험 (PC, 가상 GPIO·I2C)
- `python3 -I tools/run_host_tests.py --cc gcc` (gcc 11.4, `-Wall -Wextra -Werror`) → **17/17 통과**
- 표시 코드를 일부러 빼면 `app_c`·`app_a`가 실패하는 것 확인 (새 시험이 실제로 검사함)
- 화면 미리보기: `docs/oled_keyok_preview_1103.png` (PC 시험 I2C 출력으로 그린 것, 실물 사진 아님)

## 보드에 적용 (김채희 노트북) — 1104 갱신: 8개 파일
> 1103 처음 판의 "4개/3개만 덮어쓰기" 안내는 USER 모드 선택을 넣기 전 목록이라 틀렸음(곽동규 검토 R2). 아래 8개를 모두 덮어쓴다.

1. `sharekey_f429_OLED` 프로젝트를 통째로 백업
2. 이 폴더의 8개 파일을 덮어쓰기
   - `Core/Inc`: `config.h`, `board.h`, `vehicle_app.h`, `vehicle_platform.h`
   - `Core/Src`: `board.c`, `port_stm32.c`, `vehicle_app.c`, `oled.c`
3. CubeMX 설정(TIM4 PD14, I2C1 PB8/PB9, `MX_TIM4_Init`·`MX_I2C1_Init` 호출 끔)은 그대로. **Clean** → Build(0 errors) → Run As
4. 웹 화면이나 터미널에서 **차에 키 등록** → OLED에 `KEY OK` / `KEY 7` 확인. 이어 문 열기 → `ALLOW` / `LEFT 3`
5. `VC_DEMO_MODE_SELECT`는 기본 0(꺼짐). 먼저 0으로 등록·다시 잠그기를 실물 확인한 뒤 1로 켠다

## USER 버튼 모드 선택 (`VC_DEMO_MODE_SELECT 1`일 때만)
- USER를 누른 채 RESET → 기본 다음 모드(C면 A)가 화면에 나옴 → 누르고 있으면 1.5초마다 C↔A → **손을 떼면 확정**
- 누르지 않고 RESET → 기본 모드(`APP_POLICY_MODE`, 지금 C)
- **15초 넘게 계속 누르면** 그 순간 화면에 보이는 모드로 확정(`VC_MODE_SELECT_MAX_MS`). 버튼이 눌린 채 고장 나도 부팅이 멈추지 않게 하려는 것
- 확정 뒤 부팅 로그 `MODE=A` 또는 `MODE=C`, OLED 첫 줄 모드 글자 확인. 키는 RAM에만 있으므로 RESET마다 다시 등록

## 1104 수정 — 모드 선택 중 받은 HB (곽동규 검토 R1)
- 문제: 선택을 기다리는 동안 들어온 HB가 큐에 남아 있다가 선택이 끝난 뒤 처리되면서 **처리한 시각**으로 기록됨 → 실제로는 오래된 HB가 약 2초간 새 신호로 취급(PC 재현: age 3930ms인데 fresh=1, 문 열기 ACT=OK)
- 고침(`vehicle_app.c` `select_mode`만): 선택 중 들어오는 UART 바이트는 계속 버리고, 선택이 끝날 때 한 번 더 비움. 버린 마지막 바이트가 줄 중간이면 다음 줄 끝(`\n`)까지 버려서 잘린 꼬리가 명령으로 실행되지 않게 함. **선택 뒤에 새로 온 HB가 있어야** 서보가 움직임
- 판단 코드(sharekey.c/h, sk_crypto.c/h)·메시지 형식·핀은 바꾸지 않음. 모드 선택을 끈 빌드(기본 0)에는 영향 없음
- 시험(PC): `tests/test_app.c` `test_mode_select_drops_buffered_rx` 추가 — 선택 중 HB 1줄 → 선택 뒤 link 오래됨·문 열기 허용돼도 서보 안 움직임 → 새 HB 뒤 움직임 / 잘린 줄 꼬리 버림 / 15초 시간 초과 확정. **수정 전 코드로 돌리면 이 시험이 실패**하는 것 확인
- 결과: `python3 -I tools/run_host_tests.py --cc gcc` (gcc, `-Wall -Wextra -Werror`) 19/19 통과. ARM 컴파일·링크 5종(default/demo/policy-a/all-features/servo) 통과, 경고 0 → `build_support/ARM_BUILD_RESULTS_1104.json`
- 동규 재현 코드(`evidence/test_review_boundaries.c`)를 고친 판으로 돌리면 `fresh=0` (그 파일의 assert는 버그를 전제로 해서 멈추는 것이 정상)
- 1103 대비 차이: `docs/R1_1104.patch` (config.h 주석, vehicle_platform.h 주석 정리, vehicle_app.c, tests/test_app.c)
- **보드·CubeIDE·실물은 미확인**
