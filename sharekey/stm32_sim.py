"""STM32 흉내 (Nucleo 없을 때 Pi 중계 시험용). 네트워크를 모르고 '시리얼 한 줄'만 주고받음.
pi_relay.py --sim 이 이 프로그램에 TCP로 붙어서 USB 시리얼 대신 사용.
실행: python3 stm32_sim.py --mode C

STM32가 시리얼로 하는 일 (곽동규 구현 기준):
  - 받은 줄  RID|KEY... / RID|REQ... / RID|RESP...  → 판단 후  같은RID|응답...  한 줄 송신
  - sync 초마다 스스로  RID|SYNCREQ|VID|NONCE|VER  송신 (nonce 는 매번 새로)
  - 같은 RID 로  SYNC...  가 오면 검증·반영 후  RID|SYNCACK|VID|VER  송신
  - 일정 시간 안에 SYNC 가 안 오면 오프라인으로 판단 (횟수 복구 없음)
  - '#' 로 시작하는 줄은 로그 (Pi 가 화면에만 출력)"""
import socket, threading, time, argparse, os
from common import *
from core import VehicleCore

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="C", choices="ABCD")
ap.add_argument("--port", type=int, default=9200)
ap.add_argument("--sync", type=float, default=2.0)
ap.add_argument("--flash-file", help="PC 플래시 모의 파일. 생략 시 기존 RAM 시연")
a = ap.parse_args()


def log(*x):
    print(time.strftime("%H:%M:%S"), f"[STM32 {a.mode}]", *x, flush=True)


from storage import FlashJournal, MemoryFlash
core = VehicleCore(a.mode, log, FlashJournal(MemoryFlash(path=a.flash_file)) if a.flash_file else None)
wlock = threading.Lock()
sync_rid = None


def main():
    global sync_rid
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", a.port)); srv.listen(1)
    log(f"시작 (가상 시리얼 port={a.port}) Pi 연결 대기")
    while True:
        s, _ = srv.accept()
        log("Pi 연결됨")
        f = s.makefile("r", encoding="ascii", newline="\n")
        alive = [True]

        def out(rid, fields):
            with wlock:
                s.sendall(("|".join([rid, *fields]) + "\n").encode())

        def ticker():
            global sync_rid
            while alive[0]:
                sync_rid = os.urandom(1).hex().upper()
                try:
                    request = core.make_syncreq()
                    if request is not None:
                        out(sync_rid, request)
                except OSError:
                    return
                time.sleep(a.sync)

        threading.Thread(target=ticker, daemon=True).start()
        try:
            for line in f:
                p = line.strip().split("|")
                rid, p = p[0], p[1:]
                if not p:
                    continue
                if p[0] == "SYNC" and rid == sync_rid:
                    sync_rid = None
                    if core.apply_sync(p):
                        out(rid, ["SYNCACK", f"{VID:08X}", f"{core.ver:08X}"])
                    continue
                r = core.handle(p)
                if r is not None:
                    out(rid, r)
        except (OSError, ValueError):
            pass
        alive[0] = False
        log("Pi 연결 끊김")


if __name__ == "__main__":
    main()
