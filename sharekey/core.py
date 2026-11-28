"""STM32와 같은 판단·영속 저장·복구 규칙. storage=None은 기존 PC 시연용 RAM 모드."""
import os
import time
import threading
from common import *
from storage import encode_state, decode_state, decode_clock

CLOCK_TOLERANCE_S = 300   # 시계 되돌림 허용 오차 (00 §6 13)
CLOCK_SAVE_STEP_S = 600   # B·D에서 시계 하한을 주기적으로 저장하는 간격 (하루 최대 144회 쓰기)
EXP_NONE = 0xFFFFFFFF     # 시계 오류용 키: 기간 없음, B·D에서 RTC를 못 읽을 때만 횟수로 허용 (00 §6 14, 1128)


class VehicleCore:
    def __init__(self, mode="C", log=print, storage=None, clock=time.monotonic,
                 reauth_period=60, reauth_grace=30, stop_cutoff=600, reauth_enabled=True):
        self.use_exp = mode in "BD"
        self.use_cnt = mode in "CD"
        self.mode, self.log = mode, log
        self.lock = threading.Lock()
        self.keys, self.nonces = {}, {}
        self.ver, self.sync_nonce = 0, None
        self.online = -1
        self.sync_misses = 0
        self.sync_waiting = False
        self.storage = storage
        self.recovery_required = False
        self.recovery_nonce = None
        self.clock, self.reauth_enabled = clock, reauth_enabled
        self.period_ms, self.grace_ms, self.cutoff_ms = (int(v * 1000) for v in (reauth_period, reauth_grace, stop_cutoff))
        if not (0 < self.period_ms and 0 <= self.grace_ms and self.period_ms + self.grace_ms < 0x80000000
                and 0 < self.cutoff_ms < 0x80000000):
            raise ValueError("잘못된 재인증 시간")
        self.engine_running = self.engine_warning = self.stopped = self.stop_tracking = False
        self.engine_kid, self.last_auth, self.stop_started = 0, 0, 0
        self.clock_floor = self.clock_seen = 0
        self.clock_alarm = self.clock_bad = False
        if storage is not None:
            image = storage.load()
            try:
                if image is None:
                    raise ValueError("복원 불가")
                self.ver, self.keys = decode_state(image)
                self.clock_floor = self.clock_seen = decode_clock(image)
            except ValueError:
                self.keys, self.ver = {}, 0
                self.recovery_required = True
                self.log("STORAGE RECOVERY REQUIRED")

    def _clock_ok(self):
        """B·D 기간 판단용 RTC 시각. 본 적 있는 가장 늦은 시각(clock_seen)보다 허용 오차 이상 뒤면
        되돌림으로 보고 None. clock_seen은 저장할 때마다 플래시에 함께 쓴다(00 §6 13)."""
        t = time.time()
        if int(t) == 0:                      # RTC를 못 읽음 → 기간을 모르므로 04 (1128)
            if not self.clock_bad:
                self.clock_bad = True
                self.log("CLOCK INVALID: period keys denied (04)")
            return None
        self.clock_bad = False
        if int(t) + CLOCK_TOLERANCE_S < self.clock_seen:
            if not self.clock_alarm:
                self.clock_alarm = True
                self.log("CLOCK ROLLBACK: period keys denied (04)")
            return None
        self.clock_alarm = False
        self.clock_seen = max(self.clock_seen, int(t))
        return t

    def _clock_tick(self):
        """B·D: 허가된 명령이 없어도 CLOCK_SAVE_STEP_S마다 하한을 저장한다."""
        if not self.use_exp or self.recovery_required or self.storage is None:
            return
        if self._clock_ok() is not None and self.clock_seen >= self.clock_floor + CLOCK_SAVE_STEP_S:
            self._persist()

    def _expired(self, exp):
        t = self._clock_ok()
        return t is None or t > exp

    def _fallback(self, k):
        """시계 오류용 키(EXP=EXP_NONE): B·D에서 RTC를 못 읽을 때만 C처럼 횟수로 제한해 허용."""
        return self.use_exp and k["exp"] == EXP_NONE

    def _counted(self, k):
        return self.use_cnt or self._fallback(k)

    def _now(self):
        return int(round(self.clock() * 1000)) & 0xFFFFFFFF

    def configure_reauth(self, period, grace, cutoff):
        """차량 로컬 설정/시험용 밀리초. 운행 중 변경 금지."""
        if self.engine_running or not (0 < period and 0 <= grace and period + grace < 0x80000000
                                       and 0 < cutoff < 0x80000000):
            return False
        self.period_ms, self.grace_ms, self.cutoff_ms = period, grace, cutoff
        return True

    def set_stopped(self, stopped):
        """차량 로컬 센서/PC 시험 전용. 네트워크 명령에 연결하지 않는다."""
        with self.lock:
            self.stopped = bool(stopped)
            if not self.stopped:
                self.stop_tracking = False

    def _engine_stop(self):
        self.engine_running = self.engine_warning = self.stop_tracking = False

    def _drive_warn(self):
        if not self.engine_running or self.engine_warning:
            return True
        self.engine_warning, self.stop_tracking = True, False
        self.log("REAUTH REQUIRED: driving continues until local stopped cutoff")
        k = self.keys.get(self.engine_kid)
        if k and k["state"] == 0:
            k["state"] = 3
            return self._persist()
        return True

    def _drive_poll(self):
        if not self.reauth_enabled or not self.engine_running:
            return
        now = self._now()
        if not self.engine_warning and ((now - self.last_auth) & 0xFFFFFFFF) >= self.period_ms + self.grace_ms:
            self._drive_warn()
        if not self.engine_warning:
            return
        if not self.stopped:
            self.stop_tracking = False
            return
        if not self.stop_tracking:
            self.stop_tracking, self.stop_started = True, now
        if ((now - self.stop_started) & 0xFFFFFFFF) >= self.cutoff_ms:
            self._engine_stop()
            self.log("REAUTH STOP CUTOFF")
            self.actuate(5, None)

    def poll(self):
        with self.lock:
            self._drive_poll()
            self._clock_tick()

    def _drive_status(self):
        elapsed = (self._now() - self.last_auth) & 0xFFFFFFFF if self.engine_running else 0
        left = max(0, self.period_ms + self.grace_ms - elapsed) if self.engine_running and not self.engine_warning else 0
        return ["DSTATE", f"{self.engine_kid if self.engine_running else 0xFFFFFFFF:08X}",
                str(int(self.engine_running)), str(int(self.engine_warning)), str(int(self.stopped)),
                f"{elapsed // 1000:08X}", f"{(left + 999) // 1000:08X}"]

    def _persist(self):
        if self.storage is None or self.storage.save(encode_state(self.ver, self.keys, self.clock_seen)):
            self.clock_floor = self.clock_seen
            return True
        self.recovery_required = True
        self.recovery_nonce = None
        if self.engine_running and not self.engine_warning:
            self.engine_warning, self.stop_tracking = True, False
        self.log("STORAGE RECOVERY REQUIRED")
        return False

    def actuate(self, cmd, rem):
        self.log(f"▶ {CMD_NAME[cmd]} 실행 (LCD: ALLOW / LEFT {'∞' if rem is None else rem})")

    def decide(self, kid, cmd, nonce, tag):
        k = self.keys.get(kid)
        pend = self.nonces.pop(kid, None)
        if self.recovery_required and cmd != 5:
            return "D", "0A", k
        if not k:
            return "D", "08", k
        if not eq(auth_tag(derive(kid), kid, cmd, nonce), tag):
            return "D", "01", k
        if not pend or pend[0] != nonce or time.time() - pend[1] > NONCE_LIFE:
            return "D", "02", k
        def reject(why):
            if self.reauth_enabled and cmd == 4 and self.engine_running and self.engine_kid == kid:
                if not self._drive_warn():
                    why = "0A"
            return "D", why, k
        if cmd == 5:
            if not k["perm"] & 2:
                return "D", "06", k
            if self.engine_running and self.engine_kid != kid:
                return "D", "07", k
            was_running = self.engine_running
            self._engine_stop()
            if was_running:
                self.actuate(5, None)
            return "A", "00", k
        if k["state"] in (1, 2):
            return reject("03" if k["state"] == 1 else "09")
        if k["state"] == 3 and cmd in (2, 4):
            return reject("07")
        if self._fallback(k):
            if int(time.time()) != 0:        # 시계가 정상이면 원래 기간 키를 쓴다
                return reject("04")
        elif self.use_exp and self._expired(k["exp"]):
            return reject("04")
        if cmd == 3:
            k["state"] = 2
        else:
            if cmd not in PERM_BIT or not (k["perm"] & PERM_BIT[cmd]):
                return reject("06")
            if cmd == 2 and self.engine_running:
                return reject("07")
            if cmd == 4 and (not self.reauth_enabled or not self.engine_running or self.engine_kid != kid):
                return reject("07")
            if self._counted(k):
                if k["remaining"] <= 0:
                    return reject("05")
                k["remaining"] -= 1
        if not self._persist():
            return "D", "0A", k
        if cmd == 2:
            self.engine_running = True
            self.engine_warning = self.stop_tracking = False
            self.engine_kid, self.last_auth = kid, self._now()
        if cmd == 4:
            self.last_auth = self._now()
        if cmd == 3 and self.engine_running and self.engine_kid == kid:
            self._drive_warn()
        if cmd not in (3, 4):
            self.actuate(cmd, k["remaining"] if self._counted(k) else None)
        return "A", "00", k

    def _recover(self, p):
        if self.engine_running:
            return ["RFAIL", "07"]
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
        if self.use_exp and self._expired(exp):
            return ["RFAIL", "04"]
        self.keys = {kid: dict(exp=exp, limit=limit, remaining=limit, sit=sit, perm=perm, state=0)}
        self.ver = ver
        if not self.storage.recover(encode_state(ver, self.keys, self.clock_seen)):
            return ["RFAIL", "0A"]
        self.clock_floor = self.clock_seen
        self.recovery_required = False
        self.nonces.clear()
        self.sync_nonce = None
        self.online = -1
        self.sync_misses = 0
        self.sync_waiting = False
        self.log("STORAGE RECOVERY COMPLETE")
        return ["RECOVERED", f"{kid:08X}"]

    def handle(self, p):
        if not p:
            return ["ERR", "FF"]
        kind = p[0]
        if kind == "HB":
            return None
        with self.lock:
            self._drive_poll()
            if p == ["DSTATUS"]:
                return self._drive_status()
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
                if self.recovery_required and int(p[2], 16) != 5:
                    return ["RES", p[1], "D", "0A", "FF"]
                if kid not in self.keys:
                    return ["RES", p[1], "D", "08", "00"]
                n = os.urandom(16)
                self.nonces[kid] = (n, time.time())
                return ["CHAL", p[1], hx(n)]
            if kind == "RESP":
                kid, cmd = int(p[1], 16), int(p[2], 16)
                res, why, k = self.decide(kid, cmd, bytes.fromhex(p[3]), bytes.fromhex(p[4]))
                rem = f"{k['remaining']:02X}" if (k and self._counted(k)) else "FF"
                if res == "D":
                    self.log(f"✖ KID={p[1]} 거부: {REASON[why]}")
                return ["RES", p[1], res, why, rem]
        return ["ERR", "FF"]

    def make_syncreq(self):
        with self.lock:
            self._drive_poll()
            self._clock_tick()
            if self.recovery_required:
                return None
            if self.sync_waiting:
                self.sync_misses = min(3, self.sync_misses + 1)
                if self.sync_misses == 3 and self.online != 0:
                    self.online = 0
                    self.log("no server response -> OFFLINE")
            self.sync_nonce = os.urandom(16)
            self.sync_waiting = True
            return ["SYNCREQ", f"{VID:08X}", hx(self.sync_nonce), f"{self.ver:08X}"]

    def apply_sync(self, p):
        with self.lock:
            self._drive_poll()
            try:
                nv, rn, ents = int(p[2], 16), bytes.fromhex(p[3]), dec_entries(p[5])
                ok = (not self.recovery_required and len(p) == 7 and p[0] == "SYNC"
                      and int(p[1], 16) == VID and len(ents) == int(p[4], 16) <= 16
                      and all(state in (0, 1) for _, state in ents)
                      and self.sync_nonce is not None and rn == self.sync_nonce
                      and nv >= self.ver and eq(sync_tag(nv, rn, ents), bytes.fromhex(p[6])))
            except (ValueError, IndexError, OverflowError):
                ok = False
            self.sync_nonce = None
            if not ok:
                return False
            drive_revalidated = False
            for kid, state in ents:
                if kid in self.keys:
                    k = self.keys[kid]
                    if state == 1:
                        k["state"] = 1
                    elif k["state"] in (0, 3):
                        k["state"] = 0
                        k["remaining"] = k["limit"]
                        if self.engine_running and kid == self.engine_kid:
                            drive_revalidated = True
            self.ver = nv
            if not self._persist():
                return False
            if self.engine_running:
                owner = self.keys.get(self.engine_kid)
                if owner and owner["state"] != 0:
                    self._drive_warn()
                elif drive_revalidated and self.engine_warning:
                    self.engine_warning = self.stop_tracking = False
                    self.last_auth = self._now()
            self.sync_waiting = False
            self.sync_misses = 0
            if self.online != 1:
                self.online = 1
                self.log("server sync ok -> ONLINE")
            return True
