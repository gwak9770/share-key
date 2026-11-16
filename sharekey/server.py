"""노트북 서버: 키 발급·취소·버전 관리, 차량 동기화 응답.
실행: python server.py
NET 0 이면 차량의 동기화 요청에 응답하지 않음 (서버↔차량 단절 시연용. 실제 실험은 방화벽으로 대체 가능)."""
import socketserver, threading, json, os, time
from common import *

STATE_FILE = "server_state.json"
lock = threading.Lock()
st = {"ver": 0, "keys": {}, "net": 1}
if os.path.exists(STATE_FILE):
    st = json.load(open(STATE_FILE))


def save():
    json.dump(st, open(STATE_FILE, "w"), indent=1)


def log(*a):
    print(time.strftime("%H:%M:%S"), "[서버]", *a, flush=True)


def handle(c, p):
    kind = p[0]
    with lock:
        if kind == "ISSUE":                       # ISSUE|KID|EXP|LIMIT|SIT|PERM
            kid, exp = int(p[1], 16), int(p[2], 16)
            limit, sit, perm = (int(x, 16) for x in p[3:6])
            st["keys"][f"{kid:08X}"] = {"exp": exp, "limit": limit, "sit": sit, "perm": perm, "state": 0}
            st["ver"] += 1; save()
            tag = key_tag(kid, exp, limit, sit, perm)
            log(f"발급 KID={kid:08X} 한도={limit} 권한={perm:02X} → VER {st['ver']}")
            return ["ISSUED", f"{kid:08X}", f"{exp:08X}", f"{limit:02X}", f"{sit:02X}", f"{perm:02X}",
                    hx(tag), hx(derive(kid))]          # 마지막 값 k_i 는 받는 사람 앱에만 전달
        if kind == "REVOKE":                      # REVOKE|KID
            k = st["keys"].get(p[1].upper())
            if not k:
                return ["ERR", "08"]
            k["state"] = 1; st["ver"] += 1; save()
            log(f"취소 KID={p[1]} → VER {st['ver']}")
            return ["REVOKED", p[1].upper(), f"{st['ver']:08X}"]
        if kind == "NET":                         # NET|0 or NET|1
            st["net"] = int(p[1]); save()
            log("서버↔차량", "연결" if st["net"] else "차단")
            return ["NET", p[1]]
        if kind == "SYNCREQ":                     # SYNCREQ|VID|NONCE|VER
            if not st["net"]:
                return None                       # 단절: 응답 없이 끊음
            nonce = bytes.fromhex(p[2])
            entries = sorted((int(k, 16), v["state"]) for k, v in st["keys"].items())
            tag = sync_tag(st["ver"], nonce, entries)
            return ["SYNC", f"{VID:08X}", f"{st['ver']:08X}", p[2], f"{len(entries):02X}",
                    enc_entries(entries), hx(tag)]
        if kind == "SYNCACK":
            return ["OK"]
    return ["ERR", "FF"]


class H_(socketserver.StreamRequestHandler):
    def handle(self):
        c = Conn(self.request)
        try:
            while True:
                rid, p = c.recv()
                r = handle(c, p)
                if r is None:
                    return
                c.send(rid, *r)
        except (ConnectionError, OSError, ValueError, IndexError):
            pass


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else SERVER_PORT
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("0.0.0.0", port), H_)
    log(f"시작 port={port} VER={st['ver']} 연결={'O' if st['net'] else 'X'}")
    srv.serve_forever()
