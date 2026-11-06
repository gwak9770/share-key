# 팀 협업 안내

## 작업 단위와 브랜치

`main`은 검토된 통합 기준으로 유지하고, 작업마다 짧은 브랜치를 만듭니다. 팀원당 영구 브랜치보다 기능별 브랜치를 권장합니다.

| 작업 예시 | 브랜치 예시 | 검토할 내용 |
|---|---|---|
| 곽동규 Pi 중계·시험 지원 | `feat/gwak-pi-relay` | 판단 로직을 중계기에 추가하지 않았는지 |
| STM32·서보·OLED 통합 | `fix/stm32-oled-sync` | 핀·설정·실물 적용 이력 |
| 서버·웹 담당 작업 | `feat/server-key-sync` | 인증·동기화·발급 데이터 제외 |
| 조민선 기구·센서 시험 기록 | `docs/door-switch-test` | 스위치 상태와 재잠금 실측 |

이는 문서에서 확인한 작업 범위를 참고한 예시이며 새 역할 배정이나 발표자 지정이 아닙니다.

## 매번 작업하는 순서

처음에는 GitHub 저장소의 실제 주소로 `git clone`합니다. 아래 예시는 기존 clone 폴더에서 실행합니다.

```sh
git switch main
git pull --ff-only
git switch -c fix/stm32-oled-sync
# 코드와 관련 MD 수정 후 해당 파일만 추가
git add firmware/stm32/Core/Src/oled.c docs/history/작업기록.md
git diff --cached
git commit -m "fix: OLED 동기화 상태 갱신"
git push -u origin fix/stm32-oled-sync
```

`작업기록.md`는 실제 작성한 경로로 바꿉니다. GitHub에서 대상 `main`으로 PR을 만들고, 다른 팀원 한 명의 검토와 필요한 시험을 거쳐 병합합니다. 같은 파일을 동시에 수정하기 전 서로 작업 범위를 공유하세요. 충돌 시 양쪽 변경을 읽고 해결하며, 다른 사람의 변경을 통째로 덮거나 강제 푸시하지 않습니다.

## PR에 남길 기록

- 무엇을 바꿨고 어느 코드 버전을 기준으로 했는지
- A/C 방식, 한도, 설정, 보드·서버·Pi 버전
- 호스트 시험과 실물 시험을 구분한 결과
- 온라인 사용·복구, 오프라인 4회 허용 후 5·6회 거부, 온라인 복귀, 해제·재잠금, OLED 상태
- 실패 조건과 로그의 비밀정보 제거 여부

인증 `sharekey.c/h`, 공통 메시지, 핀 또는 `config.h` 변경은 관련 담당자가 함께 검토합니다. `sharekey.c/h` 쌍의 버전을 맞춥니다. 코드 변경과 설계 기록을 한 PR로 연결합니다.

## GitHub 관리자가 인증 후 할 일

1. 비공개 저장소로 생성하고 접근할 팀원의 정확한 GitHub 계정을 확인해 초대합니다.
2. `main`의 PR 검토 1명, 해결되지 않은 대화 해소, 강제 푸시·삭제 방지 규칙을 설정합니다. 비공개 저장소의 강제 보호 기능은 계정 요금제에 따라 지원 범위가 다르므로 실제 설정 화면에서 확인합니다.
3. 실제 실행이 확인된 CI만 필수 검사로 등록합니다. 현재 자동 검사나 보호 규칙을 설정했다고 간주하지 않습니다.
4. 실물 확인이 끝난 기준에 태그를 붙입니다. PC 시험 성공과 보드 검증 완료를 구분합니다.

참고: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
