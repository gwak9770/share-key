"""PC 모의: production C/Python 동일 시나리오, 전원 차단 주입, 단계별 CLI."""
import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import *
from core import VehicleCore
from storage import FlashJournal, MemoryFlash
import server

QUIET = lambda *args: None
EXP = 0xFFFFFFFF
SECTOR = 1024
BRIDGE = os.environ.get("SHAREKEY_TEST_BRIDGE")
DLL = ctypes.CDLL(BRIDGE) if BRIDGE else None
if DLL:
    DLL.bridge_send.argtypes = [ctypes.c_char_p]
    DLL.bridge_send.restype = ctypes.c_char_p
    DLL.bridge_sync.restype = ctypes.c_char_p
    DLL.bridge_media.restype = ctypes.POINTER(ctypes.c_uint8)
    DLL.bridge_advance.argtypes = [ctypes.c_uint32]
    DLL.bridge_advance.restype = ctypes.c_char_p
    DLL.bridge_clock.argtypes = [ctypes.c_uint32]


class Native:
    def __init__(self, image=None):
        DLL.bridge_reset()
        if image is not None:
            ctypes.memmove(DLL.bridge_media(), image, len(image))
            DLL.bridge_boot()

    def send(self, fields):
        rid = self.sync_rid if fields[0] == "SYNC" else "00"
        raw = DLL.bridge_send((rid + "|" + "|".join(fields)).encode()).decode()
        return raw.split("|")[1:] if raw else None

    def boot(self):
        DLL.bridge_boot()

    @property
    def locked(self):
        return bool(DLL.bridge_locked())

    @property
    def actions(self):
        return DLL.bridge_actions()

    def raw(self):
        return ctypes.string_at(DLL.bridge_media(), 2 * SECTOR)

    def cut(self, n):
        DLL.bridge_cut(n)

    def corrupt(self):
        # Corrupt a committed body's CRC, never the commit word.
        image = self.raw()
        records = [(int.from_bytes(image[i+8:i+12], "big"), i)
                   for i in range(0, len(image), 256)
                   if image[i:i+4] == b"SKJ1" and image[i+5] == 0 and image[i+252:i+256] == b"\0"*4]
        off = max(records)[1] + 32
        DLL.bridge_media()[off] ^= 1

    def sync_request(self):
        fields = DLL.bridge_sync().decode().split("|")
        self.sync_rid = fields[0]
        return fields[1:]

    @property
    def online(self):
        return DLL.bridge_online()

    @property
    def misses(self):
        return DLL.bridge_misses()

    @property
    def offline_logs(self):
        return DLL.bridge_offline_logs()


class PythonVehicle:
    def __init__(self, image=None):
        self.flash = MemoryFlash(SECTOR)
        if image is not None:
            self.flash.data[:] = image
        self.actions = 0
        self.logs = []
        self.boot()

    def boot(self):
        self.core = VehicleCore(log=self.logs.append, storage=FlashJournal(self.flash))
        self.core.actuate = lambda *args: setattr(self, "actions", self.actions + 1)

    def send(self, fields):
        if fields[0] == "SYNC":
            if self.core.apply_sync(fields):
                return ["SYNCACK", f"{VID:08X}", f"{self.core.ver:08X}"]
            return None
        return self.core.handle(fields)

    @property
    def locked(self):
        return self.core.recovery_required

    def raw(self):
        return bytes(self.flash.data)

    def cut(self, n):
        self.flash.budget = None if n < 0 else n

    def corrupt(self):
        image = self.raw()
        records = [(int.from_bytes(image[i+8:i+12], "big"), i)
                   for i in range(0, len(image), 256)
                   if image[i:i+4] == b"SKJ1" and image[i+5] == 0 and image[i+252:i+256] == b"\0"*4]
        self.flash.data[max(records)[1]+32] ^= 1

    def sync_request(self):
        return self.core.make_syncreq()

    @property
    def online(self):
        return self.core.online

    @property
    def misses(self):
        return self.core.sync_misses

    @property
    def offline_logs(self):
        return self.logs.count("no server response -> OFFLINE")


def register(v, kid=7):
    return v.send(["KEY", f"{kid:08X}", "FFFFFFFF", "04", "02", "03",
                   hx(key_tag(kid, EXP, 4, 2, 3))])


def token(v, kid=7):
    challenge = v.send(["RBEGIN"])
    nonce = bytes.fromhex(challenge[2])
    return ["RECOVER", f"{VID:08X}", hx(nonce), "00000001", f"{kid:08X}",
            "FFFFFFFF", "04", "02", "03", hx(recovery_tag(1, nonce, kid, EXP, 4, 2, 3))]


def recover(v, kid=7):
    return v.send(token(v, kid))


def use(v, kid=7, cmd=1):
    fields = v.send(["REQ", f"{kid:08X}", f"{cmd:02X}"])
    if fields[0] != "CHAL":
        return fields
    nonce = bytes.fromhex(fields[2])
    return v.send(["RESP", f"{kid:08X}", f"{cmd:02X}", hx(nonce),
                   hx(auth_tag(derive(kid), kid, cmd, nonce))])


class PolicyTests(unittest.TestCase):
    def factories(self):
        return [PythonVehicle, Native] if DLL else [PythonVehicle]

    def test_30_reboots_exhausted_count_and_reregister(self):
        for factory in self.factories():
            v = factory()
            self.assertTrue(v.locked)
            self.assertEqual(register(v)[-1], "0A")
            self.assertEqual(recover(v), ["RECOVERED", "00000007"])
            for _ in range(4):
                self.assertEqual(use(v)[2:4], ["A", "00"])
            for _ in range(30):
                v.boot()
                self.assertFalse(v.locked)
                self.assertEqual(register(v)[0], "KEYOK")
                self.assertEqual(use(v)[2:], ["D", "05", "00"])
            self.assertEqual(v.actions, 4)

    def test_eight_keys_and_independent_counts(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            for kid in range(8, 15):
                self.assertEqual(register(v, kid)[0], "KEYOK")
            self.assertEqual(register(v, 15), ["KEYNG", "0000000F", "FF"])
            self.assertEqual(use(v, 7)[-1], "03")
            self.assertEqual(use(v, 8)[-1], "03")
            v.boot()
            self.assertEqual(use(v, 7)[-1], "02")
            self.assertEqual(use(v, 8)[-1], "02")

    def test_return_and_revoke_survive_boot(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            self.assertEqual(use(v, cmd=3)[2], "A")
            v.boot()
            self.assertEqual(use(v)[3], "09")
            register(v, 8)
            req = v.sync_request()
            nonce = bytes.fromhex(req[2])
            entries = [(7, 0), (8, 1)]
            self.assertEqual(v.send(["SYNC", f"{VID:08X}", "00000002", hx(nonce), "02",
                                     enc_entries(entries), hx(sync_tag(2, nonce, entries))])[0], "SYNCACK")
            v.boot()
            self.assertEqual(use(v)[3], "09")
            self.assertEqual(use(v, 8)[3], "03")

    def test_sync_noop_no_write_and_old_version_rejected(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            before = v.raw()
            for version in (1, 0):
                req = v.sync_request()
                nonce = bytes.fromhex(req[2])
                response = v.send(["SYNC", f"{VID:08X}", f"{version:08X}", hx(nonce), "01",
                                   "00000007:00", hx(sync_tag(version, nonce, [(7, 0)]))])
                self.assertEqual(response is not None, version == 1)
            self.assertEqual(v.raw(), before)

    def test_committed_corruption_blocks_and_recovers_new_key(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            use(v)
            v.corrupt()
            v.boot()
            self.assertTrue(v.locked)
            self.assertEqual(use(v)[3], "0A")
            self.assertEqual(register(v)[-1], "0A")
            self.assertEqual(recover(v, 8), ["RECOVERED", "00000008"])
            v.boot()
            self.assertEqual(use(v, 7)[3], "08")
            self.assertEqual(use(v, 8)[2], "A")

    def test_nonce_tamper_wrong_vehicle_replay_and_reboot(self):
        for factory in self.factories():
            v = factory()
            good = token(v)
            again = v.send(["RBEGIN"])
            self.assertEqual(again[2], good[2])
            bad = list(good)
            bad[-1] = "00" * 32
            self.assertEqual(v.send(bad), ["RFAIL", "01"])
            bad = list(good)
            bad[1] = "00000000"
            self.assertEqual(v.send(bad), ["RFAIL", "FF"])
            v.boot()
            self.assertEqual(v.send(good), ["RFAIL", "02"])
            good = token(v)
            self.assertEqual(v.send(good)[0], "RECOVERED")
            self.assertEqual(v.send(good), ["RFAIL", "0A"])

    def test_failed_sync_has_no_ack_and_reboot_keeps_old_version(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            req = v.sync_request()
            nonce = bytes.fromhex(req[2])
            v.cut(0)
            response = v.send(["SYNC", f"{VID:08X}", "00000002", hx(nonce), "01",
                               "00000007:01", hx(sync_tag(2, nonce, [(7, 1)]))])
            self.assertIsNone(response)
            self.assertTrue(v.locked)
            v.cut(-1)
            v.boot()
            self.assertFalse(v.locked)
            self.assertEqual(v.sync_request()[-1], "00000001")

    @unittest.skipUnless(DLL, "C bridge 필요")
    def test_read_failure_never_erases_media(self):
        v = Native()
        recover(v)
        v.corrupt()
        v.boot()
        recovery = token(v, 8)
        before = v.raw()
        DLL.bridge_read_fail(1)
        self.assertEqual(v.send(recovery), ["RFAIL", "0A"])
        self.assertEqual(v.raw(), before)
        DLL.bridge_read_fail(0)

    def test_every_program_word_cut_before_actuation(self):
        for factory in self.factories():
            initial = factory()
            recover(initial)
            baseline = initial.raw()
            for cut in range(65):
                v = factory(baseline)
                v.cut(cut)
                response = use(v)
                allowed = response[2] == "A"
                self.assertEqual(v.actions, int(allowed), (factory, cut))
                self.assertEqual(allowed, cut == 64)
                v.cut(-1)
                v.boot()
                if not v.locked:
                    self.assertEqual(use(v)[-1], "02" if allowed else "03")

    def test_every_rotation_erase_and_program_word_cut(self):
        for factory in self.factories():
            initial = factory()
            recover(initial)
            for _ in range(3):
                use(initial)
            baseline = initial.raw()
            for cut in range(321):
                v = factory(baseline)
                v.cut(cut)
                response = use(v)
                allowed = response[2] == "A"
                self.assertEqual(allowed, cut == 320, (factory, cut, response))
                self.assertEqual(v.actions, int(allowed))
                v.cut(-1)
                v.boot()
                if not v.locked:
                    self.assertEqual(use(v)[3], "05" if allowed else "00")

    def test_recovery_cut_and_retry_cannot_revive_old_key(self):
        for factory in self.factories():
            initial = factory()
            recover(initial)
            use(initial)
            initial.corrupt()
            initial.boot()
            baseline = initial.raw()
            for cut in range(577):
                v = factory(baseline)
                recovery = token(v, 8)
                v.cut(cut)
                response = v.send(recovery)
                v.cut(-1)
                v.boot()
                if not v.locked:
                    self.assertEqual(use(v, 7)[3], "08", (factory, cut))
                else:
                    # Another interruption during retry must retain the barrier.
                    retry = token(v, 9)
                    v.cut(cut % 66)
                    v.send(retry)
                    v.cut(-1)
                    v.boot()
                    if not v.locked:
                        self.assertEqual(use(v, 7)[3], "08")
                    else:
                        self.assertEqual(recover(v, 10)[0], "RECOVERED")
                        v.boot()
                        self.assertFalse(v.locked)
                        self.assertEqual(use(v, 7)[3], "08")

    @unittest.skipUnless(DLL, "run_persistence_tests.py로 C bridge 빌드 필요")
    def test_python_c_binary_journal_identical(self):
        p, c = PythonVehicle(), Native()
        recover(p)
        recover(c)
        self.assertEqual(p.raw(), c.raw())
        for kid in (8, 9):
            self.assertEqual(register(p, kid), register(c, kid))
            self.assertEqual(p.raw(), c.raw())
        for kid in (7, 8, 7, 9):
            self.assertEqual(use(p, kid), use(c, kid))
            self.assertEqual(p.raw(), c.raw())


class OfflineTests(unittest.TestCase):
    def factories(self):
        return [PythonVehicle, Native] if DLL else [PythonVehicle]

    def accept(self, v, req=None, version=1):
        req = req or v.sync_request()
        nonce = bytes.fromhex(req[2])
        return v.send(["SYNC", f"{VID:08X}", f"{version:08X}", hx(nonce), "00", "-",
                       hx(sync_tag(version, nonce, []))])

    def test_unknown_first_request_three_failures_and_saturation(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            self.assertEqual((v.online, v.misses), (-1, 0))
            v.sync_request()
            self.assertEqual((v.online, v.misses), (-1, 0))
            for i in range(1, 8):
                v.sync_request()
                self.assertEqual((v.online, v.misses), (0 if i >= 3 else -1, min(i, 3)))
            self.assertEqual(v.offline_logs, 1)

    def test_online_two_failures_keeps_state_and_success_resets(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            self.accept(v)
            self.assertEqual((v.online, v.misses), (1, 0))
            req = v.sync_request()
            for i in (1, 2):
                req = v.sync_request()
                self.assertEqual((v.online, v.misses), (1, i))
            self.assertEqual(self.accept(v, req)[0], "SYNCACK")
            self.assertEqual((v.online, v.misses), (1, 0))
            v.sync_request()
            v.sync_request()
            self.assertEqual((v.online, v.misses), (1, 1))

    def test_bad_responses_and_hb_never_reset_failures(self):
        for factory in self.factories():
            for bad_kind in ("tag", "nonce", "version", "vid", "format"):
                v = factory()
                recover(v)
                self.accept(v)
                v.sync_request()
                for i in (1, 2, 3):
                    req = v.sync_request()
                    nonce = bytes.fromhex(req[2])
                    fields = ["SYNC", f"{VID:08X}", "00000001", hx(nonce), "00", "-",
                              hx(sync_tag(1, nonce, []))]
                    if bad_kind == "tag": fields[-1] = "00" * 32
                    if bad_kind == "nonce": fields[3] = "00" * 16
                    if bad_kind == "version":
                        fields[2], fields[-1] = "00000000", hx(sync_tag(0, nonce, []))
                    if bad_kind == "vid": fields[1] = "00000000"
                    if bad_kind == "format": fields = fields[:2]
                    self.assertIsNone(v.send(fields))
                    v.send(["HB"])
                    self.assertEqual(v.misses, i, (factory, bad_kind, i))
                    self.assertEqual(v.online, 0 if i == 3 else 1)
                self.assertEqual(v.offline_logs, 1)
                self.assertEqual(self.accept(v)[0], "SYNCACK")
                self.assertEqual((v.online, v.misses), (1, 0))

    def test_offline_transition_never_refills_counts_or_writes_flash(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            self.accept(v)
            use(v)
            before = v.raw()
            for _ in range(4): v.sync_request()
            self.assertEqual(v.online, 0)
            self.assertEqual(v.raw(), before)
            self.assertEqual(use(v)[-1], "02")
            v.boot()
            self.assertEqual((v.online, v.misses), (-1, 0))

    def test_recovery_wait_does_not_count_timeouts(self):
        for factory in self.factories():
            v = factory()
            for _ in range(5): v.sync_request()
            self.assertEqual((v.online, v.misses), (-1, 0))
            recover(v)
            self.assertEqual((v.online, v.misses), (-1, 0))

    def test_failed_durable_sync_is_not_online(self):
        for factory in self.factories():
            v = factory()
            recover(v)
            v.cut(0)
            self.assertIsNone(self.accept(v, version=2))
            self.assertTrue(v.locked)
            self.assertEqual(v.online, -1)

    @unittest.skipUnless(DLL, "C bridge 필요")
    def test_c_millisecond_boundaries_wraparound_and_stale_rid(self):
        for start in (0, 0xFFFFFF00):
            v = Native()
            recover(v)
            DLL.bridge_clock(start)
            v.boot()
            fields = DLL.bridge_advance(0).decode().split("|")
            self.assertEqual(fields[1], "SYNCREQ")
            stale_rid = fields[0]
            self.assertEqual(v.misses, 0)
            for i in (1, 2, 3):
                self.assertEqual(DLL.bridge_advance(1999), b"")
                self.assertEqual(v.misses, i - 1)
                fields = DLL.bridge_advance(1).decode().split("|")
                self.assertEqual(v.misses, i)
            self.assertEqual(v.online, 0)
            nonce = bytes.fromhex(fields[3])
            wrong_rid = f"{(int(fields[0], 16) + 1) % 256:02X}"
            response = ["SYNC", f"{VID:08X}", "00000001", hx(nonce), "00", "-", hx(sync_tag(1, nonce, []))]
            DLL.bridge_send((wrong_rid + "|" + "|".join(response)).encode())
            self.assertEqual((v.online, v.misses), (0, 3))
            v.sync_rid = fields[0]
            self.assertEqual(v.send(response)[0], "SYNCACK")
            self.assertEqual((v.online, v.misses), (1, 0))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.STATE_FILE = str(Path(self.temp.name) / "server_state.json")
        server.st = {"ver": 1, "net": 0, "keys": {"00000007":
                     dict(exp=EXP, limit=4, sit=2, perm=3, state=0)}}
        self.nonce = bytes(range(16))
        self.request = ["RISSUE", f"{VID:08X}", hx(self.nonce), "00000007", "00000008",
                        hx(recovery_proof(7, 8, self.nonce))]

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_issue_offline_and_idempotent_retry(self):
        response = server.handle(None, self.request)
        self.assertEqual(response[0], "RISSUED")
        self.assertEqual(server.handle(None, self.request), response)
        self.assertEqual(server.st["ver"], 2)
        self.assertEqual(server.st["keys"]["00000007"]["state"], 1)
        self.assertEqual(response[9], hx(recovery_tag(2, self.nonce, 8, EXP, 4, 2, 3)))

    def test_revoked_returned_expired_rejected(self):
        for state, exp, why in ((1, EXP, "03"), (2, EXP, "09"), (0, 1, "04")):
            server.st["keys"]["00000007"].update(state=state, exp=exp)
            self.assertEqual(server.handle(None, self.request), ["RFAIL", why])

    def test_bad_proof_unknown_vehicle_existing_new_key(self):
        bad = list(self.request)
        bad[-1] = "00" * 32
        self.assertEqual(server.handle(None, bad), ["RFAIL", "01"])
        bad = list(self.request)
        bad[1] = "00000000"
        self.assertEqual(server.handle(None, bad), ["RFAIL", "FF"])
        server.st["keys"]["00000008"] = dict(server.st["keys"]["00000007"])
        self.assertEqual(server.handle(None, self.request), ["RFAIL", "FF"])

    def test_return_proof_then_recovery_denied(self):
        proof = H(derive(7), b"RETURN" + u32(VID) + u32(7))
        self.assertEqual(server.handle(None, ["RETURN", "00000007", hx(proof)])[0], "RETURNED")
        self.assertEqual(server.handle(None, self.request), ["RFAIL", "09"])

    def test_revoke_new_key_blocks_idempotent_fetch(self):
        server.handle(None, self.request)
        server.handle(None, ["REVOKE", "00000008"])
        self.assertEqual(server.handle(None, self.request), ["RFAIL", "03"])

    def test_failed_save_rolls_back_issuance_before_retry(self):
        with patch.object(server, "save", side_effect=OSError("시험 저장 실패")):
            with self.assertRaises(OSError):
                server.handle(None, self.request)
        self.assertEqual(server.st["ver"], 1)
        self.assertEqual(server.st["keys"]["00000007"]["state"], 0)
        self.assertNotIn("00000008", server.st["keys"])
        self.assertEqual(server.handle(None, self.request)[0], "RISSUED")


class CLITests(unittest.TestCase):
    def test_disconnected_three_stage_recovery_and_restart(self):
        # Isolated runtime files/ports; never touches the user's keys or server state.
        with tempfile.TemporaryDirectory() as tmp:
            def port():
                with socket.socket() as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]
            sp, vp = port(), port()
            processes = []
            env = dict(os.environ, PYTHONUTF8="1")
            def start(script, *args):
                proc = subprocess.Popen([sys.executable, "-X", "utf8", str(ROOT/script), *args],
                                        cwd=tmp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(proc)
                return proc
            def wait_port(number):
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", number), timeout=.2):
                            return
                    except OSError:
                        time.sleep(.05)
                self.fail("시험 프로세스가 열리지 않음")
            def app(*args):
                r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT/"app.py"), *args,
                                    "--server", f"127.0.0.1:{sp}", "--vehicle", f"127.0.0.1:{vp}"],
                                   cwd=tmp, env=env, text=True, capture_output=True, timeout=15)
                self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
                return r.stdout
            try:
                start("server.py", str(sp))
                wait_port(sp)
                app("issue", "7")
                app("net", "off")
                vehicle = start("vehicle_sim.py", "--port", str(vp), "--flash-file", "vehicle.bin",
                                "--server", f"127.0.0.1:{sp}")
                wait_port(vp)
                app("recovery-request")
                # Vehicle process stopped while the 'phone' visits the server.
                vehicle.terminate()
                vehicle.wait(timeout=5)
                app("recovery-issue", "7", "--new-kid", "8")
                # A new boot invalidates the old request.
                vehicle = start("vehicle_sim.py", "--port", str(vp), "--flash-file", "vehicle.bin",
                                "--server", f"127.0.0.1:{sp}")
                wait_port(vp)
                app("recovery-request")
                app("recovery-issue", "8", "--new-kid", "9")
                app("recovery-apply")
                for _ in range(4):
                    self.assertIn("(정상)", app("open", "9"))
                vehicle.terminate()
                vehicle.wait(timeout=5)
                start("vehicle_sim.py", "--port", str(vp), "--flash-file", "vehicle.bin",
                      "--server", f"127.0.0.1:{sp}")
                wait_port(vp)
                app("register", "9")
                self.assertIn("오프라인 횟수 초과", app("open", "9"))
            finally:
                for proc in processes:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
