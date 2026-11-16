"""앱 스크립트 (주인 앱 + 받는 사람 앱). 휴대폰 앱 대신 사용.
주인:   python app.py issue 7 --limit 4 --hours 24 --perm 3
        python app.py revoke 7
        python app.py net off|on          (시연용 서버↔차량 차단/복구)
받는 사람: python app.py register 7       (차량에 키 등록)
        python app.py open|start|return 7
공격:   python app.py tamper 7             (인증값 1비트 변조)
        python app.py replay 7             (직전 응답 재전송)"""
import argparse, json, os, time
from common import *

KEYDIR = "keys"
ap = argparse.ArgumentParser()
ap.add_argument("cmd")
ap.add_argument("arg", nargs="?")
ap.add_argument("--limit", type=int, default=4)
ap.add_argument("--hours", type=float, default=24)
ap.add_argument("--sit", type=int, default=2, help="0가족 1대리·발레 2렌트·카셰어링 3엄격")
ap.add_argument("--perm", type=int, default=3, help="1문 2시동 3문+시동")
ap.add_argument("--server", default=f"{SERVER_HOST}:{SERVER_PORT}")
ap.add_argument("--vehicle", default=f"{VEHICLE_HOST}:{VEHICLE_PORT}")


def kpath(kid):
    return os.path.join(KEYDIR, f"{kid:08X}.json")


def server(a, *f):
    h, p = a.server.split(":")
    c = Conn.connect(h, int(p)); r = c.request(*f); c.close(); return r


def vehicle(a):
    h, p = a.vehicle.split(":")
    return Conn.connect(h, int(p))


def use(a, kid, cmd, attack=None):
    k = json.load(open(kpath(kid)))
    ki = bytes.fromhex(k["ki"])
    c = vehicle(a)
    if attack == "replay":
        last = k.get("last_resp")
        if not last:
            print("재전송할 이전 응답 없음"); return None
        p = c.request(*last)
    else:
        p = c.request("REQ", f"{kid:08X}", f"{cmd:02X}")
        if p[0] == "CHAL":
            n = bytes.fromhex(p[2])
            tag = bytearray(auth_tag(ki, kid, cmd, n))
            if attack == "tamper":
                tag[0] ^= 0x01
            resp = ["RESP", f"{kid:08X}", f"{cmd:02X}", hx(n), hx(tag)]
            p = c.request(*resp)
            if attack is None:                   # 정상 응답만 보관 (재전송 공격 시험용)
                k["last_resp"] = resp
                json.dump(k, open(kpath(kid), "w"))
    c.close()
    _, _, res, why, rem = p
    left = "제한없음" if rem == "FF" else int(rem, 16)
    print(f"[앱] {CMD_NAME[cmd]}: {RESULT[res]} ({REASON[why]}) 남은횟수={left}")
    return res, why, rem


def main(argv=None):
    a = ap.parse_args(argv)
    kid = int(a.arg, 16) if a.arg and a.cmd not in ("net",) else None
    if a.cmd == "issue":
        exp = int(time.time() + a.hours * 3600)
        p = server(a, "ISSUE", f"{kid:08X}", f"{exp:08X}", f"{a.limit:02X}", f"{a.sit:02X}", f"{a.perm:02X}")
        os.makedirs(KEYDIR, exist_ok=True)
        json.dump({"key_line": ["KEY", *p[1:7]], "ki": p[7]}, open(kpath(kid), "w"))
        print(f"[주인 앱] KID={kid:08X} 발급 (한도 {a.limit}, {a.hours}시간)")
    elif a.cmd == "revoke":
        p = server(a, "REVOKE", f"{kid:08X}")
        print(f"[주인 앱] KID={kid:08X} 취소 요청 → 서버 VER {int(p[2],16)}")
    elif a.cmd == "net":
        server(a, "NET", "1" if a.arg == "on" else "0")
        print(f"[시연] 서버↔차량 {'연결' if a.arg == 'on' else '차단'}")
    elif a.cmd == "register":
        k = json.load(open(kpath(kid)))
        c = vehicle(a); p = c.request(*k["key_line"]); c.close()
        print(f"[앱] 차량 키 등록: {'성공' if p[0] == 'KEYOK' else '실패'}")
    elif a.cmd in ("open", "start", "return"):
        return use(a, kid, {"open": 1, "start": 2, "return": 3}[a.cmd])
    elif a.cmd in ("tamper", "replay"):
        return use(a, kid, 1, a.cmd)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
