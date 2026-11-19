"""T01~T03 반복 시험 (00 §10, 02 §6). 앱 대신 같은 메시지를 Pi 중계(또는 가짜 차량)에 반복해서 보낸다.

실물 (김채희):
    python3 server.py                                   (노트북, server_state.json 새로 시작 권장)
    python3 pi_relay.py --serial /dev/ttyACM0 --server <노트북IP>:9000   (Pi)
    python3 repeat_t01_t03.py --vehicle <PiIP>:9100 --server <노트북IP>:9000 --sync 2
PC 모의:
    python3 server.py & python3 stm32_sim.py --mode C --sync 1 & python3 pi_relay.py --sim 127.0.0.1:9200 &
    python3 repeat_t01_t03.py --sync 1

시험 (기본 --count 100)
  T01-normal   정상 문열기 count회 → 모두 허용(00)
  T01-tamper   인증값 1비트 변조 count회 → 모두 거부(01)
  T01-replay   직전 정상 응답 재전송 count회 → 모두 거부(02)
  T01-perm     문 권한(01)만 있는 키로 시동(02) count회 → 모두 거부(06)
  T02-count    N=4 키, 서버 차단 상태에서 4회 허용 후 5번째 거부(05). --t02-rounds 번 반복
               (라운드 사이 서버 연결 → 동기화로 횟수 복구 → 다시 차단)
  T03-revoked  취소 후 동기화되면 문열기 count회 → 모두 거부(03)
  T03-oldsync  취소 전에 받아 둔 서명된 옛 SYNC를 차량에 다시 넣은 뒤 문열기, count회
               → 문열기 모두 거부(03)  (옛 SYNC로 취소가 풀리지 않는지)
T02의 만료 직전·직후 30회는 B·D 방식과 RTC가 필요해 이 스크립트에서 하지 않는다(미수행으로 기록).

주의
  - 실행 1회에 키 3개를 새로 발급·등록한다. 차량은 키를 최대 8개 보관하고 플래시 판은
    재부팅해도 남으므로, 보드는 2회 실행마다 저장 상태를 비워야 한다(방법은 곽동규 확인).
  - 차량이 C 방식이어야 T02가 의미 있다. A 방식이면 T02는 FAIL로 나온다.
  - 문열기 허용마다 서보가 움직인다. --delay로 간격을 둔다.
  - 발급 키는 파일로 저장하지 않는다(keys/ 미사용).
"""
import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Conn, SERVER_HOST, SERVER_PORT, VEHICLE_HOST, VEHICLE_PORT, auth_tag, hx)  # noqa: E402

ap = argparse.ArgumentParser(description="T01~T03 반복 시험")
ap.add_argument("--server", default=f"{SERVER_HOST}:{SERVER_PORT}")
ap.add_argument("--vehicle", default=f"{VEHICLE_HOST}:{VEHICLE_PORT}")
ap.add_argument("--count", type=int, default=100, help="T01·T03 각 시험 반복 수")
ap.add_argument("--t02-rounds", type=int, default=10, help="T02 반복 라운드 수")
ap.add_argument("--sync", type=float, default=2.0, help="차량 동기화 주기(초). 기다리는 시간 계산용")
ap.add_argument("--delay", type=float, default=0.2, help="시도 사이 간격(초)")
ap.add_argument("--only", default="T01,T02,T03", help="돌릴 시험, 예: T01 또는 T01,T03")
ap.add_argument("--kid-base", type=lambda v: int(v, 16), default=None,
                help="키 번호 시작값(16진수). 기본은 실행 시각으로 정함")
a = ap.parse_args()


def addr(s):
    h, p = s.split(":")
    return h, int(p)


def server(*f):
    c = Conn.connect(*addr(a.server))
    try:
        return c.request(*f)
    finally:
        c.close()


def vehicle(*f, timeout=3.0):
    c = Conn.connect(*addr(a.vehicle), timeout=timeout)
    try:
        return c.request(*f)
    finally:
        c.close()


class Key:
    def __init__(self, kid, limit, perm, hours=24):
        exp = int(time.time() + hours * 3600)
        p = server("ISSUE", f"{kid:08X}", f"{exp:08X}", f"{limit:02X}", "02", f"{perm:02X}")
        if p[0] != "ISSUED":
            raise SystemExit(f"발급 실패 KID={kid:08X}: {p}")
        self.kid, self.ki, self.key_line = kid, bytes.fromhex(p[7]), ["KEY", *p[1:7]]
        r = vehicle(*self.key_line)
        if r[0] != "KEYOK":
            raise SystemExit(f"차량 등록 실패 KID={kid:08X}: {r} (차량 키 8개 초과·저장 장애인지 확인)")
        self.last_resp = None

    def use(self, cmd, attack=None):
        """(결과, 사유). attack: None / tamper / replay"""
        k = f"{self.kid:08X}"
        if attack == "replay":
            p = vehicle(*self.last_resp)
        else:
            p = vehicle("REQ", k, f"{cmd:02X}")
            if p[0] == "CHAL":
                n = bytes.fromhex(p[2])
                tag = bytearray(auth_tag(self.ki, self.kid, cmd, n))
                if attack == "tamper":
                    tag[0] ^= 0x01
                resp = ["RESP", k, f"{cmd:02X}", hx(n), hx(tag)]
                p = vehicle(*resp)
                if attack is None:
                    self.last_resp = resp
        if p[0] != "RES":
            return "?", "|".join(p)
        return p[2], p[3]


results = []   # (시험, 기대, 맞음, 시도, 틀린 예)


def check(name, expect, outcomes):
    """expect = (결과, 사유). 사유가 None이면 결과만 본다."""
    ok = [o for o in outcomes if o[0] == expect[0] and (expect[1] is None or o[1] == expect[1])]
    bad = [o for o in outcomes if o not in ok]
    wrong_allow = sum(1 for o in outcomes if o[0] == "A") if expect[0] != "A" else None
    results.append((name, f"{expect[0]}({expect[1] or '*'})", len(ok), len(outcomes), wrong_allow, bad[:3]))
    tag = "PASS" if not bad else "FAIL"
    print(f"{tag} {name}: {len(ok)}/{len(outcomes)}" + (f"  잘못 허용 {wrong_allow}" if wrong_allow else "")
          + (f"  예: {bad[:3]}" if bad else ""), flush=True)


def repeat(fn):
    out = []
    for _ in range(a.count):
        out.append(fn())
        time.sleep(a.delay)
    return out


def net(on):
    server("NET", "1" if on else "0")
    # 차단: 진행 중이던 동기화가 끝나도록 / 연결: 다음 동기화가 반영되도록 주기 2.5배를 기다린다
    time.sleep(a.sync * 2.5)


def t01(base):
    k = Key(base, 200, 0x03)
    check("T01-normal 정상 문열기", ("A", "00"), repeat(lambda: k.use(1)))
    check("T01-tamper 변조", ("D", "01"), repeat(lambda: k.use(1, "tamper")))
    check("T01-replay 재전송", ("D", "02"), repeat(lambda: k.use(1, "replay")))
    p = Key(base + 1, 200, 0x01)
    check("T01-perm 권한 초과(문 키로 시동)", ("D", "06"), repeat(lambda: p.use(2)))


def t02(base):
    k = Key(base + 2, 4, 0x03)
    time.sleep(a.sync * 1.5)
    outs = []
    for _ in range(a.t02_rounds):
        net(False)
        r = []
        for _ in range(5):
            r.append(k.use(1))
            time.sleep(a.delay)
        outs.append(r)
        net(True)
    good = sum(1 for r in outs if [x[0] for x in r] == ["A"] * 4 + ["D"] and r[4][1] == "05")
    bad = [r for r in outs if not ([x[0] for x in r] == ["A"] * 4 + ["D"] and r[4][1] == "05")]
    wrong = sum(1 for r in outs if r[4][0] == "A")
    results.append(("T02-count N=4 (4회 허용, 5번째 05)", "AAAA+D(05)", good, len(outs), wrong, bad[:2]))
    print(f"{'PASS' if not bad else 'FAIL'} T02-count: {good}/{len(outs)} 라운드"
          + (f"  예: {bad[:2]}" if bad else ""), flush=True)
    return k


def t03(base, k=None):
    k = k or Key(base + 2, 4, 0x03)
    # 취소 전 서명된 SYNC를 받아 둔다 (그 키가 유효로 적힌 옛 응답)
    req = server("SYNCREQ", "0000CAFE", hx(os.urandom(16)), "00000000")
    if req[0] != "SYNC":
        raise SystemExit(f"옛 SYNC 받기 실패(서버 NET 차단 상태인지 확인): {req}")
    old_sync = req
    server("REVOKE", f"{k.kid:08X}")
    time.sleep(a.sync * 2.5)
    check("T03-revoked 동기화 뒤 취소 키", ("D", "03"), repeat(lambda: k.use(1)))

    def inject_then_open():
        try:
            vehicle(*old_sync, timeout=1.0)     # 차량은 응답하지 않거나 ERR. 둘 다 괜찮다
        except (OSError, ValueError, ConnectionError):
            pass
        return k.use(1)
    check("T03-oldsync 옛 SYNC 재전송 뒤 문열기", ("D", "03"), repeat(inject_then_open))


def main():
    base = a.kid_base if a.kid_base is not None else (0x7E000000 | (int(time.time()) & 0xFFFF) << 4)
    only = {s.strip().upper() for s in a.only.split(",")}
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"시작 {started}  vehicle={a.vehicle} server={a.server} count={a.count} KID {base:08X}~{base + 2:08X}",
          flush=True)
    try:
        server("NET", "1")
        if "T01" in only:
            t01(base)
        k = t02(base) if "T02" in only else None
        if "T03" in only:
            t03(base, k)
    except (OSError, ConnectionError, socket.timeout) as e:
        print("연결 오류:", e, "— 서버·Pi 중계·차량 실행 상태와 주소를 확인")
    finally:
        try:
            server("NET", "1")
        except OSError:
            pass
    print(f"\n## T01~T03 반복 결과 ({started}, 끝 {time.strftime('%H:%M:%S')})\n")
    print("| 시험 | 기대 | 맞음 / 시도 | 잘못 허용 | 판정 |")
    print("|---|---|---|---|---|")
    for name, exp, good, n, wrong, _ in results:
        print(f"| {name} | {exp} | {good}/{n} | {'-' if wrong is None else wrong} | "
              f"{'PASS' if good == n else 'FAIL'} |")
    if "T02" in only:
        print("| T02 만료 직전·직후 30회 | B·D + RTC 필요 | - | - | 미수행 |")
    sys.exit(0 if results and all(g == n for _, _, g, n, _, _ in results) else 1)


if __name__ == "__main__":
    main()
