공유 차 키 - 중간발표 코드 (A·C 방식)   Python 3.8+  (맥: python3.12)

파일                     누가 / 어디서
  common.py              공통: 메시지 형식·HMAC 계산
  server.py              권기백 / 노트북: 발급·취소·버전, 동기화 응답 (port 9000)
  app.py                 권기백 / 노트북: 주인·받는 사람 앱 스크립트
  core.py                곽동규 기준: 차량 판단 로직 (STM32 C 코드가 똑같이 동작해야 함)
  vehicle_sim.py         노트북 단독 시연용 가짜 차량 (Pi+STM32 한 번에, port 9100)
  pi_relay.py            김채희 / Pi: 앱↔STM32, STM32↔서버 줄 중계 (port 9100)
  stm32_sim.py           Nucleo 없을 때 STM32 대신 (가상 시리얼 port 9200)
  demo.py                A·C 자동 시연 + 결과 표
  web_app.py             권기백 / 노트북: 시연용 웹 화면 (app.py 를 그대로 호출, 설치 없음)
  hmac_vectors.*         곽동규 / STM32 HMAC 점검용 정답표

[1] 자동 시연
  python3 demo.py            가짜 차량 경로
  python3 demo.py --relay    앱 → Pi 중계 → STM32 흉내 경로

[2] 손으로 시연 - 가짜 차량 (터미널 3개, 모두 먼저 cd ~/Downloads/sharekey)
  탭1  python3 server.py
  탭2  python3 vehicle_sim.py --mode C
  탭3  python3 app.py issue 7 --limit 4 → register 7 → open 7 → net off
       → revoke 7 → open 7 (여러 번) → net on → open 7
       공격: python3 app.py tamper 7 / replay 7

[3] Pi 중계 시험 - Nucleo 없이 (터미널 4개)
  탭1  python3 server.py
  탭2  python3 stm32_sim.py --mode C
  탭3  python3 pi_relay.py --sim 127.0.0.1:9200
  탭4  app.py 명령은 [2]와 같음

[4] 실물 (노트북 + Pi + Nucleo)
  노트북  python3 server.py
  Pi      pip3 install pyserial
          python3 pi_relay.py --serial /dev/ttyACM0 --server <노트북IP>:9000
  노트북  python3 app.py ... --vehicle <PiIP>:9100
  (노트북·Pi 같은 핫스팟 2.4GHz. Nucleo 포트는 Pi에서 ls /dev/ttyACM* 로 확인)

다시 깨끗하게 시작:  서버·차량 끄고  rm -rf server_state.json keys
포트 사용 중 오류:   kill $(lsof -t -i :9000) $(lsof -t -i :9100) $(lsof -t -i :9200)

STM32 시리얼 규칙 (115200 8N1, 줄 끝 \n)
  받은 줄  RID|KEY... / RID|REQ... / RID|RESP...  → 같은 RID로 응답 한 줄
  2초마다  RID|SYNCREQ|VID|NONCE|VER  송신 (nonce 매번 새로)
  같은 RID의 SYNC 수신 → 검증·반영 → RID|SYNCACK|VID|VER
  다음 SYNCREQ 때까지 응답 없으면 오프라인 (횟수 복구 없음)
  '#'로 시작하는 줄 = 디버그 로그 (Pi가 화면에만 출력)

[5] 시연용 웹 화면 (11/3~, 터미널 대신 브라우저로 app.py 명령)
  탭1  python3 server.py
  (Pi) python3 pi_relay.py --serial /dev/ttyACM0 --server <노트북IP>:9000  → 보드 RESET
  탭2  python3 web_app.py --vehicle <Pi IP>:9100        → 브라우저 http://127.0.0.1:8080
       Windows 는 python web_app.py ...
  * 버튼 = app.py 명령: 키 발급(issue) / 키 취소(revoke) / 차량에 등록(register) / 문 열기(open)
           / 인증값 변조(tamper) / 응답 재전송(replay) / 끊기·다시 연결(net off·on)
  * 결과·사유·남은 횟수는 차량이 보낸 RES 그대로. "취소 후 열린 횟수"는 끊긴 상태에서 취소 뒤 허용 수
  * 온라인 open 뒤 2초 이상 지나서 끊기 (그 사이 인증된 동기화로 횟수가 다시 채워짐, 00 §6-4)
  * 끊은 뒤 OFFLINE 이 될 때까지 몇 초 기다렸다가 취소
  * --lan 을 붙이면 같은 Wi-Fi 휴대폰에서 http://<노트북IP>:8080 로 접속 가능.
    같은 망의 누구나 명령을 보낼 수 있으니 시연 때만 사용
  * 화면이 안 되면 지금처럼 터미널 app.py 로 하면 됨 (결과 같음)
