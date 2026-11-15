# 공유 차 키 차량 측 사용 제한 모듈

서버 연결이 끊긴 차량에서 공유 디지털키의 사용을 차량 측에서 제한하는 졸업 프로젝트입니다. STM32 인증·판단·제어 코드와 Raspberry Pi 중계, 서버·웹, 시험 기록을 팀이 함께 관리하는 것이 이 저장소의 목적입니다. 오프라인 차량이 서버의 새 취소를 즉시 알아낸다는 뜻은 아닙니다.

**팀 전체 최신 자료는 아직 모이지 않았습니다.** 아래 상태는 저장소와 GitHub를 확인한 범위입니다. 과거 보고를 현재 장비의 성공으로 확대하지 않습니다. AI 작업 규칙은 [AGENTS.md](AGENTS.md), 기존 팀 협업 안내는 [CONTRIBUTING.md](CONTRIBUTING.md)를 읽어 주세요.

## Codex·Claude Code로 시작하기

공통 작업 규칙의 원본은 **[AGENTS.md](AGENTS.md)**입니다. Codex는 이 파일을 읽고, Claude Code는 루트 [CLAUDE.md](CLAUDE.md)의 `@AGENTS.md`로 같은 규칙을 불러옵니다. 규칙을 바꿀 때는 AGENTS를 수정합니다. 각 도구의 설치·로그인은 먼저 준비해 주세요.

1. 자신의 PC에 받은 저장소 루트를 엽니다. 이 PC에서는 `C:\Users\gwak9\Documents\share-key`이며, 다른 팀원은 자신의 경로를 사용합니다.
2. **Codex:** 저장소 폴더를 프로젝트로 선택해 작업을 시작합니다. CLI를 쓰는 경우 저장소 루트 터미널에서 `codex`를 실행합니다.
3. **Claude Code:** 저장소 루트 터미널에서 `claude`를 실행합니다. `/memory`로 지침 파일 위치를 확인하고, AGENTS의 공통 규칙을 읽었는지 확인합니다.
4. 첫 요청 예시: “AGENTS.md와 README.md를 읽고 현재 브랜치·Git 변경 사항부터 확인해줘. 기존 변경은 보존하고, 로컬 수정·검토까지만 진행해줘. Commit·Push·PR 생성·Merge는 하지 마.”

두 도구에서 같은 파일을 동시에 수정하지 말고, 도구를 바꿀 때 브랜치·미커밋 diff·인계 내용을 다시 확인합니다. 이번 공동 사용 설정은 기존 `chore/work-20261115`에서 이어 작성했습니다. 이 PC에서는 Claude Code 실행·import 로딩을 직접 시험하지 않았습니다.

동작 근거: [Codex의 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude Code의 공통 파일 import 안내](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools).

## 1. 이번 초안의 기준

| 항목 | 확인 결과 |
|---|---|
| 확인 시각 | 2026-11-15T14:23:33+09:00 (Asia/Seoul) |
| 로컬 저장소 루트 | `C:\Users\gwak9\Documents\share-key` (이 PC의 경로) |
| 팀 저장소 / origin | [gwak9770/share-key](https://github.com/gwak9770/share-key) / `https://github.com/gwak9770/share-key.git` |
| 공개 여부 | GitHub API 조회 결과 공개. 기존 문서의 비공개 표기는 과거 기록 |
| 기본 브랜치 | `main` |
| main 기준 Commit | [`cd4ef8157b2abbae937665b9350c71d0c978532d`](https://github.com/gwak9770/share-key/commit/cd4ef8157b2abbae937665b9350c71d0c978532d) |
| 기준 이력 | `b445034`: 초기 STM32 자료 반입 → `cd4ef81`: 저장소 안내 추가 |
| 이번 작업 | 앞서 준비한 `chore/work-20261115` 사용. fetch 성공, HEAD와 origin/main 동일한 상태에서 시작 |
| 시작 시 사용자 변경 | 미추적 `AGENTS.md` 초안이 있었음. 먼저 읽고 규칙을 반영해 개정. 그 밖의 변경 없음 |
| 이번 단계 | README·AGENTS 로컬 초안과 CLAUDE 연결 파일 작성·검토. Commit·Push·PR 생성·Merge 미수행 |

위 SHA는 **작업 시작점**입니다. 이 문서 자체의 최종 SHA를 적기 위해 반복 Commit하지 않습니다. 이후 코드의 최종 SHA는 Git 이력·PR·태그·별도 장비 적용 기록으로 추적합니다.

## 2. 현재 구현과 검증 상태

아래 표의 확인일은 모두 위 확인 시각입니다. 과거 문서에 날짜만 있으면 실제 시험 시각은 **미상**입니다. 과거 보고의 통과 수는 이번에 재실행한 결과가 아닙니다.

| 대상 / 구분 | 확인한 내용 | 근거와 한계 |
|---|---|---|
| STM32 / 코드 구현 | 인증·nonce 검증·동기화, A/C 통합 설정, 서보 제어, 문 닫힘 뒤 재잠금, OLED 상태 갱신 코드 존재 | `cd4ef81`의 [Core](firmware/stm32/Core), [OLED 변경 기록](firmware/stm32/docs/OLED_LIVE_1106_KO.md). 장비 적용 확인 아님 |
| STM32 / 과거 PC 검증 | 11/6 기록에 MSVC 호스트 19/19 통과, 가상 I2C 검사 기재 | [OLED 변경 기록](firmware/stm32/docs/OLED_LIVE_1106_KO.md). 이번 문서 작업에서 펌웨어 시험 재실행 안 함 |
| STM32 / 보드 빌드 | 현재 main 코드 전체의 ARM/CubeIDE 빌드 성공은 미확인 | 같은 11/6 기록은 해당 수정본 ARM·CubeIDE 빌드 미수행을 명시. [과거 ARM 결과](firmware/stm32/build_support/)를 현재 결과로 사용하지 않음 |
| STM32 / 업로드·실물 | 현재 장비에 올린 버전과 실제 동작 미확인 | [11/4 팀 전달 기록](docs/history/gwak_team_notice_20261104.md)에 이전 1102판 실물 보고가 있으나 현재 main의 성공 증거는 아님 |
| STM32 / 최신 확인 후보판 | PR #1의 LIVE 문 상태·I2C 복구·서보 900/2100μs 보정. 열린 PR, 미병합 | [PR #1](https://github.com/gwak9770/share-key/pull/1), head `2e692d91e15d1d210e7f5bcaf1fb577dcd4e347e`. PC 19/19·OLED 5/5 보고. OLED 5개는 19개와 중복. 보드 빌드·업로드·실물 각도 미확인 |
| 서버·Pi 중계·웹 / 자료 | 현재 main에 실행 소스 없음. 자료 수신 대기 | `cd4ef81` 파일 목록과 [과거 Pi 모의시험 기록](docs/history/곽동규_라즈베리파이세팅_1028.md) 대조. 당시 시험은 Python STM32 시뮬레이터 사용 |
| 팀 기준 문서 / 제안 | 설계 v0.3.12·CLAUDE.md·PR 양식 변경이 PR #2에 있음. main에는 아직 없음 | [PR #2](https://github.com/gwak9770/share-key/pull/2), head `4bf62ea`. PR 내 문서와 main의 파일을 혼동하지 않음 |
| 영속 저장·기간 정책 / 계획·미통합 | 재부팅 뒤 상태 유지 완료 근거 없음. 현재 제어 통합 설정은 A/C만 허용, RTC 기본 꺼짐 | [sharekey.c](firmware/stm32/Core/Src/sharekey.c)의 RAM 상태·저장 TODO, [config.h](firmware/stm32/Core/Inc/config.h). TODO의 날짜는 완료 증거가 아님 |

**세 가지 판을 따로 관리합니다.** main 기준판은 `cd4ef81`, 이 저장소에서 확인한 최신 STM32 후보판은 PR #1, 실제 장비 적용판은 미확인입니다. 팀이 따로 보유한 더 최신 자료는 수신 대기입니다. main 반영과 실물 검증은 서로 다른 상태입니다.

## 3. 폴더와 주요 파일

| 경로 | 역할 |
|---|---|
| `firmware/stm32/Core/Inc`, `Core/Src` | STM32 헤더·소스. `sharekey.c/h` 인증·판단, `sk_crypto.c/h` 암호 연산, `vehicle_app.c` 통합 루프, `control.c` 제어 상태, `board.c/h` 보드 입출력, `port_stm32.c` 통신·플랫폼 연결, `oled.c` 표시 |
| `firmware/stm32/Core/Inc/config.h` | 정책·기능·서보 설정. 실제 빌드의 compiler define 재정의도 확인 필요 |
| `firmware/stm32/tests`, `tools` | PC 시험, OLED 가상 I2C 시험, CubeIDE 복사 도구, ARM 빌드 검사 도구 |
| `firmware/stm32/build_support` | 별도 ARM 컴파일·링크 검사 하네스와 과거 결과. 실제 CubeIDE 프로젝트를 대체하지 않음 |
| `firmware/stm32/examples/servo_test_f429` | 독립 서보 시험 예제. 통합 펌웨어와 구분 |
| `firmware/stm32/docs` | 버전별 변경·검증·적용 문서와 patch. 모든 기록이 현재판에 해당하지는 않음 |
| `firmware/stm32/vendor/sharekey/SOURCE_MANIFEST.json` | 인증 소스 4개 파일의 출처·SHA-256. 소스 사본 폴더가 아님 |
| `docs/history` | 곽동규의 과거 Pi 모의시험·R1 검토·팀 전달 기록 |
| `docs/IMPORT_MANIFEST.json`, `firmware/stm32/PACKAGE_MANIFEST.json` | 자료 반입·패키지 시점의 출처와 해시. 현재 전체 코드의 검증표로 사용하지 않음 |
| `.github/pull_request_template.md`, `.gitignore` | 기존 PR 양식, 비밀정보·빌드 결과·개인 설정 등의 제외 규칙 |

현재 main에는 `server.py`, `pi_relay.py`, `web_app.py`, 완전한 CubeIDE 프로젝트의 `.ioc`·`.cproject`가 없습니다. 과거 문서의 외부 PC 경로·ZIP 이름은 이 저장소에 파일이 있다는 뜻이 아닙니다.

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
| 구동·입력·표시 | 코드·문서 기준 SG90 서보 PD14, 문 입력 PF12, SSD1306 128×64 OLED. 실제 부품·배선·전원은 장비 담당 확인 필요 |
| main 기본 설정 | C 정책, 서보·재잠금·큰 글자 OLED 켬. 모터·RTC·반납 버튼·watchdog·A/C 부팅 선택 기본 끔. 잠금/해제 1200/1800μs |
| Raspberry Pi | PR #2 제안 문서는 Pi 5를 명시. 현재 OS·중계 설치판·네트워크 설정 미확인 |

핀·클록·전원은 [CubeIDE 적용 안내](firmware/stm32/docs/INTEGRATE_CUBEIDE_KO.md), [배선·시험 안내](firmware/stm32/docs/WIRING_AND_TEST_KO.md)와 실제 보드를 대조합니다. 오래된 [펌웨어 README](firmware/stm32/README_KO.md)에는 OLED 기본 꺼짐 등 초기 설명이 남아 있으므로 현재 `config.h`와 후속 변경 기록을 함께 확인합니다.

## 5. 설치·시험·빌드

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

서버·Pi·웹은 실행 소스와 의존성 자료 수신 대기입니다. 과거 MD에 있는 외부 ZIP의 실행 명령을 현재 저장소 실행법으로 제공하지 않습니다. 소스를 받은 뒤 실제 `--help`·의존성·설정·포트·실행 결과를 확인해 이 절을 보완합니다.

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

브랜치는 작업 공간, Commit은 변경 기록, Push는 GitHub 업로드, PR은 검토 요청, Merge는 main 반영입니다.

1. 위 상태·진행 문서·개인 인계·관련 PR·실제 코드를 확인합니다. 미커밋 변경은 보존합니다. 임의 stash·reset·clean·복원은 하지 않습니다.
2. 같은 작업의 브랜치·PR이면 이어갑니다. 새 작업이고 작업 폴더가 깨끗할 때만 다음 명령을 사용합니다. 아래 브랜치 이름은 예시이며 이미 있으면 재생성하지 않습니다.

   ```powershell
   git fetch origin
   git switch -c docs/project-guide-20261115 origin/main
   ```

   로컬 main을 먼저 갱신하는 방식이라면 `git switch main` → `git pull --ff-only origin main` 후 새 브랜치를 만듭니다. 분기·충돌 시 강제로 맞추지 않습니다. 다른 작업이 남아 있으면 독립 worktree 등을 검토합니다.
3. 필요한 파일만 수정 → 변경에 맞는 기존 시험·빌드 검사 → 결과·한계·다음 작업 기록 → `git diff --check`, `git diff`, `git status` 검토 순서로 진행합니다.
4. **AI의 기본 종료는 로컬 검토입니다.** 사용자에게 변경·검증·제한 사항을 보여 주고 Commit·Push·PR 생성 지시를 기다립니다. 이번 요청도 여기서 멈춥니다.
5. 사용자가 해당 단계를 허용한 뒤에만 아래를 진행합니다. 경로는 이번 작업 파일만 명시하고 `git diff --cached`에서 신규 파일과 비밀정보도 확인합니다.

   ```powershell
   git add README.md AGENTS.md CLAUDE.md
   git diff --cached
   git commit -m "docs: 프로젝트 안내와 AI 작업 규칙 정리"
   git push -u origin HEAD
   ```

6. 같은 작업의 열린 PR이 있으면 갱신하고, 없으면 `main` 대상 **Draft PR(검토 전 초안)**을 만듭니다. [기존 양식](.github/pull_request_template.md)에 문제·변경·버전/기반 SHA·시험 결과·실물 여부·남은 위험을 담습니다. main 직접 Push·자동 Merge·자동 Merge 예약은 하지 않습니다.
7. 다른 팀원 검토와 필요한 검증을 마친 뒤 담당자가 Merge합니다. AI Merge에는 **대상 PR과 최신 변경에 대한 별도 명시 지시**가 필요합니다. 직전에 main·PR 최신 상태, 충돌, 검증 결과를 다시 확인합니다. “코드가 괜찮다”는 Merge 지시가 아닙니다.

빈 저장소이거나 최초 Commit이 없다면 위 절차를 사용할 수 없습니다. origin·기본 브랜치·초기 반입 범위를 확인하고 첫 Commit·원격 초기화 방법을 사용자와 정한 뒤 진행합니다. 이번 저장소에는 이미 이력이 있으므로 해당하지 않습니다.

## 8. 새 코드·ZIP·작업 MD 반영과 버전 기록

새 자료는 별도 위치에서 원본을 보존한 뒤 파일 목록·내용·기반 버전·변경 이력·검증 결과를 비교합니다. **파일 수정 시각, 파일명 날짜, `_1` 같은 숫자만으로 최신판을 고르지 않습니다.** 늦게 나온 미검증판은 최신 후보판으로 둡니다.

수신 → 원본 ZIP 이름·SHA-256 기록 → 비밀정보 확인 → 현재 코드와 diff → 기존 수정의 누락·되돌림 및 중복 소스 일치 검사 → 필요한 변경만 작업 브랜치에 반영 → 관련 시험 → 결과 기록 순서입니다. 기존 MD는 과거 결과를 보존하고 새 인계에서 정정·후속 결과를 연결합니다. 근거가 충돌하면 덮어쓰지 말고 두 판의 차이와 판단 대기 항목을 적습니다.

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

## 10. 기준 문서·인계와 다음 작업

우선 읽을 자료는 [11/6 OLED 변경·한계](firmware/stm32/docs/OLED_LIVE_1106_KO.md), [R1 검토 인계](docs/history/01_gwak_r1_recheck_20261104.md), [팀 전달·시험 순서](docs/history/gwak_team_notice_20261104.md), [Pi 모의시험 인계](docs/history/곽동규_라즈베리파이세팅_1028.md), [반입 목록](docs/IMPORT_MANIFEST.json)입니다. 각 문서의 대상 코드·시점을 확인합니다.

팀 공통 설계 후보는 [PR #2의 docs/00_master_design.md](https://github.com/gwak9770/share-key/blob/4bf62ea/docs/00_master_design.md)입니다. PR 내 관리자는 권기백으로 기재되어 있으나 **현재 팀 공통 문서 관리자의 확정 여부는 미확인**입니다. 기존 AGENTS 초안의 최종 검토·병합 담당 표기는 곽동규(`gwak9770`)이며 팀 전체의 현재 합의도 확인이 필요합니다. 공통 기준 변경은 담당자를 확인한 뒤 별도 PR과 팀 검토로 진행합니다.

PR #2는 별도 작업 MD 대신 PR 본문 기록을 제안합니다. 이번 요청은 개인별 인계 기록을 요구하므로 여기서는 **PR은 변경 검토, 개인 인계는 이어할 일 기록**으로 역할을 나눕니다. 기존 PR #2를 자동 수정하거나 그 제안을 이미 확정된 규칙으로 취급하지 않습니다. 두 지침을 병합하기 전 팀이 합의해야 합니다.

이번에는 README·AGENTS와 공동 사용을 위한 CLAUDE 연결 파일을 작성합니다. 현재 작업 브랜치에는 기존 CLAUDE가 없어 새로 만들었으며, PR #2의 별도 CLAUDE 제안은 보존했습니다. 다음 파일은 필요할 때 추가하는 제안이며 아직 만들지 않았습니다.

- `docs/STATUS.md`: 구성요소별 기준판·후보판·적용판과 검증 상태를 한곳에서 관리.
- `docs/handoff/곽동규.md`: 개인별 다음 작업·막힌 점·적용 기록. 다른 팀원도 각자 이름의 파일을 사용해 동시 수정을 줄임.
- `CHANGELOG.md`: 팀이 검토한 변경 이력. 실제 코드 SHA는 Git/PR과 연결.

`.github/pull_request_template.md`와 `.gitignore`는 이미 있으므로 새로 만들지 않았습니다. 추후 버전·시각·업로드 기록 항목 보완을 검토합니다.

다음 순서는 팀 최신 소스·실제 CubeIDE 프로젝트·적용 증거 수신 → PR #1 후보판과 현재 장비 diff → 공통 기준 관리자·PR #2 기록 방식 합의 → 필요한 빌드·업로드·실물 검증입니다. RTC·영속 저장·모터·기간 제한은 별도 설계·승인 없이 추가하지 않습니다. 현재 자료만으로 재부팅 뒤 제한 유지나 실제 각도·전력·지연 성능을 보장할 수 없습니다.

GitHub 조회에서 `main`의 `protected=false`를 확인했습니다. 문서 규칙은 GitHub 보호 설정을 대신하지 않습니다. 관리자에게 PR 필수, 다른 팀원 1명 리뷰, 추가 Commit 시 기존 승인 무효화, force push 차단을 제안합니다. 실제 지원 범위·설정은 별도 확인하며 **이번에는 저장소 설정을 바꾸지 않았습니다.** 자동 CI는 현재 실행 환경과 필요한 검사가 정해진 뒤 검토합니다.

이번 문서 작업에서는 로컬 링크·파일 경로, 코드와 상태 설명, 원본 AGENTS 대비 변경, 문서 diff와 공백 오류를 검토했습니다. 시험·빌드 도구 3개의 `--help` 실행은 성공했습니다. 공동 사용 설정은 공식 안내와 import 경로를 확인했으며 Claude Code 실행·로딩 시험은 미수행입니다. 펌웨어 시험·ARM/CubeIDE 빌드·업로드·실물 시험은 미수행입니다. 로컬 변경은 README·AGENTS·CLAUDE이며 stage·Commit·Push·PR 생성·Merge는 하지 않았습니다.
