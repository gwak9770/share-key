# 공유 차 키 차량 측 사용 제한 모듈

서버 연결이 끊긴 차량에서 공유 디지털키의 사용을 차량 측에서 제한하는 졸업 프로젝트입니다. STM32 인증·판단·제어 코드와 Raspberry Pi 중계, 서버·웹, 시험 기록을 팀이 함께 관리하는 것이 이 저장소의 목적입니다. 오프라인 차량이 서버의 새 취소를 즉시 알아낸다는 뜻은 아닙니다.

**팀 전체 최신 자료는 아직 모이지 않았습니다.** 아래 상태는 저장소와 GitHub를 확인한 범위입니다. 과거 보고를 현재 장비의 성공으로 확대하지 않습니다. 설계 기준은 [00](docs/00_master_design.md), 공통 AI 작업 규칙은 [AGENTS.md](AGENTS.md), 팀 협업 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)를 읽어 주세요. 이번 정리에서는 권기백 PR #2의 설계·검토·보고 체계를 우선하고 곽동규의 버전·시간·장비 적용 기록을 보완 규칙으로 유지합니다.

## Codex·Claude Code로 시작하기

공통 작업 규칙의 원본은 **[AGENTS.md](AGENTS.md)**입니다. Codex는 이 파일을 읽고, Claude Code는 루트 [CLAUDE.md](CLAUDE.md)의 `@AGENTS.md`로 같은 규칙을 불러옵니다. 규칙을 바꿀 때는 AGENTS를 수정합니다. 각 도구의 설치·로그인은 먼저 준비해 주세요.

1. 자신의 PC에 받은 저장소 루트를 엽니다. 이 PC에서는 `C:\Users\gwak9\Documents\share-key`이며, 다른 팀원은 자신의 경로를 사용합니다.
2. **Codex:** 저장소 폴더를 프로젝트로 선택해 작업을 시작합니다. CLI를 쓰는 경우 저장소 루트 터미널에서 `codex`를 실행합니다.
3. **Claude Code:** 저장소 루트 터미널에서 `claude`를 실행합니다. `/memory`로 지침 파일 위치를 확인하고, AGENTS의 공통 규칙을 읽었는지 확인합니다.
4. 첫 요청 예시: “AGENTS.md와 README.md를 읽고 현재 브랜치·Git 변경 사항부터 확인해줘. 기존 변경은 보존하고, 작업 브랜치에서 Commit·Push·PR까지 진행하고, main 병합은 하지 마.”

두 도구에서 같은 파일을 동시에 수정하지 말고, 도구를 바꿀 때 브랜치·미커밋 diff·인계 내용을 다시 확인합니다. 공동 사용 설정은 PR #3으로 main에 반영됐고 이번 통합에서도 유지합니다. 이 PC에서는 Claude Code 실행·import 로딩을 직접 시험하지 않았습니다.

동작 근거: [Codex의 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude Code의 공통 파일 import 안내](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools).

## 1. 이번 통합 초안의 기준

| 항목 | 확인 결과 |
|---|---|
| 통합 기준 확인 시각 | 2026-11-15T15:04:49+09:00 (Asia/Seoul) |
| 로컬 저장소 루트 | `C:\Users\gwak9\Documents\share-key` (이 PC의 경로) |
| 팀 저장소 / origin | [gwak9770/share-key](https://github.com/gwak9770/share-key) / `https://github.com/gwak9770/share-key.git` |
| 공개 여부 / 기본 브랜치 | 공개 / main. 보호 설정 등은 문서 말미의 확인 기록 참조 |
| main 기준 Commit | `a1f8976310a67da1d6fb34d73fdaef9edae7ecc6` (PR #3 문서 병합) |
| 권기백 자료 | [PR #2](https://github.com/gwak9770/share-key/pull/2), `4bf62ea6ef4b76311c22e6905f124ccc64831d3d` |
| 이전 이력 | `b445034` 초기 STM32 자료 → `cd4ef81` 안내 추가 → `93ca307` 곽동규 문서 → `a1f8976` main 병합 |
| 작업 브랜치 | `docs/reconcile-team-guides-20261115`. 깨끗한 최신 origin/main에서 시작. 기백님 브랜치는 변경하지 않음 |
| 이번 반영 방식 | 기백님 공통 규칙·보고 체계 우선. 00 v0.3.12 원문 보존. 곽동규의 버전·시간·승인·보존 규칙 추가 |
| 반영 단계 | 로컬 검토 후 사용자가 이 통합 내용의 main 반영을 지시함. 최종 반영 상태는 Git 이력과 통합 PR에서 확인. 원격 PR #2는 별도 보존 |

표의 SHA는 작업 시작점과 자료 출처입니다. 문서 자체의 최종 SHA를 적으려고 반복 Commit하지 않습니다. 최종 코드 SHA는 Git 이력·PR·태그·별도 적용 기록으로 추적합니다. 설계 문서의 계획·과거 보고는 현재 장비 적용 증거와 구분합니다.

통합 경위: 이번 로컬 통합 기준은 main `a1f8976310a67da1d6fb34d73fdaef9edae7ecc6`과 권기백 PR #2의 `4bf62ea6ef4b76311c22e6905f124ccc64831d3d`입니다. 00은 PR #2 원문을 보존하고, CLAUDE의 공통 내용은 AGENTS.md로 옮겼습니다. 통합 작업 중에는 PR #2의 브랜치·본문·원격 이력을 변경하지 않았습니다. 초안은 로컬 검토까지 작성했고, 이후 사용자가 이 통합 내용의 main 반영을 지시했습니다. 최종 반영 상태·Commit은 Git 이력과 통합 PR에서 확인합니다. 통합은 PR #4(`6e3e4aa`)로 main에 반영됐고, PR #2는 2026-11-15에 통합 내용을 댓글로 남기고 닫았습니다(브랜치 `docs/claude-md`는 보존).

### 운행 중 재인증 — 11/18 구현 (PR #22)

시동 허용 후 앱이 60초마다 재인증한다. 90초 동안 유효한 재인증이 없거나 인증된 운행 소유 키의 재인증이 거부되면 경고하고, 그 키의 재시동을 07(재검증 대기)로 제한한다. 주행 가정에서는 재인증 때문에 강제 종료하지 않는다. 경고 뒤 차량 로컬 입력이 연속 정차를 확인하면 설정 시간 뒤 논리적 운행 세션을 종료한다. C 방식의 재인증도 횟수를 쓰므로 정상 이용자도 소진될 수 있다.

```sh
cd sharekey
# 기존 서버·중계/시뮬레이터 실행 및 키 7 발급·등록 후
python -X utf8 app.py drive 7 --period 60  # 시동 + 주기 재인증, 거부/중단 시 타이머 종료
python -X utf8 app.py reauth 7             # 수동 재인증
python -X utf8 app.py stop 7               # 인증 후 종료, 횟수 소비 없음
python -X utf8 app.py driving-status        # 차량 상태 조회
python -X utf8 web_app.py --reauth-period 60
```

웹은 시동 허용 후 자동 재인증을 시작하고 거부·통신 오류 시 전송을 멈춘다. `drive`의 Ctrl+C는 앱 타이머만 끝내므로 차량 종료는 `stop`으로 요청한다. 경고는 해당 키가 유효로 명시된 인증 동기화로 해제한다. 취소·반납은 복구하지 않는다. 횟수 소진·취소·반납·저장 장애 중에도 운행 소유 키의 유효한 종료 인증은 허용한다. 다른 키는 진행 중인 세션을 끄거나 갱신할 수 없다.

보드 설정은 `VC_REAUTH_ENABLE=1`, 주기 60초·유예 30초·정차 종료 600초 기본이다. `check_arm_build.py --variant demo`는 정차 종료 30초를 사용한다. `VC_DEMO_DRIVE_INPUT=1`은 PC13 USER 버튼을 놓고 새로 누를 때 주행/정차 가정을 전환한다. 실제 속도 측정 기능은 없으며 앱·Pi 메시지로 정차 상태를 바꿀 수 없다. 실제 로컬 센서를 붙일 때는 이 시연 입력을 끄고 `sk_set_stopped()`에 연결한다.

OLED는 `REAUTH`, `ENG DRIVE/STOP`을 표시하고 웹은 조회 전용 `DSTATUS`로 차량 상태를 읽는다. 상태 조회의 경과 시간은 마지막 인증 이후 시간이다. 재검증 대기는 플래시에 저장하지만 운행 중 상태·타이머는 재부팅하면 초기화한다. 이전 펌웨어는 새 상태 3을 복원하지 못하므로 과거판으로 되돌릴 때 복구 절차가 필요할 수 있다.

**C/Python PC 시험을 통과한 구현이다. 11/19 김채희 보드(NUCLEO-F429ZI)에서 ARM 검사·CubeIDE 빌드·업로드와 재인증 경고·정차 뒤 종료 실물 확인을 각 1회 했다(정차 종료는 시연용 30초 빌드, 아래 [11/19 보드 적용·실물 확인](#1119-보드-적용실물-확인)). 600초 실제값의 실물 확인은 미수행이다. 기본 모터 비활성 설정이므로 실제 차량 시동 구현을 의미하지 않는다.**

## 2. 현재 구현과 검증 상태

아래 상태표는 이전 `2026-11-15T14:23:33+09:00` 확인을 바탕으로 현재 Git 파일과 대조했습니다. 이번 통합에서 생산 코드는 바꾸지 않았습니다. 과거 문서에 날짜만 있으면 실제 시험 시각은 **미상**입니다. 과거 보고의 통과 수는 이번에 재실행한 결과가 아닙니다.

| 대상 / 구분 | 확인한 내용 | 근거와 한계 |
|---|---|---|
| STM32 / 코드 구현 | 인증·nonce 검증·동기화, A/C 통합 설정, 서보 제어, 문 닫힘 뒤 재잠금, OLED 상태 갱신 코드 존재 | `cd4ef81`의 [Core](firmware/stm32/Core), [OLED 변경 기록](firmware/stm32/docs/OLED_LIVE_1106_KO.md). 장비 적용 확인 아님 |
| STM32 / 과거 PC 검증 | 11/6 기록에 MSVC 호스트 19/19 통과, 가상 I2C 검사 기재 | [OLED 변경 기록](firmware/stm32/docs/OLED_LIVE_1106_KO.md). 이번 문서 작업에서 펌웨어 시험 재실행 안 함 |
| STM32 / 보드 빌드 | 11/19 `3664cb9` 펌웨어로 ARM 검사(`default`·`demo`) PASS, CubeIDE 1.19.0 빌드 성공(각 1회) | [11/19 보드 적용·실물 확인](#1119-보드-적용실물-확인). 이후 main `f31d881`까지 펌웨어 변경 없음. 다른 PC·보드에서의 빌드는 미확인 |
| STM32 / 업로드·실물 | 11/19 김채희 보드에 업로드. 플래시 복구·전원 차단 뒤 복원·오프라인 취소·운행 중 규칙 실물 확인(각 1회) | 같은 절. 1회 시행이며 반복·장시간 시험 미수행. 이전 판 실물 보고는 [11/4 팀 전달 기록](docs/history/gwak_team_notice_20261104.md) |
| STM32 / 최신 확인 후보판 | PR #1(곽동규)의 LIVE 문 상태·I2C 복구를 `fix/servo-final` 브랜치에서 최신 main과 합침. 서보는 PR #1의 900/2100μs 대신 김채희 보드판(`_v6`·`_v7`)에서 실물로 확인한 잠금/해제 2000/1200μs로 확정(D9) | [PR #1](https://github.com/gwak9770/share-key/pull/1) head `2e692d91e15d1d210e7f5bcaf1fb577dcd4e347e`. 결과는 `fix/servo-final` PR 본문에 기록. 이 브랜치 커밋 자체의 보드 빌드·업로드는 미수행 |
| 서버·Pi 중계·웹 / 코드 | [`sharekey/`](sharekey/)에 `sharekey_1106c` 판 원본 반입(11/16). PC 모의 `demo.py`·`demo.py --relay` 각 1회 A 6/6·C 4/6 | 11/6~9 실물 시연에 쓴 판(`web_app.py` `d3a94a81…`). `demo.py --relay-c`는 C PC 하네스 없음으로 미수행. 이번 반입 뒤 Pi 실물 재확인 미수행 |
| 팀 설계·보고 / 로컬 통합 | 00 v0.3.12와 01 양식을 PR #2에서 가져오고 공통 규칙·보고 양식 통합. 통합 반영 상태는 Git 이력과 통합 PR에서 확인 | [00](docs/00_master_design.md), [01](docs/01_report_template.md), PR #2 `4bf62ea`. 00 원문은 보존, 보고 양식은 버전·시간·장비 적용 항목 보완 |
| 기백님 PC 시험 보고 / 과거 결과 | PR #2에서 macOS 호스트 19/19·OLED 5/5 통과 보고. 보드 빌드·업로드·실물은 미수행으로 기재 | [PR #2](https://github.com/gwak9770/share-key/pull/2). 이번 작업의 재실행 결과가 아님. 정확한 시험 시각 미상 |
| 영속 저장·기간 정책 | 플래시 저장은 PR #20으로 구현, 11/19 USB 전원 완전 차단 뒤 키·남은 횟수 복원 1회 확인. 기간 정책(B/D)은 A/C만 허용·RTC 기본 꺼짐으로 보드 미적용 | 1회 시행이므로 반복 전원 차단·저장 중 차단은 미수행. [config.h](firmware/stm32/Core/Inc/config.h) |

**세 가지 판을 따로 관리합니다.** main 기준판은 이 문서를 고칠 때의 `f31d881`, 실제 장비 적용판은 11/19 김채희 보드의 `3664cb9` + 로컬 설정 2줄입니다(아래 절). main 반영과 실물 검증은 서로 다른 상태입니다.

### 11/19 보드 적용·실물 확인

김채희 노트북 1대로 진행했습니다. Pi 대신 노트북에서 `pi_relay.py --serial COM4`(ST-LINK 가상 COM)로 중계했습니다. 보드 조작·관찰은 김채희, 일부 명령 실행은 Claude Code가 했습니다. 모든 실물 결과는 **각 1회 시행**입니다.

| 기록 항목 | 내용 |
|---|---|
| 구성요소 / 판 | 보드 / 실제 적용판 |
| 기반 Commit | `3664cb9638d5f373ed1b0bb8f9c095879e358b94`(main, PR #22 병합). 이 문서 작성 시 main `f31d881`과 펌웨어 동일 |
| 로컬 변경 | CubeIDE 프로젝트 `sharekey_f429_OLED_v8`의 `config.h` 2줄: `VC_DEMO_MODE_SELECT 1`(v7부터 쓰던 값), `VC_STOP_CUTOFF_S 30u`(시연용, 2차 업로드부터). 나머지 Core 파일은 저장소와 동일(줄바꿈 무시 비교) |
| 프로젝트 | `prepare_cubeide_copy.py`로 `sharekey_f429_OLED_v7`의 보드 설정을 복사해 생성(2026-11-19T10:03:46+09:00). 링커 FLASH 1792K, FLASH HAL 포함. 원본 v7은 변경 없음 |
| PC 시험 | MSVC(VS 2022) 호스트 20/20 PASS, OLED 5/5 PASS(각 1회, 시각 미상) |
| ARM 검사 | CubeIDE 1.19.0 내장 gcc + CubeF4 1.28.3, `default`·`demo` 컴파일·링크 PASS(각 1회) |
| CubeIDE 빌드·업로드 | 1차(600초) ELF 2026-11-19T11:47:09+09:00, 해시 미보존. 2차(30초) ELF 2026-11-19T13:23:19+09:00, SHA-256 `48901FCE0D09787CF5AF1E6383C7FBD79F98E4F0A9F69813C5B958D187BEBE12`. 업로드 각 1회 성공, 정확한 업로드 시각 미상 |
| 서버·중계·웹 | 같은 저장소 `sharekey/`(`3664cb9`)의 `server.py`·`pi_relay.py`·`app.py`·`web_app.py` |

| 시험 | 결과 (각 1회) |
|---|---|
| 첫 부팅 | 저장 상태가 없어 복구 필요(0A)로 시작, OLED `DENY 0A` |
| 서버 승인 복구 | `issue 9` → `net off` → `recovery-request` → `recovery-issue 9 --new-kid A` → `recovery-apply`에서 `RECOVERED`(약 12:10). 키 A 문 열기 허용(남은 3), 복구 전 키 9 거부(등록되지 않은 키) |
| 전원 차단 뒤 복원 | USB를 완전히 뽑았다 꽂은 뒤 키 A 문 열기 허용, 남은 횟수 2(3에서 이어서 감소) |
| 오프라인 취소 | 오프라인에서 서버가 키 A 취소 → 키 A 허용(남은 1) → `net on` 약 6초 뒤 키 A 거부(취소된 키) |
| 온라인 운행 유지 | 600초 빌드, 앱(웹) 종료 뒤에도 온라인 동기화가 경고를 해제해 운행 유지(12:44·13:13 `driving-status` 조회) |
| 운행 중 규칙 | 30초 빌드, 웹으로 진행. 시동 허용 → USER 버튼으로 `ENG DRIVE`/`ENG STOP` 전환 → 오프라인에서 재인증마다 남은 횟수 감소 → 0 뒤 재인증 거부·OLED `REAUTH` → 주행 가정에서는 유지 → `ENG STOP` 약 30초 뒤 운행 세션 종료 → 온라인 복귀 |
| 재시동 07 | 30초 빌드, 웹, 키 9(새로 발급·등록). 위 순서로 경고·세션 종료 뒤 오프라인에서 다시 시동 → 거부 07(재검증 대기), OLED `DENY 07` → 온라인 복귀 뒤 다시 시동 → 허용 |

미수행: 600초 실제값 정차 종료, 반복 전원 차단·저장 중 전원 차단, 오프라인 횟수 소진 뒤 문 열기 거부, 모터 출력(빌드에서 꺼짐), Pi 5 실물 중계.

진행 중 발견한 문제(코드 미수정):

- `prepare_cubeide_copy.py`가 CubeIDE 생성 링커의 `ORIGIN = 0x8000000`(앞 0 생략) 표기를 찾지 못해 `Review FLASH journal reservation manually`로 멈춘다. 이번에는 임시 복사본의 표기만 `0x08000000`으로 바꿔 우회했다.
- `sharekey_f429_OLED_v7`의 `.cproject` 빌드 출력 경로가 `${workspace_loc:/sharekey_f429}`로 고정돼 있어 복사 도구가 거부했다. 임시 복사본에서 `${ProjName}`으로 바꿨다.
- 문 열기 뒤 자동 재잠금 중 문 스위치가 열림으로 읽혀 `C FAULT`(FAULT_DOOR)가 1회 발생했고 RESET으로 해제했다. 문 스위치 배선·고정 상태 확인이 필요하다.
- 거부 상태에서 남은 횟수 값이 -1이라 OLED 3번째 줄이 `LEFT INF`로 보인다. 무제한이라는 뜻이 아니다.
- 9000번 포트에 서버를 두 번 띄우면 Windows에서 둘 다 바인딩돼 요청이 갈린다(`ERR|FF`). 서버는 하나만 띄운다.
- 이미 쓴 키 번호로 웹 "공유 키 만들기"를 다시 누르면 서버는 그 키를 유효로 덮어쓴다(취소된 키 A도 서버에서 유효로 바뀜). 보드는 취소된 키를 되살리지 않아 등록이 03으로 거부된다. 시연에서는 새 번호("새 시연" 버튼)를 쓴다.

## 3. 폴더와 주요 파일

| 경로 | 역할 |
|---|---|
| `firmware/stm32/Core/Inc`, `Core/Src` | STM32 헤더·소스. `sharekey.c/h` 인증·판단, `sk_crypto.c/h` 암호 연산, `vehicle_app.c` 통합 루프, `control.c` 제어 상태, `board.c/h` 보드 입출력, `port_stm32.c` 통신·플랫폼 연결, `oled.c` 표시 |
| `firmware/stm32/Core/Inc/config.h` | 정책·기능·서보 설정. 실제 빌드의 compiler define 재정의도 확인 필요 |
| `firmware/stm32/tests`, `tools` | PC 시험, OLED 가상 I2C 시험, CubeIDE 복사 도구, ARM 빌드 검사 도구 |
| `firmware/stm32/build_support` | 별도 ARM 컴파일·링크 검사 하네스와 과거 결과. 실제 CubeIDE 프로젝트를 대체하지 않음 |
| `firmware/stm32/examples/servo_test_f429` | 독립 서보 시험 예제. 통합 펌웨어와 구분 |
| `firmware/stm32/docs` | 버전별 변경·검증·적용 문서와 patch. 모든 기록이 현재판에 해당하지는 않음 |
| `firmware/stm32/vendor/sharekey/SOURCE_MANIFEST.json` | 인증·저장 소스의 출처·Git 원본 SHA-256. 소스 사본 폴더가 아님 |
| `sharekey/` | 서버(`server.py`)·앱(`app.py`)·Pi 중계(`pi_relay.py`)·웹 화면(`web_app.py`)·Python 판단 기준(`core.py`)·모의 차량·자동 시연(`demo.py`). 실행법은 [`sharekey/README.txt`](sharekey/README.txt) |
| `docs/00_master_design.md` | 권기백 관리 설계 기준 v0.3.25. v0.3.12는 PR #2 원문 그대로 반입, v0.3.13에서 §4·§9·§12에 저장소 기준 반영. 과거 결과·계획과 현재 적용 상태를 구분 |
| `docs/01_report_template.md` | 기백님 01 작업 보고 양식에 버전·시간·단계별 검증 기록을 추가 |
| `docs/history` | 곽동규의 과거 Pi 모의시험·R1 검토·팀 전달 기록 |
| `docs/IMPORT_MANIFEST.json`, `firmware/stm32/PACKAGE_MANIFEST.json` | 자료 반입·패키지 시점의 출처와 해시. 현재 전체 코드의 검증표로 사용하지 않음 |
| `.github/pull_request_template.md`, `.gitignore` | 기존 PR 양식, 비밀정보·빌드 결과·개인 설정 등의 제외 규칙 |

통합 디지털키 펌웨어에는 완전한 CubeIDE 프로젝트의 `.ioc`·`.cproject`가 없습니다. [독립 모터 시험 프로젝트](firmware/stm32/examples/mdd3a_motor_test_f429/README.md)의 소스·IOC·IDE 설정은 예제 폴더에 보관합니다. Python 코드는 `sharekey/`에 있지만 공유 폴더의 `sharekey/stm32/` 판단 사본은 넣지 않았습니다. 과거 문서의 외부 PC 경로·ZIP 이름은 이 저장소에 파일이 있다는 뜻이 아닙니다.

### 11/19 하드웨어 제작·독립 모터 시험

기록 버전 `motor-bench-20261119-v1`, 기반 `e957bd9`, 기준 00 v0.3.24. 실물 결과는 시험 담당자의 보고이며 정확한 시험 횟수·시각은 미상입니다. 모터 시험판의 결과를 기록했습니다.

- MDD3A와 TT 모터 4개, AA 알카라인 4개, 공통 GND, 10kΩ 풀다운 4개를 연결했습니다. 개별 모터·M1/M2·좌우 2개 병렬·USER 버튼 정지 동작은 성공 보고입니다.
- **모터 4개 동시 구동은 불안정·미완료**입니다. MDD3A 입력 전압은 정지 5.5V, 왼쪽 2개 4.6V, 오른쪽 2개 4.7V, 전체 4.2V로 관측했습니다. 공급 경로 문제는 유력 가설이며 원인 확정·개선 재시험은 미수행입니다.
- 실제 외부 시험 프로젝트 파일 105개를 원본 해시와 함께 별도 예제로 보존했습니다. 약 100Hz·40% 소프트웨어 PWM, 최대 약 500ms·버튼 재누름 조건의 시험판이며 팀의 TIM1 10kHz·인증 제어와 다릅니다. ARM 재빌드 27개 단위 PASS(1회), CubeIDE GUI 재빌드·업로드·실물 재시험 미수행입니다.
- 설치 CubeIDE 2.3.0, ETH·USB 활성화, FLASH 2048K는 팀 표준과 다릅니다. 원본 보존을 위해 통합 기준·Core는 고치지 않았습니다. 이번 재조립의 서보·문·시험 정지 스위치·OLED·RTC 연결 및 디지털키 통합 검증도 남았습니다.

자료: [작업 일지](docs/history/2026-11-19_motor_bench/work_log.md), [시험 결과·절차](docs/history/2026-11-19_motor_bench/test_results.md), [트러블슈팅](docs/history/2026-11-19_motor_bench/troubleshooting.md), [배선](docs/history/2026-11-19_motor_bench/wiring.md), [저항 CSV](docs/history/2026-11-19_motor_bench/resistance.csv), [전압 CSV](docs/history/2026-11-19_motor_bench/voltage.csv), [포트폴리오 요약](docs/history/2026-11-19_motor_bench/portfolio.md).

## 4. 구성과 개발 환경

다음은 저장소 코드·문서에 있는 구성입니다. 현재 배선·설치·장비 보유를 이번에 직접 확인한 것은 아닙니다.

```text
웹/앱 화면 ── 키 발급·취소 요청 ── 서버
    │                              ⇅ 인증 동기화
    └── 차량 요청 ── Pi 중계(전달) ⇄ STM32(인증·판단·제어)
                                      ├─ 서보 / 문 스위치
                                      └─ OLED
```

서버↔Pi↔STM32의 실제 실행 코드 중 이 저장소에서 확인 가능한 부분은 STM32입니다. 과거에는 노트북이 중계를 실행해 보드에 직접 연결한 구성도 있으므로 **노트북 직결 / Pi 경유 / 시뮬레이터**를 시험마다 적습니다. Pi 생존 신호(HB)와 서버 동기화 성공은 다른 신호입니다. HB가 와도 서버가 온라인이라고 단정하지 않습니다.

| 항목 | 저장소에서 확인한 기준 |
|---|---|
| 보드 | NUCLEO-F429ZI / STM32F429xx. [board.h](firmware/stm32/Core/Inc/board.h) |
| 도구 | 적용 문서 기준 STM32CubeIDE 1.19.0, STM32CubeF4 1.28.3. ARM 검사에는 Python 3.11 이상·Arm GNU Toolchain 필요 |
| PC 시험 | Python 3 + GCC/Clang 또는 MSVC. 이번 PC의 Python은 3.11.9, 현재 터미널 PATH에서 gcc·cl·arm-none-eabi-gcc는 찾지 못함 |
| 통신 | 적용 문서 기준 USART3 PD8/PD9, 115200 8N1. 실제 COM·장치 경로는 매번 확인 |
| 구동·입력·표시 | 코드·문서 기준 SG90 서보 PD14, 문 입력 PF12, SSD1306용 128×64 OLED 드라이버. 00에는 2.42인치 SSD1309의 과거 실물 보고가 있음. 실제 부품·배선·전원은 장비 담당 확인 필요 |
| main 기본 설정 | C 정책, 서보·재잠금·큰 글자 OLED 켬. 모터·RTC·반납 버튼·watchdog·A/C 부팅 선택 기본 끔. 잠금/해제 2000/1200μs(김채희 보드판 실물 확인값, 시험 시각·횟수 미상) |
| Raspberry Pi | 00과 기백님 팀 환경 기준 Pi 5. 현재 OS·중계 설치판·네트워크 설정 미확인 |

핀·클록·전원은 [CubeIDE 적용 안내](firmware/stm32/docs/INTEGRATE_CUBEIDE_KO.md), [배선·시험 안내](firmware/stm32/docs/WIRING_AND_TEST_KO.md)와 실제 보드를 대조합니다. 오래된 [펌웨어 README](firmware/stm32/README_KO.md)에는 OLED 기본 꺼짐 등 초기 설명이 남아 있으므로 현재 `config.h`와 후속 변경 기록을 함께 확인합니다.

### 부품 상태 (2026-11-26 기준)

| 부품 | 상태 | 쓰는 곳 | 도착 전 대체 |
|---|---|---|---|
| 4WD 주행로봇 프레임 세트 | **도착 (11/19), 조립함 (11/19)** (10/27 디바이스마트 주문) | 차체 위판 교체 | 기존 4WD 아래판 |
| Cytron MDD3A 모터 드라이버 | **도착 (11/19)**. 독립 시험판에서 모터 하나씩·좌우 2개 동작 보고, **4개 동시 구동은 불안정**(전압 4.2V, 원인 미확정). 통합 펌웨어 연결은 미수행 ([11/19 하드웨어 제작·독립 모터 시험](#1119-하드웨어-제작독립-모터-시험)) | 바퀴 구동(시동 시연) | 통합 전까지 판단만, 모터 끔(VC_ENABLE_MOTORS 0) |
| Grove Micro Switch | **취소 확정 (11/18)** | — | 문 스위치는 키트 택트 스위치로 확정(PF12–GND, VC_DOOR_ACTIVE_LOW 1) |
| Grove → 암 점퍼 케이블 | **취소 확정 (11/19)** | Grove 스위치용이라 불필요 | — |
| 4×AA 배터리 홀더(커버형), AA 건전지 4개 | **취소 확정 (11/19)**, 지금 쓰는 4구 홀더·건전지 사용 | 서보·모터 6V | 지금 쓰는 4구 홀더 |
| DS3231 RTC (키트) | 보유, 미연결. 김채희 보관(11/17 확인). 칩 DS3231SN이 붙은 'DS3231 For Pi' 소형 모듈(5핀 소켓, I2C 주소 0x68), 뒷면 12mm급 동전 전지(CR1220 추정, 규격·잔량 미확인). 핀 인쇄·전압 미확인 | B·D 기간 방식 시계 | PC 시험은 가짜 시계 |
| SG90 서보, 택트 스위치, LED (키트) | 보유, 사용 중 | 문 잠금·입력·표시 | — |
| OLED 2.42" SSD1309 | 보유, 사용 중 | 상태 표시 | — |
| 끝점 스위치 | 미주문 | 잠금 위치 확인 PF13/PF14 | 시간 추정(LOCK EST) |

디바이스마트 주문 중 4WD 프레임 세트·MDD3A는 11/19 도착·조립(MDD3A는 독립 시험만, 통합 미수행). Grove 스위치(11/18)와 케이블·홀더·건전지(11/19)는 취소 확정, 홀더·건전지는 기존 것을 쓴다. 주문 원본은 [04 주문 목록](docs/04_purchase_list.md). 부품이 도착하면 이 표의 상태와 날짜를 PR로 갱신한다.

## 5. 설치·시험·빌드

### 오프라인 판정 보완 (PR #21, PC 검증·11/19 실물 1회)

기본 2초 간격 동기화에서 연속 3회 유효한 응답이 없을 때 오프라인으로 판단한다. 첫 요청은 실패로 세지 않으며, 1·2회 실패까지 기존 온라인/미확인 상태를 유지한다. 인증된 동기화와 저장이 성공하면 즉시 온라인으로 복귀하고 연속 실패 수를 초기화한다. 잘못된 응답·Pi 생존 신호는 초기화하지 않는다. 사용 횟수는 판정 대기 중에도 기존대로 차감하며, 오프라인 표시 전환만으로 복구하지 않는다.

C와 Python 판단 코드·직접/중계 모의가 같은 규칙을 사용한다. 기본 주기에서 약 6초이며 스케줄 지연을 포함한 실물 시간 보장은 아니다. PC 시험용 1초 주기에서는 약 3초다. 저장 장애 복구 대기에는 실패를 누적하지 않는다. 스스로 통신을 끄는 이벤트·오프라인 시간 제한은 이번 범위 밖이다. 11/19 보드에서 `net off`/`net on` 뒤 수 초 안에 온라인 LED(LD2)가 꺼지고 켜지는 것을 1회 관찰했다. 판정까지 걸린 시간은 측정하지 않았다.

### 플래시 저장·복구 (PR #20, 11/19 보드 1회 확인)

최대 8키의 남은 횟수·취소/반납 상태·동기화 버전을 내부 플래시 두 구역에 기록하는 구현이다. 호스트 PC 시험과 실제 보드 결과는 구분한다. **11/19 김채희 보드에서 ARM/CubeIDE 빌드·업로드, 첫 부팅 복구, USB 전원 완전 차단 뒤 복원을 각 1회 확인했다**([기록](#1119-보드-적용실물-확인)). 반복 전원 차단·저장 중 차단 시험은 미수행이다. 실제 휴대폰 앱 대신 아래 앱 스크립트가 요청·발급·운반 역할을 한다.

- 보드는 `VC_ENABLE_FLASH=1` 기본. 최초 빈 저장소도 0A(복구 필요)로 제한한다. 서버 일반 키 발급 후 복구 절차로 초기 승인한다. `VC_ENABLE_FLASH=0`은 저장 없는 이전 시연 설정이다.
- 섹터 22·23(각 128KiB)을 예약한다. `prepare_cubeide_copy.py`는 복사본의 링커 FLASH 길이를 1792K로 변경하고 FLASH HAL 소스를 포함한다. 원본 CubeIDE 프로젝트는 건드리지 않는다. 코드/상수의 load image는 bank 1 안이어야 하며 드라이버가 검사한다.
- 저장 실패면 성공 응답·구동을 하지 않는다. 불완전한 기록은 제외하고, 완료 기록 손상은 복구 필요로 처리한다. 복구 후에는 서버가 새 승인한 키 1개만 사용한다. 복구는 이전 잔여 횟수 복원이 아니라 새 권한 부여다.
- 지우기는 모터·서보 동작 중 거부한다. HAL 지우기의 통신/제어 지연·watchdog·전압 저하 영향은 실물 확인 필요. CRC가 모든 손상·물리적 변조를 검출하거나 복구 포함 총 사용량을 보장하지 않는다.

PC 저장 모의는 `sharekey/`에서 `python -X utf8 vehicle_sim.py --mode C --flash-file vehicle_flash.bin`으로 실행한다. 생략하면 기존 RAM 시연이다. Pi 중계 모의는 `stm32_sim.py --flash-file vehicle_flash.bin`도 지원한다. 저장 파일 크기가 잘못되면 자동 삭제·초기화하지 않고 시작을 중단한다.

서버(`server.py`)와 차량/중계를 먼저 실행한 뒤 다음 단계를 각각 수행한다. 키 번호는 16진수이며, 새 번호는 서버에서 사용한 적 없는 번호여야 한다. `--server`·`--vehicle`로 주소를 지정할 수 있다.

```sh
python -X utf8 app.py issue 7
python -X utf8 app.py net off
# 차량 옆: 복구 요청을 휴대폰 역할의 파일에 담음
python -X utf8 app.py recovery-request
# 서버 통신 가능한 곳: 차량 연결 없이 새 권한 발급
python -X utf8 app.py recovery-issue 7 --new-kid 8
# 차량 옆: 서버 연결 없이 전달·적용
python -X utf8 app.py recovery-apply
python -X utf8 app.py open 8
```

`recovery/bundle.json`과 `keys/`는 인증 정보를 담는 실행 데이터이며 Git 제외 대상이다. 복구 요청 뒤 차량이 재부팅되면 요청부터 다시 하고, 이미 새 키가 발급됐다면 그 키를 근거로 또 다른 새 번호를 발급받는다. 발급 응답은 저장돼 같은 요청을 재시도할 수 있다. 차량 응답 유실로 적용 여부가 불분명하면 새 키 사용 여부로 확인한다. 일반 사용 중 `RBEGIN`으로 횟수를 충전할 수는 없다.

서버는 기존 키 소유 증명·유효/미만료 상태를 확인하고 새 권한을 발급한다. 기존 발급/취소 API는 인증 없는 개발용이며 상업용 본인 인증은 아니다. 차량 반납 후 앱이 서버에도 반납을 알리지만 알림 실패 시 서버는 그 반납을 모를 수 있다. 발급 후 전달 전 취소도 오프라인 차량에 즉시 전달되지 않는다. 서버 전체 기록은 동기화 형식에 맞춰 16개로 제한하며 장기 정리는 범위 밖이다.

추가 PC 시험(저장소 루트 기준):

```sh
python firmware/stm32/tools/run_persistence_tests.py --cc gcc
```

Windows MSVC 개발자 터미널에서는 `python -X utf8 firmware/stm32/tools/run_persistence_tests.py --cc cl`을 쓴다. 실제 C 판단 코드와 Python을 같은 시나리오로 실행하며, 기록 바이트 일치·30회 재부팅 모의·저장/구역 전환/복구 도중 차단·취소/반납 발급 거부·단계별 CLI를 검사한다. `demo.py --relay-c`용 TCP C 하네스와는 다르다.

새 PC에서는 Git을 설치하고 아래 명령으로 받습니다. 이미 이 폴더가 있으면 다시 clone하지 말고 6절의 최신 코드 확인부터 진행합니다. 도구 설치는 각자 환경에서 준비하며 이 문서 작업에서는 설치하지 않았습니다.

```powershell
git clone https://github.com/gwak9770/share-key.git
cd share-key
```

PC 시험은 저장소 루트에서 다음과 같이 실행합니다. GCC가 PATH에 있어야 합니다.

```powershell
cd firmware/stm32
python tools/run_host_tests.py --cc gcc --build-dir build-host/full
python tools/run_oled_tests.py --cc gcc --build-dir build-host/oled
```

MSVC는 Visual Studio 개발자 터미널에서 `--cc gcc`를 `--cc cl`로 바꿉니다. macOS/Linux에서 Python 명령이 `python3`이면 그 이름을 사용합니다. 전체 19개 구성에 OLED 5개가 포함됩니다. 결과 폴더를 분리한 이유는 두 도구 모두 `summary.json`을 쓰기 때문입니다. 통과 로그와 경고를 함께 보고합니다. PC 가상 입출력 시험으로 실제 보드 동작을 주장하지 않습니다.

ARM 검사는 `firmware/stm32`에서 아래 형식을 사용합니다. `<...>`는 **설치된 실제 경로로 교체**해야 하며 그대로 실행할 명령이 아닙니다.

```text
python tools/check_arm_build.py --cube-root "<설치된 STM32CubeF4 1.28.3 폴더>" --gcc "<arm-none-eabi-gcc 실행파일 경로>" --variant default
```

지원 변형과 조건은 [ARM 검사 안내](firmware/stm32/build_support/README_KO.md), 실제 인자는 `python tools/check_arm_build.py --help`로 확인합니다. 이 도구는 컴파일·링크 검사이며 보드 업로드는 하지 않습니다.

실제 CubeIDE 적용은 다음 순서로 진행합니다.

1. 장비 담당자가 **현재 사용 중인 프로젝트 전체와 설정**을 백업하고 그 판을 식별합니다.
2. [CubeIDE 적용 안내](firmware/stm32/docs/INTEGRATE_CUBEIDE_KO.md)와 [11/6 변경 기록](firmware/stm32/docs/OLED_LIVE_1106_KO.md)을 읽고 현재 프로젝트와 diff를 확인합니다. 이미 팀원의 I2C·문 상태 수정이 있으면 전체 덮어쓰기를 하지 않습니다.
3. `sharekey.c/h`를 짝으로 맞추고 생성 main·startup·링커·HAL 설정과 중복 정의를 확인합니다. `tests`와 `build_support`를 통째로 실제 Core에 넣지 않습니다.
4. CubeIDE Clean → Build 결과와 오류·경고를 기록합니다. Run 설정이 **해당 프로젝트에서 방금 만든 ELF**를 가리키는지 확인하고 업로드 결과를 별도로 기록합니다.
5. 업로드 후 필요한 RESET·키 재등록을 수행하고 실물 시험을 기록합니다. 현재 RAM 기반 상태는 RESET 뒤 유지되지 않으므로 이전 횟수 상태를 전제로 시험하지 않습니다.

서버·Pi·웹 실행법은 [`sharekey/README.txt`](sharekey/README.txt)를 따릅니다. Python 3.8 이상, 표준 라이브러리만 사용하고 Pi에서 실물 보드에 연결할 때만 `pyserial`이 필요합니다. Windows 콘솔에서 한글이 깨지거나 모의 차량이 끊기면 `PYTHONUTF8=1`(또는 `python -X utf8`)로 실행합니다. 실행 중 생기는 `server_state.json`·`keys/`는 Commit하지 않습니다(`.gitignore` 포함).

```sh
cd sharekey
python3 demo.py            # 가짜 차량 경로, A·C 결과표
python3 demo.py --relay    # 앱 → Pi 중계 → STM32 흉내 경로
```

## 6. 최신 코드와 실제 적용판 확인

작업 전 저장소 루트에서 확인합니다. `fetch`는 원격 정보를 가져오며 작업 파일을 자동 교체하지 않습니다.

```powershell
git rev-parse --show-toplevel
git status --short --branch
git remote -v
git fetch origin
git symbolic-ref refs/remotes/origin/HEAD
git log -5 --oneline origin/main
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff
git diff --cached
```

origin이 팀 저장소인지 먼저 확인합니다. fetch 실패 시 **최신 원격 상태 미확인**으로 적습니다. 마지막 두 diff는 미커밋 변경 확인입니다. GitHub의 [열린 PR](https://github.com/gwak9770/share-key/pulls)도 읽어 main과 후보판을 구분합니다.

실제 보드 적용판은 담당자에게 프로젝트 경로·기반 Commit·추가 로컬 변경·compiler define·ELF/BIN 해시·업로드 로그·실물 결과를 받아 확인합니다. 적용 파일 SHA-256과 Git의 해당 Commit 파일을 비교하고 차이가 있으면 수정 내용을 기록합니다. 빌드·업로드 시각과 시험 시각은 따로 적습니다. 화면에 날짜가 보이거나 부팅 로그가 같다는 이유만으로 버전 일치를 확정하지 않습니다. 증거가 없으면 **실제 장비 적용판 미확인**입니다.

## 7. 팀 작업 순서

브랜치는 작업 공간, Commit은 변경 기록, Push는 GitHub 업로드, PR은 main 병합 요청, Merge는 main 반영입니다.

1. 00의 관련 절·현재 상태·관련 PR·요청된 개인 인계·실제 코드를 확인합니다. 미커밋 변경은 보존합니다. 임의 stash·reset·clean·복원은 하지 않습니다.
2. 같은 작업의 브랜치·PR이면 이어갑니다. 새 작업이고 작업 폴더가 깨끗할 때만 다음 명령을 사용합니다. 아래 브랜치 이름은 예시이며 이미 있으면 재생성하지 않습니다.

   ```powershell
   git fetch origin
   git switch -c docs/project-guide-20261115 origin/main
   ```

   로컬 main을 먼저 갱신하는 방식이라면 `git switch main` → `git pull --ff-only origin main` 후 새 브랜치를 만듭니다. 분기·충돌 시 강제로 맞추지 않습니다. 다른 작업이 남아 있으면 독립 worktree 등을 검토합니다.
3. 필요한 파일만 수정 → 변경에 맞는 기존 시험·빌드 검사 → 결과·한계·다음 작업 기록 → `git diff --check`, `git diff`, `git status` 검토 순서로 진행합니다.
4. **기본 흐름은 수정 → 검증 → Commit → 작업 브랜치 Push → PR → (사용자 확인) → main 병합입니다.** 자기 작업 브랜치에서는 AI가 사용자 허락 없이 PR 생성까지 진행합니다. 팀원 리뷰·승인은 받지 않습니다.
5. Commit할 때 경로는 이번 작업 파일만 명시하고 `git diff --cached`에서 신규 파일과 비밀정보도 확인합니다.

   ```powershell
   git add README.md AGENTS.md CLAUDE.md
   git diff --cached
   git commit -m "docs: 프로젝트 안내와 AI 작업 규칙 정리"
   git push -u origin HEAD
   ```

6. 기백님 방식대로 작업 기록은 [01 양식](docs/01_report_template.md)을 따른 PR 본문에 씁니다. 같은 작업의 열린 PR이 있으면 갱신하고, 없으면 `main` 대상 **Draft PR(초안)**을 만듭니다. [기존 양식](.github/pull_request_template.md)에 문제·변경·버전/기반 SHA·시험 결과·실물 여부·남은 위험을 담습니다. main 직접 Push·자동 Merge·자동 Merge 예약은 하지 않습니다.
7. 필요한 검증을 마친 뒤 main 병합은 **AI가 사용자에게 묻고, 사용자가 대상 PR과 최신 변경에 대해 명시적으로 허락하면** 진행합니다. 직전에 main·PR 최신 상태, 충돌, 검증 결과를 다시 확인합니다. “코드가 괜찮다”는 병합 허락이 아닙니다.

빈 저장소이거나 최초 Commit이 없다면 위 절차를 사용할 수 없습니다. origin·기본 브랜치·초기 반입 범위를 확인하고 첫 Commit·원격 초기화 방법을 사용자와 정한 뒤 진행합니다. 이번 저장소에는 이미 이력이 있으므로 해당하지 않습니다.

## 8. 새 코드·ZIP·작업 MD 반영과 버전 기록

새 자료는 별도 위치에서 원본을 보존한 뒤 파일 목록·내용·기반 버전·변경 이력·검증 결과를 비교합니다. **파일 수정 시각, 파일명 날짜, `_1` 같은 숫자만으로 최신판을 고르지 않습니다.** 늦게 나온 미검증판은 최신 후보판으로 둡니다.

수신 → 원본 ZIP 이름·SHA-256 기록 → 비밀정보 확인 → 현재 코드와 diff → 기존 수정의 누락·되돌림 및 중복 소스 일치 검사 → 필요한 변경만 작업 브랜치에 반영 → 관련 시험 → 결과 기록 순서입니다. 기존 MD는 과거 결과를 보존하고 PR 본문에서 정정·후속 결과를 연결합니다. 별도 인계를 요청받으면 개인별 파일을 보조 기록으로 사용합니다. 근거가 충돌하면 덮어쓰지 말고 두 판의 차이와 판단 대기 항목을 적습니다.

수신·적용 기록에는 다음 양식을 사용합니다. 시각은 **Asia/Seoul ISO 8601**(예: `2026-11-15T14:30:00+09:00`, 형식 예시이며 실제 사건 시각 아님)으로 적습니다. 날짜만 알면 원문 날짜를 따로 남기고 정확한 시각은 `미상`으로 둡니다. 미확인 상태와 미상 시각을 구분합니다.

| 기록 항목 | 입력할 내용 |
|---|---|
| 구성요소 / 판의 구분 | 보드·서버·Pi·웹 / main 기준판·최신 후보판·실제 적용판 |
| 버전 또는 후보판 ID / 작성자·제공자 | 식별자와 실제 확인한 사람. 모르면 미확인 |
| 작성 시각 / 배포 시각 / 수신 시각 | 각각 별도 기록. 모르면 미상 |
| 기반 버전 / 기반 Commit | 어느 판에서 바뀌었는지 |
| 변경 내용 / 코드 Commit SHA | 코드가 있는 Commit의 전체 SHA. 아직 미커밋이면 미커밋으로 표시 |
| 외부 ZIP | 원본 파일명 + 원본 바이트의 SHA-256. 해당 없으면 해당 없음 |
| 호환 구성요소 | 서버·중계·웹·보드의 버전 조합과 통신·설정 차이. 모르면 미확인 |
| 검증 결과 / 확인 시각 | PC 시험, ARM 검사, CubeIDE 빌드 각각 방법·환경·횟수·결과·시각 |
| 실제 업로드 / 실물 확인 | 각각 수행 여부·담당자·장비·시각·결과·로그/사진 위치 |
| 적용 산출물 | 사용한 ELF/BIN 해시, 프로젝트 설정·추가 로컬 변경, 복귀할 이전판 |

PowerShell에서 수신한 원본 ZIP은 `Get-FileHash -LiteralPath '<실제 ZIP 경로>' -Algorithm SHA256`으로 확인합니다. 압축을 다시 만든 파일의 해시로 원본을 대신하지 않습니다. Git 줄바꿈 변환(LF/CRLF)은 바이트 해시를 바꿀 수 있으므로 원본 바이트·Git 저장 원본·작업 사본을 구분합니다. 정규화 후 같더라도 원본 해시가 같다고 쓰지는 않습니다.

현재 인증 소스는 한 벌이며 동일 이름의 중복 소스는 없습니다. 이번 검사에서 `SOURCE_MANIFEST.json`의 4개 해시는 Git 저장 원본과 모두 일치했습니다. 로컬 `sk_crypto.c/h`의 바이트 해시는 `core.autocrlf=true`에 따른 LF→CRLF 변환으로 달랐고 LF 비교 시 일치했습니다. 해시를 맞추려고 파일이나 매니페스트를 임의 변경하지 않았습니다.

## 9. 자주 생기는 문제와 복구

현재 `sharekey.c`에는 개발용 고정 데모 마스터키가 소스에 포함되어 있어 공개 저장소에서 읽을 수 있습니다. 실제 장비·서버에서도 이 값을 쓰는지는 미확인입니다. 실제 비밀키와 구분하고, 운용에 사용했다면 담당자가 교체·주입 방식을 검토해야 합니다. 비밀번호·실제 키·토큰·개인 설정·발급 데이터·실행 상태 파일은 Commit하지 않습니다. `.gitignore`는 이미 추적한 파일이나 소스 내부의 값을 제거하지 않습니다.

| 문제 | 먼저 할 일 |
|---|---|
| pull의 fast-forward 실패 / 브랜치 전환 거부 | `git status`, `git diff`, Git 이력 확인. 변경을 보존하고 분기 원인을 설명. 강제 reset·clean·자동 stash로 해결하지 않음 |
| 팀 코드 반영 중 충돌 | 양쪽 변경과 기반판을 비교. 서보 보정·OLED·통신 수정 누락 여부 확인. 한쪽 파일 전체로 덮지 않음 |
| fetch/Push 실패 | 주소·네트워크·계정 권한 확인. 실패를 완료로 쓰지 않음. main Push나 force push로 우회하지 않음 |
| C compiler not found | GCC/Clang 설치 경로 또는 MSVC 개발자 터미널 확인. 실행하지 못한 시험은 미수행 |
| 보드가 이전 동작을 함 | Run 설정의 프로젝트·ELF, 빌드 결과·해시, 업로드 로그 확인. 업로드 성공과 실물 동작을 별도 확인 |
| ALLOW인데 구동이 안 됨 | 인증 응답과 `ACT`·제어 오류를 구분. HB·`LINK_STALE`, 배선·전원·안전 입력 확인. 안전 차단을 임의 해제하지 않음 |
| 문이 다시 잠기지 않음 | 실제 열림→닫힘 입력이 생기는지 확인. 스위치를 처음부터 계속 누른 상태와 구분. [팀 시험 안내](docs/history/gwak_team_notice_20261104.md) 참조 |
| RESET 후 키·횟수가 달라짐 | 현재 RAM 상태 초기화 특성을 확인하고 시험용 키를 재등록. 재부팅 내구성이 검증됐다고 기록하지 않음 |
| 보드 적용 뒤 문제 발생 | 원인·로그를 보존. 적용 기록으로 확인한 이전 프로젝트·산출물로 담당자가 복귀하고 재시험. 출처 불명 ZIP으로 복구하지 않음 |
| 실제 비밀정보 노출 의심 | 값을 채팅·PR에 복사하지 않고 위치를 알림. 실제 사용 여부와 폐기·교체 필요성을 담당자에게 확인. ignore만 추가해 해결됐다고 쓰지 않음 |

## 10. 기준 문서·작업 보고와 다음 작업

기백님 설계·보고 체계를 기준으로 문서의 역할을 나눴습니다.

| 문서 | 역할 / 관리·변경 절차 |
|---|---|
| [00 전체 설계](docs/00_master_design.md) | 설계 기준 v0.3.25, 관리 권기백. 설계·코드는 같은 작업 브랜치에서 함께 변경하고 main 최종 병합 때만 사용자 허락 |
| [02 최종 로드맵](docs/02_final_roadmap.md) | 최종발표까지 할 일·담당·마감·완료 기준 |
| [AGENTS](AGENTS.md) / [CLAUDE](CLAUDE.md) | 공통 작업 규칙은 AGENTS 한 곳. CLAUDE는 import 연결. 공통 규칙 변경은 PR로 처리하고 main 병합 때 사용자 확인 |
| [CONTRIBUTING](CONTRIBUTING.md) | 팀원의 브랜치·검증·업로드·병합 절차 |
| [01 보고 양식](docs/01_report_template.md) / [PR 양식](.github/pull_request_template.md) | 한 일·결정·파일·00과 차이·시험·질문·다음 작업 7항목과 참고. 곽동규의 버전·시각·장비 적용 기록 보완 |
| README 8절 | main 기준판·후보판·적용판 식별과 수신·호환성·검증 기록 |
| PR / Issue / 요청된 개인 인계 | 변경 보고는 PR, 질문·요청·버그는 Issue. 별도 개인 인계는 요청받은 경우에만 보조 기록 |

기존 인계는 [11/6 OLED 변경·한계](firmware/stm32/docs/OLED_LIVE_1106_KO.md), [R1 검토](docs/history/01_gwak_r1_recheck_20261104.md), [팀 전달·시험 순서](docs/history/gwak_team_notice_20261104.md), [Pi 모의시험](docs/history/곽동규_라즈베리파이세팅_1028.md), [반입 목록](docs/IMPORT_MANIFEST.json)에서 보존합니다. 각 문서의 대상 코드·시점을 확인합니다.

**00과 실제 저장소:** 00 v0.3.13부터 §9에 저장소 기준(판단 코드는 `firmware/stm32` 한 곳·한 벌)을, §12에 PR 본문 보고를 반영했습니다. §9의 공유 폴더 구조·여러 사본 기록은 과거 기록으로 보존합니다. 서버·중계·웹 Python 코드는 v0.3.16부터 `sharekey/`에 있고, 과거 공유 폴더의 LIVE판과 현재 main 코드도 다릅니다. 차이를 구현 완료로 처리하지 않습니다.

팀 역할은 AGENTS 9절과 00을 따릅니다. 권기백은 PM·설계 관리·보안/판단 검토, 곽동규는 STM32 제어·시험·저장, 김채희는 Pi·STM32 빌드/업로드, 조민선은 실물·보정이 주 영역입니다. 새 역할 배정이나 현재 구현 완료를 뜻하지 않으며 필요에 따라 협업합니다. 곽동규를 발표자로 지정하지 않습니다. 최종 병합 담당은 프로젝트 운영에 맞게 정하고, AI Merge에는 대상 PR과 최신 내용에 대한 별도 사용자 지시가 필요합니다.

이번 통합은 main `a1f8976`과 권기백 PR #2 `4bf62ea`를 비교해 만든 로컬 초안입니다. 기백님 CLAUDE의 공통 규칙을 AGENTS로 옮기고 CONTRIBUTING·PR/01 양식을 기준으로 채택했습니다. 곽동규의 버전·시간·해시·실제 장비 적용 기록과 변경 보존·승인 절차는 추가 규칙으로 남겼습니다. 원격 PR #2는 미병합이며 브랜치·본문을 수정하지 않았습니다. 추후 GitHub 반영 시 기존 PR과 연결하고 기백님 기여를 보존해야 합니다.

추가 문서는 아직 만들지 않았습니다. `docs/STATUS.md`는 구성요소 상태를 모을 필요가 생기면, `CHANGELOG.md`는 릴리스 변경을 정리할 필요가 생기면 제안합니다. 개인 인계를 요청받으면 `docs/handoff/곽동규.md`처럼 각자 파일을 사용합니다. 한 파일을 여러 사람이 동시에 편집하지 않고 PR 보고를 대체하지 않습니다. `.gitignore`는 기존 것을 유지했습니다.

다음 작업부터는 요청 범위 안에서 작업 브랜치 생성·수정·검증·Commit·Push·PR까지 별도 허락 없이 진행하고, 최종 main 병합 직전에만 사용자에게 대상 PR·최신 변경·검증 결과를 보여 주고 허락을 받습니다. 설계 문서 관리자나 다른 팀원의 승인 대기는 두지 않습니다. 별도로 팀 최신 소스·실제 CubeIDE 프로젝트·적용 증거를 받아 PR #1 후보판과 비교하고 필요한 보드 빌드·업로드·실물 검증을 진행해야 합니다. RTC·영속 저장·모터·기간 제한 구현은 이번 문서 작업의 범위 밖이며, 해당 작업을 요청받으면 같은 브랜치에서 설계와 코드를 함께 맞춥니다. 현재 자료만으로 재부팅 뒤 제한 유지나 실제 각도·전력·지연 성능을 보장할 수 없습니다.

이전 GitHub 확인에서 main은 protected=false였습니다. 문서 규칙은 GitHub 보호 설정을 대신하지 않습니다. PR 필수(main 직접 Push 차단), force push·삭제 차단을 제안하며(팀원 리뷰 필수는 두지 않음) 이번에 설정은 변경하지 않았습니다. 자동 CI는 실제 환경과 검사 실행을 확인한 뒤 검토합니다.

기존 곽동규 문서 작업에서는 로컬 링크·경로·명령·diff를 검토했고 PC/OLED/ARM 도구 3개의 --help를 확인했습니다. 기백님 PR #2의 시험 보고는 상태표에서 별도 구분했습니다. 이번 통합도 문서 검토 범위이며 펌웨어 시험·ARM/CubeIDE 빌드·업로드·실물 시험·Claude Code 실제 import 로딩 시험은 미수행입니다. 초안 검토 뒤 사용자의 main 반영 지시를 받았으며 최종 반영 상태는 통합 PR과 Git 이력으로 추적합니다.

이번 통합 검토 결과: 로컬 링크 44개, UTF-8·코드 블록·문서 형식·일반 비밀정보 패턴·diff 공백 검사 통과. 00 원문은 PR #2와 바이트 단위 동일하며 CLAUDE import 연결과 보고 양식 1~8항을 유지했습니다. 변경 범위는 문서 6개이고 코드는 바꾸지 않았습니다.
