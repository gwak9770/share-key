"""STM32와 같은 판단·영속 저장·복구 규칙. storage=None은 기존 PC 시연용 RAM 모드."""
import os
import time
import threading
from common import *
from storage import encode_state, decode_state


class VehicleCore:
    def __init__(self, mode="C", log=print, storage=None):
        self.use_exp = mode in "BD"
        self.use_cnt = mode in "CD"
        self.mode, self.log = mode, log
        self.lock = threading.Lock()
        self.keys, self.nonces = {}, {}
        self.ver, self.sync_nonce = 0, None
        self.storage = storage
        self.recovery_required = False
        self.recovery_nonce = None
        if storage is not None:
            image = storage.load()
            try:
                if image is None:
                    raise ValueError("복원 불가")
                self.ver, self.keys = decode_state(image)
            except ValueError:
                self.keys, self.ver = {}, 0
                self.recovery_required = True
                self.log("STORAGE RECOVERY REQUIRED")

    def _persist(self):
        if self.storage is None or self.storage.save(encode_state(self.ver, self.keys)):
            return True
        self.recovery_required = True
        self.recovery_nonce = None
        self.log("STORAGE RECOVERY REQUIRED")
        return False

    def actuate(self, cmd, rem):
        self.log(f"▶ {CMD_NAME[cmd]} 실행 (LCD: ALLOW / LEFT {'∞' if rem is None else rem})")

    def decide(self, kid, cmd, nonce, tag):
        k = self.keys.get(kid)
        pend = self.nonces.pop(kid, None)
        if self.recovery_required:
            return "D", "0A", k
        if not k:
            return "D", "08", k
        if not eq(auth_tag(derive(kid), kid, cmd, nonce), tag):
            return "D", "01", k
        if not pend or pend[0] != nonce or time.time() - pend[1] > NONCE_LIFE:
            return "D", "02", k
        if k["state"] in (1, 2):
            return "D", "03" if k["state"] == 1 else "09", k
        if self.use_exp and time.time() > k["exp"]:
            return "D", "04", k
        if cmd == 3:
            k["state"] = 2
        else:
            if cmd not in PERM_BIT or not (k["perm"] & PERM_BIT[cmd]):
                return "D", "06", k
            if self.use_cnt:
                if k["remaining"] <= 0:
                    return "D", "05", k
                k["remaining"] -= 1
        if not self._persist():
            return "D", "0A", k
        if cmd != 3:
            self.actuate(cmd, k["remaining"] if self.use_cnt else None)
        return "A", "00", k

    def _recover(self, p):
        if self.storage is None or not self.recovery_required:
            return ["RFAIL", "0A"]
        if p == ["RBEGIN"]:
            if self.recovery_nonce is None:
                self.recovery_nonce = os.urandom(16)
            return ["RCHAL", f"{VID:08X}", hx(self.recovery_nonce)]
        if len(p) != 10 or p[0] != "RECOVER":
            return ["RFAIL", "FF"]
        try:
            if any(len(v) != n for v, n in zip(p[1:], (8, 32, 8, 8, 8, 2, 2, 2, 64))):
                raise ValueError("길이")
            vid, nonce, ver = int(p[1], 16), bytes.fromhex(p[2]), int(p[3], 16)
            kid, exp = int(p[4], 16), int(p[5], 16)
            limit, sit, perm = (int(v, 16) for v in p[6:9])
            tag = bytes.fromhex(p[9])
            if vid != VID:
                return ["RFAIL", "FF"]
            if self.recovery_nonce is None or nonce != self.recovery_nonce:
                return ["RFAIL", "02"]
            if not eq(recovery_tag(ver, nonce, kid, exp, limit, sit, perm), tag):
                return ["RFAIL", "01"]
        except (ValueError, OverflowError):
            return ["RFAIL", "FF"]
        self.recovery_nonce = None
        if self.use_exp and time.time() > exp:
            return ["RFAIL", "04"]
        self.keys = {kid: dict(exp=exp, limit=limit, remaining=limit, sit=sit, perm=perm, state=0)}
        self.ver = ver
        if not self.storage.recover(encode_state(ver, self.keys)):
            return ["RFAIL", "0A"]
        self.recovery_required = False
        self.nonces.clear()
        self.sync_nonce = None
        self.log("STORAGE RECOVERY COMPLETE")
        return ["RECOVERED", f"{kid:08X}"]

    def handle(self, p):
        if not p:
            return ["ERR", "FF"]
        kind = p[0]
        if kind == "HB":
            return None
        with self.lock:
            if kind in ("RBEGIN", "RECOVER"):
                return self._recover(p)
            if kind == "KEY":
                kid, exp = int(p[1], 16), int(p[2], 16)
                limit, sit, perm = (int(x, 16) for x in p[3:6])
                if self.recovery_required:
                    return ["KEYNG", p[1], "0A"]
                if not eq(key_tag(kid, exp, limit, sit, perm), bytes.fromhex(p[6])):
                    return ["KEYNG", p[1], "01"]
                if kid not in self.keys:
                    if len(self.keys) >= 8:
                        return ["KEYNG", p[1], "FF"]
                    self.keys[kid] = dict(exp=exp, limit=limit, remaining=limit,
                                          sit=sit, perm=perm, state=0)
                if not self._persist():
                    return ["KEYNG", p[1], "0A"]
                return ["KEYOK", p[1]]
            if kind == "REQ":
                kid = int(p[1], 16)
                if self.recovery_required:
                    return ["RES", p[1], "D", "0A", "FF"]
                if kid not in self.keys:
                    return ["RES", p[1], "D", "08", "00"]
                n = os.urandom(16)
                self.nonces[kid] = (n, time.time())
                return ["CHAL", p[1], hx(n)]
            if kind == "RESP":
                kid, cmd = int(p[1], 16), int(p[2], 16)
                res, why, k = self.decide(kid, cmd, bytes.fromhex(p[3]), bytes.fromhex(p[4]))
                rem = f"{k['remaining']:02X}" if (k and self.use_cnt) else "FF"
                if res == "D":
                    self.log(f"✖ KID={p[1]} 거부: {REASON[why]}")
                return ["RES", p[1], res, why, rem]
        return ["ERR", "FF"]

    def make_syncreq(self):
        with self.lock:
            if self.recovery_required:
                return None
            self.sync_nonce = os.urandom(16)
            return ["SYNCREQ", f"{VID:08X}", hx(self.sync_nonce), f"{self.ver:08X}"]

    def apply_sync(self, p):
        with self.lock:
            try:
                nv, rn, ents = int(p[2], 16), bytes.fromhex(p[3]), dec_entries(p[5])
                ok = (not self.recovery_required and len(p) == 7 and p[0] == "SYNC"
                      and int(p[1], 16) == VID and len(ents) == int(p[4], 16) <= 16
                      and self.sync_nonce is not None and rn == self.sync_nonce
                      and nv >= self.ver and eq(sync_tag(nv, rn, ents), bytes.fromhex(p[6])))
            except (ValueError, IndexError, OverflowError):
                ok = False
            self.sync_nonce = None
            if not ok:
                return False
            for kid, state in ents:
                if kid in self.keys:
                    k = self.keys[kid]
                    if state == 1:
                        k["state"] = 1
                    elif k["state"] == 0:
                        k["remaining"] = k["limit"]
            self.ver = nv
            return self._persist()
