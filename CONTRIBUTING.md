# 팀 협업 안내

## 작업 단위와 브랜치

`main`은 검토된 통합 기준으로 유지하고, 작업마다 짧은 브랜치를 만듭니다. 팀원당 영구 브랜치보다 기능별 브랜치를 권장합니다.

| 작업 예시 | 브랜치 예시 | 검토할 내용 |
|---|---|---|
| 김채희 Pi 중계·시험 | `feat/pi-relay` | 판단 로직을 중계기에 추가하지 않았는지 |
| 곽동규 내부 플래시 저장 | `feat/flash-save` | 저장·재부팅 동작을 실물 확인 전 완료로 쓰지 않았는지 |
| STM32·서보·OLED 통합 | `fix/stm32-oled-sync` | 핀·설정·실물 적용 이력 |
| 서버·웹 담당 작업 | `feat/server-key-sync` | 인증·동기화·발급 데이터 제외 |
| 조민선 기구·센서 시험 기록 | `docs/door-switch-test` | 스위치 상태와 재잠금 실측 |

이는 `CLAUDE.md` 9절의 주로 맡는 영역을 참고한 예시이며 새 역할 배정이나 발표자 지정이 아닙니다. 팀원 이름만으로 된 영구 브랜치는 만들지 않습니다.

## 매번 작업하는 순서

처음에는 GitHub 저장소의 실제 주소로 `git clone`합니다. 아래 예시는 기존 clone 폴더에서 실행합니다.

```sh
git switch main
git pull --ff-only
git switch -c fix/stm32-oled-sync
# 코드 수정 후 바꾼 파일만 추가
git add firmware/stm32/Core/Src/oled.c
git diff --cached
git commit -m "fix: OLED 동기화 상태 갱신"
git push -u origin fix/stm32-oled-sync
```

커밋 메시지는 `영어 접두어: 한국어 설명` 한 줄입니다. 접두어는 `feat`, `fix`, `docs`, `test`, `chore`입니다. 작업 기록은 별도 MD 대신 PR 본문에 씁니다. GitHub에서 대상 `main`으로 PR을 만들고, 다른 팀원 한 명의 검토와 필요한 시험을 거쳐 병합한 뒤 브랜치를 지웁니다. 질문·요청·버그는 Issue로 올리고 담당자를 지정합니다. 같은 파일을 동시에 수정하기 전 서로 작업 범위를 공유하세요. 충돌 시 양쪽 변경을 읽고 해결하며, 다른 사람의 변경을 통째로 덮거나 강제 푸시하지 않습니다.

## PR에 남길 기록

PR 본문은 `.github/pull_request_template.md`의 7항목 양식(`CLAUDE.md` 7절, 자세한 양식은 `docs/01_report_template.md`)으로 씁니다. 특히 아래 내용을 빠뜨리지 않습니다.

- 무엇을 바꿨고 어느 00 버전·코드 버전을 기준으로 했는지
- A/C 방식, 한도, 설정, 보드·서버·Pi 버전
- 호스트 시험과 실물 시험을 구분한 결과
- 온라인 사용·복구, 오프라인 4회 허용 후 5·6회 거부, 온라인 복귀, 해제·재잠금, OLED 상태
- 실패 조건과 로그의 비밀정보 제거 여부

인증·판단 `sharekey.c/h`·`sk_crypto.c/h`, 공통 메시지, 핀 또는 `config.h` 변경은 권기백이 확인합니다. 판단 코드는 `firmware/stm32/` 한 곳에서 관리하고, `sharekey.c/h` 쌍의 버전과 `vendor/sharekey/SOURCE_MANIFEST.json` 해시를 같은 커밋에서 맞춥니다. 메시지 형식·판단 규칙·핀 배치를 바꿔야 하면 코드보다 `docs/00_master_design.md`를 먼저 PR로 고칩니다.

## GitHub 관리자가 인증 후 할 일

1. 비공개 저장소로 생성하고 접근할 팀원의 정확한 GitHub 계정을 확인해 초대합니다.
2. `main`의 PR 검토 1명, 해결되지 않은 대화 해소, 강제 푸시·삭제 방지 규칙을 설정합니다. 비공개 저장소의 강제 보호 기능은 계정 요금제에 따라 지원 범위가 다르므로 실제 설정 화면에서 확인합니다.
3. 실제 실행이 확인된 CI만 필수 검사로 등록합니다. 현재 자동 검사나 보호 규칙을 설정했다고 간주하지 않습니다.
4. 실물 확인이 끝난 기준에 태그를 붙입니다. PC 시험 성공과 보드 검증 완료를 구분합니다.

참고: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
