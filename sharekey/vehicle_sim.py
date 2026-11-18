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
ap.add_argument("--flash-file", help="PC 플래시 모의 파일. 생략 시 기존 RAM 시연")
a = ap.parse_args()
SH, SP = a.server.split(":")


def log(*x):
    print(time.strftime("%H:%M:%S"), f"[차량 {a.mode}]", *x, flush=True)


from storage import FlashJournal, MemoryFlash
core = VehicleCore(a.mode, log, FlashJournal(MemoryFlash(path=a.flash_file)) if a.flash_file else None)


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
    while True:
        started = time.monotonic()
        request = core.make_syncreq()
        if request is None:
            time.sleep(a.sync)
            continue
        c = None
        try:
            c = Conn.connect(SH, int(SP), timeout=1.0)
            p = c.request(*request)
            if core.apply_sync(p):
                c.request("SYNCACK", f"{VID:08X}", f"{core.ver:08X}")
        except (OSError, ConnectionError, ValueError, IndexError):
            pass
        finally:
            if c is not None:
                c.close()
        # Count at scheduled request boundaries, not timeout + sync seconds.
        time.sleep(max(0, a.sync - (time.monotonic() - started)))


if __name__ == "__main__":
    threading.Thread(target=sync_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("0.0.0.0", a.port), App)
    log(f"시작 port={a.port} 서버={a.server}")
    srv.serve_forever()
