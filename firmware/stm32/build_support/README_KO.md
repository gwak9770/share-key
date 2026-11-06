# F429 ARM 컴파일과 링크 검증

이 폴더는 소스 패키지를 STM32F429ZI 대상으로 컴파일하고 링크하는 별도 하네스다. 팀의 정상 동작한 `sharekey_f429` CubeIDE 프로젝트에서는 기존 생성 파일을 유지한다. 이 폴더의 `main.c` 대체 파일, 링커, HAL 설정을 기존 프로젝트에 함께 추가하지 않는다.

## 실행

Python 3.11 이상, Arm GNU Toolchain, STM32CubeF4 1.28.3의 전체 `Drivers` 디렉터리가 필요하다. 스크립트는 다운로드, 설치, 보드 접속, 펌웨어 업로드를 하지 않는다.

```text
python tools/check_arm_build.py --cube-root "<STM32Cube_FW_F4_V1.28.3>" --gcc "<arm-none-eabi-gcc 경로>" --variant default
python tools/check_arm_build.py --cube-root "<STM32Cube_FW_F4_V1.28.3>" --gcc "<arm-none-eabi-gcc 경로>" --variant all-features
python tools/check_arm_build.py --cube-root "<STM32Cube_FW_F4_V1.28.3>" --gcc "<arm-none-eabi-gcc 경로>" --variant policy-a
python tools/check_arm_build.py --cube-root "<STM32Cube_FW_F4_V1.28.3>" --gcc "<arm-none-eabi-gcc 경로>" --variant servo
```

`--out <경로>`로 결과 디렉터리를 지정할 수 있다. 기본 경로는 `build-arm/<variant>`이다. ELF, HEX, BIN, map, 빌드 로그, 소스 해시와 검증 결과 JSON을 만든다. 이 결과물은 검증용이며 실제 프로젝트의 배선 및 설정 확인을 대신하지 않는다.

## 변형

| 변형 | 검사 범위 |
|---|---|
| `default` | 기본 C 방식, 서보 활성화, 끝점 센서·모터·RTC·OLED 등 기본 비활성 설정 |
| `all-features` | 끝점 센서, 모터, RTC, OLED, 반납 버튼, watchdog, 시험 명령의 조건부 코드까지 컴파일 |
| `policy-a` | 인증 경로를 A 방식으로 빌드 |
| `servo` | 독립 서보 시험 모듈과 타이머 클록 계산기를 링크 |

`all-features` 통과는 해당 기능의 실물 동작이나 최종 정책 연결 완료를 뜻하지 않는다. 조건부 코드에 컴파일·링크 오류가 없는지 확인하는 검사다.

## 하네스 설정

- STM32F429ZI, Cortex-M4, `fpv4-sp-d16`, hard-float.
- HSE 8 MHz bypass, PLL M=8/N=336/P=2/Q=7.
- SYSCLK 168 MHz, APB1 42 MHz, APB2 84 MHz, RNG 48 MHz.
- USART3 PD8/PD9, 115200 8N1, 인터럽트 수신.
- Flash 2 MiB, 일반 SRAM 192 KiB, 초기 스택 주소 `0x20030000`.
- CCM SRAM은 별도 주소 영역이므로 일반 SRAM 길이에 합치지 않는다.
- 내부 Flash 저장용 영역은 이 하네스에 예약하지 않았다.

## 의존성 기준

- [STM32CubeF4 v1.28.3](https://github.com/STMicroelectronics/STM32CubeF4/tree/v1.28.3)
- HAL 의존성 커밋: `b6f0ed3829f3829eb358a2e7417d80bba1a42db7`
- CMSIS Device F4 의존성 커밋: `3c77349ce04c8af401454cc51f85ea9a50e34fc1`
- CMSIS 코어 헤더는 같은 CubeF4 v1.28.3의 `Drivers/CMSIS/Include`를 사용한다.

검증 하네스와 사용자 CubeIDE 프로젝트는 별개다. 실제 CubeIDE 적용에서는 해당 프로젝트의 생성 코드와 중복 정의가 없는지 확인하고 보드에 다운로드해 시험해야 한다.
