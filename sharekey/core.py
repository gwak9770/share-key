"""차량 판단 로직 (STM32가 할 일을 그대로 옮긴 기준 구현).
vehicle_sim.py(네트워크 직접)와 stm32_sim.py(시리얼 흉내) 둘 다 이 코드를 씀.
곽동규: STM32 C 코드는 이 파일의 handle / decide / make_syncreq / apply_sync 와 같게 동작하면 됨."""
import os, time, threading
from common import *


class VehicleCore:
    def __init__(self, mode="C", log=print):
        self.use_exp = mode in "BD"
        self.use_cnt = mode in "CD"
        self.mode = mode
        self.log = log
        self.lock = threading.Lock()
        self.keys = {}       # kid -> dict(exp, limit, remaining, sit, perm, state[0유효 1취소 2반납])
        self.nonces = {}     # kid -> (nonce, 발급시각)
        self.ver = 0
        self.sync_nonce = None

    def actuate(self, cmd, rem):
        left = "∞" if rem is None else rem
        self.log(f"▶ {CMD_NAME[cmd]} 실행 (LCD: ALLOW / LEFT {left})")

    def decide(self, kid, cmd, nonce, tag):
        """판단 순서: 등록 → 인증값 → nonce → 취소/반납 → 기간 → (반납) → 권한 → 횟수 → 실행"""
        k = self.keys.get(kid)
        pend = self.nonces.pop(kid, None)          # nonce 는 성공/실패 관계없이 1회용
        if not k:
            return "D", "08", k
        if not eq(auth_tag(derive(kid), kid, cmd, nonce), tag):
            return "D", "01", k
        if not pend or pend[0] != nonce or time.time() - pend[1] > NONCE_LIFE:
            return "D", "02", k
        if k["state"] == 1:
            return "D", "03", k
        if k["state"] == 2:
            return "D", "09", k
        if self.use_exp and time.time() > k["exp"]:
            return "D", "04", k
        if cmd == 3:                               # 반납: 차량 내부에서 즉시 무효화, 횟수 차감 없음
            k["state"] = 2
            self.log(f"KID={kid:08X} 반납 처리 → 이후 거부")
            return "A", "00", k
        if cmd not in PERM_BIT or not (k["perm"] & PERM_BIT[cmd]):
            return "D", "06", k
        if self.use_cnt:
            if k["remaining"] <= 0:
                return "D", "05", k
            k["remaining"] -= 1                    # 차감(저장) 후 실행
        self.actuate(cmd, k["remaining"] if self.use_cnt else None)
        return "A", "00", k

    def handle(self, p):
        """앱 요청 한 줄(RID 제외 필드 목록) → 응답 필드 목록"""
        kind = p[0]
        if kind == "HB":                           # Pi 생존 신호: 응답 없음
            return None
        with self.lock:
            if kind == "KEY":                      # KEY|KID|EXP|LIMIT|SIT|PERM|TAG
                kid, exp = int(p[1], 16), int(p[2], 16)
                limit, sit, perm = (int(x, 16) for x in p[3:6])
                if not eq(key_tag(kid, exp, limit, sit, perm), bytes.fromhex(p[6])):
                    self.log(f"키 등록 거부 KID={p[1]} (인증값 불일치)")
                    return ["KEYNG", p[1], "01"]
                if kid not in self.keys:           # 같은 KID 재등록은 기존 기록 유지
                    self.keys[kid] = {"exp": exp, "limit": limit, "remaining": limit,
                                      "sit": sit, "perm": perm, "state": 0}
                self.log(f"키 등록 KID={p[1]} 한도={limit}")
                return ["KEYOK", p[1]]
            if kind == "REQ":                      # REQ|KID|CMD
                kid = int(p[1], 16)
                if kid not in self.keys:
                    return ["RES", p[1], "D", "08", "00"]
                n = os.urandom(16)                 # STM32: 하드웨어 RNG 128비트
                self.nonces[kid] = (n, time.time())
                return ["CHAL", p[1], hx(n)]
            if kind == "RESP":                     # RESP|KID|CMD|NONCE|TAG
                kid, cmd = int(p[1], 16), int(p[2], 16)
                res, why, k = self.decide(kid, cmd, bytes.fromhex(p[3]), bytes.fromhex(p[4]))
                rem = f"{k['remaining']:02X}" if (k and self.use_cnt) else "FF"
                if res == "D":
                    self.log(f"✖ KID={p[1]} {CMD_NAME.get(cmd, cmd)} 거부: {REASON[why]}")
                return ["RES", p[1], res, why, rem]
        return ["ERR", "FF"]

    def make_syncreq(self):
        self.sync_nonce = os.urandom(16)
        return ["SYNCREQ", f"{VID:08X}", hx(self.sync_nonce), f"{self.ver:08X}"]

    def apply_sync(self, p):
        """SYNC|VID|VER|NONCE|COUNT|entries|TAG 검증 후 반영. 성공 시 True"""
        try:
            nv, rn, ents = int(p[2], 16), bytes.fromhex(p[3]), dec_entries(p[5])
            ok = (p[0] == "SYNC" and self.sync_nonce is not None and rn == self.sync_nonce
                  and nv >= self.ver and eq(sync_tag(nv, rn, ents), bytes.fromhex(p[6])))
        except (ValueError, IndexError):
            ok = False
        self.sync_nonce = None                     # 동기화 nonce 도 1회용
        if not ok:
            self.log("동기화 응답 거부 (nonce/버전/인증값 불일치)")
            return False
        with self.lock:
            for kid, s in ents:
                if kid in self.keys:
                    k = self.keys[kid]
                    if s == 1:
                        k["state"] = 1
                    elif k["state"] == 0:
                        k["remaining"] = k["limit"]    # 인증된 동기화만 횟수 복구
            if nv > self.ver:
                self.log(f"동기화 반영 VER {self.ver} → {nv}")
            self.ver = nv
        return True
