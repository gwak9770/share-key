"""가짜 차량 (STM32+Pi를 한 프로그램으로 흉내, 네트워크 직접 사용). 노트북 단독 시연용.
실행: python3 vehicle_sim.py --mode C      (A: 서버 취소만 / B: +기간 / C: +오프라인 횟수 / D: +기간·횟수)"""
import socketserver, threading, time, argparse
from common import *
from core import VehicleCore

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="C", choices="ABCD")
ap.add_argument("--port", type=int, default=VEHICLE_PORT)
ap.add_argument("--server", default=f"{SERVER_HOST}:{SERVER_PORT}")
ap.add_argument("--sync", type=float, default=2.0, help="동기화 주기(초)")
a = ap.parse_args()
SH, SP = a.server.split(":")


def log(*x):
    print(time.strftime("%H:%M:%S"), f"[차량 {a.mode}]", *x, flush=True)


core = VehicleCore(a.mode, log)


class App(socketserver.StreamRequestHandler):
    def handle(self):
        c = Conn(self.request)
        try:
            while True:
                rid, p = c.recv()
                r = core.handle(p)
                if r is not None:
                    c.send(rid, *r)
        except (ConnectionError, OSError, ValueError, IndexError):
            pass


def sync_loop():
    online = None
    while True:
        ok = False
        try:
            c = Conn.connect(SH, int(SP), timeout=1.0)
            p = c.request(*core.make_syncreq())
            if core.apply_sync(p):
                c.request("SYNCACK", f"{VID:08X}", f"{core.ver:08X}")
                ok = True
            c.close()
        except (OSError, ConnectionError, ValueError, IndexError):
            pass
        if ok != online:
            log("서버 연결됨" if ok else "서버 연결 끊김 → 오프라인 판단")
            online = ok
        time.sleep(a.sync)


if __name__ == "__main__":
    threading.Thread(target=sync_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("0.0.0.0", a.port), App)
    log(f"시작 port={a.port} 서버={a.server}")
    srv.serve_forever()
