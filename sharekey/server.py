"""노트북 서버: 키 발급·취소·버전 관리, 차량 동기화 응답.
실행: python server.py
NET 0 이면 차량의 동기화 요청에 응답하지 않음 (서버↔차량 단절 시연용. 실제 실험은 방화벽으로 대체 가능)."""
import socketserver, threading, json, os, time, copy
from common import *

STATE_FILE = "server_state.json"
lock = threading.RLock()
st = {"ver": 0, "keys": {}, "net": 1}
if os.path.exists(STATE_FILE):
    st = json.load(open(STATE_FILE))


def save():
    temporary = STATE_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(st, stream, indent=1)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, STATE_FILE)


def log(*a):
    print(time.strftime("%H:%M:%S"), "[서버]", *a, flush=True)


def _handle(c, p):
    kind = p[0]
    with lock:
        if kind == "RISSUE":
            if len(p) != 6:
                return ["RFAIL", "FF"]
            try:
                if any(len(v) != n for v, n in zip(p[1:], (8, 32, 8, 8, 64))):
                    raise ValueError("길이")
                vid, nonce = int(p[1], 16), bytes.fromhex(p[2])
                kid, newkid, proof = int(p[3], 16), int(p[4], 16), bytes.fromhex(p[5])
                if vid != VID:
                    return ["RFAIL", "FF"]
                if not eq(recovery_proof(kid, newkid, nonce), proof):
                    return ["RFAIL", "01"]
            except (ValueError, OverflowError):
                return ["RFAIL", "FF"]
            request_id = f"{kid:08X}:{newkid:08X}:{hx(nonce)}"
            previous = st.get("recoveries", {}).get(request_id)
            if previous is not None:
                current = st["keys"][f"{newkid:08X}"]
                if current["state"] != 0 or time.time() > current["exp"]:
                    return ["RFAIL", "04" if current["state"] == 0 else "03"]
                return previous
            old = st["keys"].get(f"{kid:08X}")
            if old is None:
                return ["RFAIL", "08"]
            if old["state"] != 0:
                return ["RFAIL", "09" if old["state"] == 2 else "03"]
            if time.time() > old["exp"]:
                return ["RFAIL", "04"]
            if f"{newkid:08X}" in st["keys"] or len(st["keys"]) >= 16:
                return ["RFAIL", "FF"]
            fresh = dict(old)
            fresh["state"] = 0
            st["keys"][f"{newkid:08X}"] = fresh
            old["state"] = 1
            st["ver"] += 1
            tag = recovery_tag(st["ver"], nonce, newkid, fresh["exp"], fresh["limit"], fresh["sit"], fresh["perm"])
            response = ["RISSUED", f"{VID:08X}", hx(nonce), f"{st['ver']:08X}", f"{newkid:08X}",
                        f"{fresh['exp']:08X}", f"{fresh['limit']:02X}", f"{fresh['sit']:02X}",
                        f"{fresh['perm']:02X}", hx(tag), hx(derive(newkid)),
                        hx(key_tag(newkid, fresh["exp"], fresh["limit"], fresh["sit"], fresh["perm"]))]
            st.setdefault("recoveries", {})[request_id] = response
            save()
            return response
        if kind == "RETURN":
            if len(p) != 3:
                return ["ERR", "FF"]
            kid = int(p[1], 16)
            k = st["keys"].get(f"{kid:08X}")
            if k is None:
                return ["ERR", "08"]
            expected = H(derive(kid), b"RETURN" + u32(VID) + u32(kid))
            if not eq(expected, bytes.fromhex(p[2])):
                return ["ERR", "01"]
            if k["state"] == 0:
                k["state"] = 2
                st["ver"] += 1
                save()
            return ["RETURNED", f"{kid:08X}"]
        if kind == "ISSUE":                       # ISSUE|KID|EXP|LIMIT|SIT|PERM
            kid, exp = int(p[1], 16), int(p[2], 16)
            limit, sit, perm = (int(x, 16) for x in p[3:6])
            if f"{kid:08X}" not in st["keys"] and len(st["keys"]) >= 16:
                return ["ERR", "FF"]
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
            entries = sorted((int(k, 16), 1 if v["state"] else 0) for k, v in st["keys"].items())
            tag = sync_tag(st["ver"], nonce, entries)
            return ["SYNC", f"{VID:08X}", f"{st['ver']:08X}", p[2], f"{len(entries):02X}",
                    enc_entries(entries), hx(tag)]
        if kind == "SYNCACK":
            return ["OK"]
    return ["ERR", "FF"]


def handle(c, p):
    # A failed durable write must not leave an in-memory "issued" result that
    # an idempotent retry could return without a persisted server state.
    with lock:
        before = copy.deepcopy(st)
        try:
            return _handle(c, p)
        except OSError:
            st.clear()
            st.update(before)
            raise


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
