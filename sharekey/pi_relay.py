"""라즈베리파이 중계 (김채희 담당). 판단은 하지 않고 줄을 그대로 전달만 함.
  앱 ──TCP 9100──▶ Pi ──USB 시리얼 115200──▶ STM32      (앱 요청/응답, RID 로 짝 맞춤)
  STM32 ──SYNCREQ──▶ Pi ──TCP──▶ 서버 ──SYNC──▶ Pi ──▶ STM32   (동기화 중계)

실행 (실물):   python3 pi_relay.py --serial /dev/ttyACM0 --server <노트북IP>:9000
실행 (시험):   python3 pi_relay.py --sim 127.0.0.1:9200        (stm32_sim.py 를 STM32 대신 사용)
실물은 pyserial 필요:  pip3 install pyserial
나중에 AI 점수는 여기서 RESP 를 보내기 전에 계산해 덧붙이는 위치에 넣음 (STM32 제한은 못 풂)."""
import socket, socketserver, threading, time, argparse, os
from common import VEHICLE_PORT, SERVER_HOST, SERVER_PORT

ap = argparse.ArgumentParser()
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--serial", help="예: /dev/ttyACM0 (Nucleo ST-LINK 가상 COM)")
g.add_argument("--sim", help="stm32_sim 주소 예: 127.0.0.1:9200")
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--port", type=int, default=VEHICLE_PORT)
ap.add_argument("--server", default=f"{SERVER_HOST}:{SERVER_PORT}")
ap.add_argument("--door-port", type=int, default=None, help="시연 화면용 문 상태 알림 포트 (기본: --port + 1 = 9101)")
a = ap.parse_args()
SH, SP = a.server.split(":")


def log(*x):
    print(time.strftime("%H:%M:%S"), "[Pi]", *x, flush=True)


class Link:
    """STM32 쪽 연결: 실물은 USB 시리얼, 시험은 TCP. 둘 다 '한 줄 쓰기/읽기'만 제공."""
    def __init__(self):
        self.wlock = threading.Lock()
        if a.serial:
            import serial                      # pip3 install pyserial
            self.ser = serial.Serial(a.serial, a.baud, timeout=None)
            self._w = self.ser.write
            self._r = self.ser.readline
        else:
            h, p = a.sim.split(":")
            self.sock = socket.create_connection((h, int(p)))
            f = self.sock.makefile("rb")
            self._w = self.sock.sendall
            self._r = f.readline

    def write(self, line):
        with self.wlock:
            self._w((line.rstrip("\r\n") + "\n").encode("ascii"))

    def read(self):
        b = self._r()
        if not b:
            raise ConnectionError("STM32 연결 끊김")
        return b.decode("ascii", "replace").strip()


link = Link()

# ---- 1106 시연 화면용: STM32 디버그 로그('#')에서 문 상태만 읽어 둔다 (판단·중계와 무관) ----
DOOR = {"state": "UNKNOWN", "seq": 0, "lock": "-"}     # seq = 문 닫힘 뒤 다시 잠그기 시도 횟수
dlock = threading.Lock()


def note_log(text):
    with dlock:
        if text.startswith("DOOR STATE OPEN"):
            DOOR["state"] = "OPEN"
        elif text.startswith("DOOR STATE CLOSED"):
            DOOR["state"] = "CLOSED"
        elif text.startswith("DOOR CLOSED -> LOCK ACT="):
            DOOR["seq"] += 1
            DOOR["lock"] = text.split("=", 1)[1].strip() or "-"


class DoorInfo(socketserver.StreamRequestHandler):
    """한 번 접속하면 'DOOR|상태|seq|결과' 한 줄을 주고 끊는다. 읽기만 함."""
    def handle(self):
        with dlock:
            line = f"DOOR|{DOOR['state']}|{DOOR['seq']}|{DOOR['lock']}\n"
        try:
            self.wfile.write(line.encode("ascii"))
        except OSError:
            pass
pending = {}                 # RID -> 앱 소켓 (응답을 돌려줄 곳)
plock = threading.Lock()


def to_server(line):
    """STM32의 SYNCREQ/SYNCACK 을 서버로. 응답이 오면 STM32 로 돌려줌. 단절이면 아무것도 안 보냄."""
    try:
        s = socket.create_connection((SH, int(SP)), timeout=1.5)
        s.sendall((line + "\n").encode())
        reply = s.makefile("r", encoding="ascii").readline().strip()
        s.close()
        if reply and "|SYNC|" in reply:
            link.write(reply)
    except OSError:
        pass                                     # 서버 단절 → STM32 가 시간 초과로 오프라인 판단


def serial_reader():
    while True:
        try:
            line = link.read()
        except (ConnectionError, OSError) as e:
            log("STM32 연결 끊김 — 케이블/전원 확인 후 다시 실행:", e)
            os._exit(1)
        if not line:
            continue
        if line.startswith("#"):                 # STM32 디버그 로그
            log("STM32:", line[1:].strip()); note_log(line[1:].strip()); continue
        parts = line.split("|")
        if len(parts) < 2:
            log("형식 오류 줄 무시:", line); continue
        rid, kind = parts[0], parts[1]
        if kind in ("SYNCREQ", "SYNCACK"):
            threading.Thread(target=to_server, args=(line,), daemon=True).start()
            continue
        with plock:
            dst = pending.pop(rid, None)
        if dst:
            try:
                dst.sendall((line + "\n").encode())
            except OSError:
                pass
        else:
            log("받을 앱이 없는 응답:", line)


class App(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            for raw in self.rfile:
                line = raw.decode("ascii", "replace").strip()
                if not line:
                    continue
                rid = line.split("|", 1)[0]
                with plock:
                    pending[rid] = self.request
                link.write(line)                  # 내용은 건드리지 않고 그대로 전달
        except OSError:
            pass


def heartbeat():
    """STM32 제어 보호용 생존 신호 (00 v0.3 §5). 250ms마다, 응답 없음. 2초 끊기면 STM32가 모터 정지."""
    n = 0
    while True:
        try:
            link.write(f"{n % 256:02X}|HB")
        except OSError:
            pass
        n += 1
        time.sleep(0.25)


if __name__ == "__main__":
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("0.0.0.0", a.port), App)
    dport = a.door_port or a.port + 1
    try:
        dsrv = socketserver.ThreadingTCPServer(("0.0.0.0", dport), DoorInfo)
        threading.Thread(target=dsrv.serve_forever, daemon=True).start()
        log(f"문 상태 알림 port={dport} (시연 화면용, 읽기 전용)")
    except OSError as e:
        log("문 상태 알림 포트 열기 실패 (중계는 정상):", e)
    log(f"시작 앱 port={a.port} STM32={'시리얼 ' + a.serial if a.serial else '시뮬 ' + a.sim} 서버={a.server}")
    srv.serve_forever()
