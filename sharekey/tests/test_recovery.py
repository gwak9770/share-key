"""PC 모의: production C/Python 동일 시나리오, 전원 차단 주입, 단계별 CLI."""
import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import types
import unittest
import json
import shutil
import urllib.request
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
    DLL.bridge_reauth_config.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    DLL.bridge_mode.argtypes = [ctypes.c_char]
    DLL.bridge_unix.argtypes = [ctypes.c_uint32]


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

    def configure_drive(self, period=1000, grace=500, cutoff=1000):
        return bool(DLL.bridge_reauth_config(period, grace, cutoff))

    def advance(self, ms):
        DLL.bridge_advance(ms)

    def stopped(self, value):
        DLL.bridge_stopped(int(value))


class PythonVehicle:
    mode = "C"

    def __init__(self, image=None):
        self.flash = MemoryFlash(SECTOR)
        if image is not None:
            self.flash.data[:] = image
        self.actions = 0
        self.ms = 0
        self.logs = []
        self.boot()

    def boot(self):
        self.core = VehicleCore(mode=self.mode, log=self.logs.append, storage=FlashJournal(self.flash),
                                clock=lambda: self.ms / 1000)
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

    def configure_drive(self, period=1000, grace=500, cutoff=1000):
        return self.core.configure_reauth(period, grace, cutoff)

    def advance(self, ms):
        self.ms = (self.ms + ms) & 0xFFFFFFFF
        self.core.poll()

    def stopped(self, value):
        self.core.set_stopped(value)


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


class ReauthTests(unittest.TestCase):
    def factories(self):
        return [PythonVehicle, Native] if DLL else [PythonVehicle]

    def ready(self, factory):
        v = factory()
        self.assertEqual(recover(v)[0], "RECOVERED")
        self.assertTrue(v.configure_drive())
        return v

    def status(self, v):
        p = v.send(["DSTATUS"])
        self.assertEqual(p[0], "DSTATE")
        return tuple(int(x, 16) for x in p[1:])  # kid, run, warn, stopped, elapsed, left

    def sync(self, v, entries):
        req = v.sync_request()
        nonce = bytes.fromhex(req[2])
        return v.send(["SYNC", f"{VID:08X}", "00000002", hx(nonce), f"{len(entries):02X}",
                       enc_entries(entries), hx(sync_tag(2, nonce, entries))])

    def test_reauth_counts_no_new_actuation_and_stop_without_count(self):
        for factory in self.factories():
            v = self.ready(factory)
            self.assertEqual(use(v, cmd=2)[-1], "03")
            for left in ("02", "01", "00"):
                v.advance(1000)
                self.assertEqual(use(v, cmd=4)[2:], ["A", "00", left])
            self.assertEqual(v.actions, 1)
            v.advance(1000)
            self.assertEqual(use(v, cmd=4)[2:], ["D", "05", "00"])
            self.assertEqual(self.status(v)[1:3], (1, 1))
            self.assertEqual(use(v, cmd=2)[3], "07")
            self.assertEqual(use(v, cmd=5)[2:], ["A", "00", "00"])
            self.assertEqual(v.actions, 2)
            self.assertEqual(self.status(v)[1], 0)

    def test_timeout_boundary_driving_continues_stopped_cutoff_and_reboot_hold(self):
        for factory in self.factories():
            v = self.ready(factory)
            use(v, cmd=2)
            v.advance(1499)
            self.assertEqual(self.status(v)[1:3], (1, 0))
            v.advance(1)
            self.assertEqual(self.status(v)[1:3], (1, 1))
            v.advance(10000)
            self.assertEqual(self.status(v)[1], 1)
            v.stopped(True)
            v.advance(0)
            v.advance(999)
            self.assertEqual(self.status(v)[1], 1)
            v.advance(1)
            self.assertEqual(self.status(v)[1], 0)
            self.assertEqual(use(v, cmd=2)[3], "07")
            v.boot()
            self.assertEqual(self.status(v)[1], 0)
            self.assertEqual(use(v, cmd=2)[3], "07")

    def test_stopped_timer_starts_after_warning_and_resets_on_drive(self):
        for factory in self.factories():
            v = self.ready(factory)
            v.stopped(True)
            use(v, cmd=2)
            v.advance(1000)
            self.assertEqual(self.status(v)[1:3], (1, 0))
            v.advance(500)
            self.assertEqual(self.status(v)[1:3], (1, 1))
            v.advance(500)
            v.stopped(False)
            v.advance(2000)
            self.assertEqual(self.status(v)[1], 1)
            v.stopped(True)
            v.advance(0)
            v.advance(999)
            self.assertEqual(self.status(v)[1], 1)
            v.advance(1)
            self.assertEqual(self.status(v)[1], 0)

    def test_other_keys_repeated_start_and_forged_auth_cannot_refresh_or_force_hold(self):
        for factory in self.factories():
            v = self.ready(factory)
            register(v, 8)
            self.assertEqual(use(v, cmd=4)[3], "07")
            use(v, cmd=2)
            before = v.raw()
            self.assertEqual(use(v, 8, 4)[3], "07")
            self.assertEqual(use(v, 8, 5)[3], "07")
            self.assertEqual(use(v, 8, 2)[3], "07")
            self.assertEqual(use(v, 7, 2)[3], "07")
            self.assertEqual(v.raw(), before)
            nonce = v.send(["REQ", "00000007", "04"])[2]
            self.assertEqual(v.send(["RESP", "00000007", "04", nonce, "00" * 32])[3], "01")
            self.assertEqual(self.status(v)[2], 0)
            v.advance(1499)
            self.assertEqual(self.status(v)[2], 0)
            v.advance(1)
            self.assertEqual(self.status(v)[2], 1)

    def test_only_listed_valid_sync_clears_hold_and_revocation_stays(self):
        for factory in self.factories():
            v = self.ready(factory)
            use(v, cmd=2)
            v.advance(1500)
            self.assertEqual(self.sync(v, [])[0], "SYNCACK")
            self.assertEqual(use(v, cmd=2)[3], "07")
            self.assertEqual(self.status(v)[2], 1)
            self.assertEqual(self.sync(v, [(7, 0)])[0], "SYNCACK")
            self.assertEqual(self.status(v)[2], 0)
            self.assertEqual(use(v, cmd=4)[2:], ["A", "00", "03"])
            self.sync(v, [(7, 1)])
            self.assertEqual(self.status(v)[1:3], (1, 1))
            self.assertEqual(use(v, cmd=5)[2], "A")
            self.sync(v, [(7, 0)])
            self.assertEqual(use(v, cmd=2)[3], "03")

    def test_return_preserves_restriction_but_authenticated_stop_works(self):
        for factory in self.factories():
            v = self.ready(factory)
            use(v, cmd=2)
            self.assertEqual(use(v, cmd=3)[2], "A")
            self.assertEqual(self.status(v)[1:3], (1, 1))
            self.assertEqual(use(v, cmd=5)[2], "A")
            self.assertEqual(use(v, cmd=2)[3], "09")

    def test_storage_failure_does_not_force_stop_and_authenticated_stop_still_works(self):
        for factory in self.factories():
            v = self.ready(factory)
            use(v, cmd=2)
            v.cut(0)
            self.assertEqual(use(v, cmd=4)[3], "0A")
            self.assertTrue(v.locked)
            self.assertEqual(self.status(v)[1:3], (1, 1))
            self.assertEqual(use(v, cmd=5)[2], "A")
            self.assertEqual(self.status(v)[1], 0)

    def test_wire_cannot_set_motion_and_recovery_during_drive_is_denied(self):
        for factory in self.factories():
            v = self.ready(factory)
            use(v, cmd=2)
            self.assertEqual(v.send(["STOPPED", "1"]), ["ERR", "FF"])
            self.assertEqual(self.status(v)[3], 0)
            self.assertEqual(v.send(["RBEGIN"]), ["RFAIL", "07"])
            self.assertFalse(v.configure_drive(period=50000))

    def test_timer_unsigned_wrap(self):
        for factory in self.factories():
            v = self.ready(factory)
            if isinstance(v, Native):
                DLL.bridge_clock(0xFFFFFF00)
            else:
                v.ms = 0xFFFFFF00
            use(v, cmd=2)
            v.advance(1499)
            self.assertEqual(self.status(v)[2], 0)
            v.advance(1)
            self.assertEqual(self.status(v)[2], 1)

    @unittest.skipUnless(DLL, "C bridge 필요")
    def test_held_snapshot_matches_python_and_c(self):
        p, c = self.ready(PythonVehicle), self.ready(Native)
        self.assertEqual(use(p, cmd=2), use(c, cmd=2))
        p.advance(1500)
        c.advance(1500)
        self.assertEqual(p.raw(), c.raw())
        self.assertEqual(self.status(p), self.status(c))
        self.assertEqual(use(p, cmd=5), use(c, cmd=5))


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


class WebReauthTests(unittest.TestCase):
    def test_cli_timer_web_auto_renew_status_and_authenticated_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for source in ROOT.glob("*.py"):
                shutil.copy2(source, tmp/source.name)
            chosen = set()
            def port():
                while True:
                    with socket.socket() as s:
                        s.bind(("127.0.0.1", 0))
                        number = s.getsockname()[1]
                    if number not in chosen:
                        chosen.add(number)
                        return number
            sp, vp, wp = port(), port(), port()
            processes = []
            env = dict(os.environ, PYTHONUTF8="1")
            def start(script, *args):
                proc = subprocess.Popen([sys.executable, "-X", "utf8", str(tmp/script), *args],
                                        cwd=tmp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(proc)
            def wait_port(number):
                deadline = time.monotonic()+8
                while time.monotonic()<deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", number), timeout=.2):
                            return
                    except OSError:
                        time.sleep(.05)
                self.fail("시연 시험 프로세스 시작 실패")
            def cli(*args):
                result = subprocess.run([sys.executable,"-X","utf8",str(tmp/"app.py"),*args,
                    "--server",f"127.0.0.1:{sp}","--vehicle",f"127.0.0.1:{vp}"],
                    cwd=tmp,env=env,text=True,encoding="utf-8",capture_output=True,timeout=12)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                return result.stdout
            def api(cmd):
                req=urllib.request.Request(f"http://127.0.0.1:{wp}/api",
                    data=json.dumps(dict(cmd=cmd,kid="7",limit=4)).encode(),headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req,timeout=4) as r:
                    return json.load(r)
            try:
                start("server.py",str(sp)); wait_port(sp)
                cli("issue","7"); cli("net","off")
                start("vehicle_sim.py","--port",str(vp),"--server",f"127.0.0.1:{sp}",
                      "--reauth-period","0.5","--reauth-grace","0.5","--stop-cutoff","0.5")
                wait_port(vp); cli("register","7")
                self.assertIn("재인증: 허용",cli("drive","7","--period","0.1","--cycles","1"))
                cli("stop","7")
                start("web_app.py","--port",str(wp),"--server",f"127.0.0.1:{sp}",
                      "--vehicle",f"127.0.0.1:{vp}","--reauth-period","0.1")
                wait_port(wp)
                with urllib.request.urlopen(f"http://127.0.0.1:{wp}/",timeout=4) as r:
                    html=r.read().decode()
                self.assertIn('id="drivestatus"',html)
                self.assertEqual(api("start")["res"]["code"],"A")
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    state=api("driving-status")
                    if state.get("warning"):
                        break
                    time.sleep(.05)
                else:
                    self.fail("웹 자동 재인증·횟수 소진 경고 없음")
                self.assertTrue(state["running"])
                self.assertFalse(state["stopped"])
                self.assertIn("오프라인 횟수 초과",cli("open","7"))
                self.assertFalse(api("stopped")["ok"])
                self.assertEqual(api("stop")["res"]["code"],"A")
                self.assertFalse(api("driving-status")["running"])
            finally:
                for proc in processes:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=5)


class ClockRollbackTests(unittest.TestCase):
    """S7 시계 되돌림 (00 §6 13). B 방식, 같은 시나리오를 Python과 C(브리지)에 넣는다."""
    T0 = 1_800_000_000
    E = T0 + 3600

    def python_vehicle(self):
        clock = types.SimpleNamespace(unix=self.T0)
        fake = types.SimpleNamespace(time=lambda: clock.unix, monotonic=time.monotonic)
        p = patch("core.time", fake)
        p.start()
        self.addCleanup(p.stop)
        v = PythonVehicle()
        v.mode = "B"
        v.boot()
        v.set_unix = lambda t: setattr(clock, "unix", t)
        return v

    def native_vehicle(self):
        v = Native()
        DLL.bridge_mode(b"B")
        v.set_unix = DLL.bridge_unix
        v.set_unix(self.T0)
        return v

    def scenario(self, v):
        out = []
        self.assertEqual(recover(v)[0], "RECOVERED")
        tag = hx(key_tag(9, self.E, 4, 2, 3))
        self.assertEqual(v.send(["KEY", "00000009", f"{self.E:08X}", "04", "02", "03", tag])[0], "KEYOK")
        def step(t, label):
            v.set_unix(t)
            r = use(v, 9)
            out.append((label, r[2], r[3]))
        step(self.T0, "정상")
        step(self.T0 - 86400, "부팅 중 하루 되돌림")
        step(self.T0 + 200, "오차 안(+200초)")
        step(self.E + 60, "만료 뒤")
        step(self.E - 600, "만료 뒤 부팅 중 되돌림")
        v.set_unix(self.E + 60)
        v.advance(1000)                         # 주기 저장(10분 간격) — 만료 뒤 시각을 플래시에 남김
        v.boot()
        step(self.T0 + 200, "재부팅 뒤 마지막 허용 시각으로 되돌림")
        step(self.E + 120, "재부팅 뒤 실제 시각")
        return out

    def expected(self):
        return [("정상", "A", "00"), ("부팅 중 하루 되돌림", "D", "04"), ("오차 안(+200초)", "A", "00"),
                ("만료 뒤", "D", "04"), ("만료 뒤 부팅 중 되돌림", "D", "04"),
                ("재부팅 뒤 마지막 허용 시각으로 되돌림", "D", "04"), ("재부팅 뒤 실제 시각", "D", "04")]

    def test_python_rollback_denied_and_floor_survives_reboot(self):
        v = self.python_vehicle()
        self.assertEqual(self.scenario(v), self.expected())
        self.assertIn("CLOCK ROLLBACK: period keys denied (04)", v.logs)

    @unittest.skipUnless(DLL, "C bridge 필요")
    def test_c_matches_python_and_same_flash_bytes(self):
        n = self.native_vehicle()
        self.assertEqual(self.scenario(n), self.expected())
        p = self.python_vehicle()
        self.scenario(p)
        self.assertEqual(n.raw(), p.raw())

    def test_old_format_record_has_no_floor(self):
        from storage import decode_clock, encode_state, IMAGE_SIZE
        image = bytearray(encode_state(1, {}, 123))
        self.assertEqual((IMAGE_SIZE, decode_clock(image)), (136, 123))
        image[132:136] = b"\xff" * 4             # 11/28 이전 기록: 132바이트 뒤가 지워진 FF
        self.assertEqual(decode_clock(image), 0)

    def test_without_defense_rollback_would_reopen(self):
        """대조군: 하한이 없으면(새 차량, 저장 없음) 되돌린 시각에서는 허용된다 = 방어가 하는 일."""
        v = self.python_vehicle()
        self.assertEqual(recover(v)[0], "RECOVERED")
        tag = hx(key_tag(9, self.E, 4, 2, 3))
        v.send(["KEY", "00000009", f"{self.E:08X}", "04", "02", "03", tag])
        v.set_unix(self.E + 60)
        self.assertEqual(use(v, 9)[2:4], ["D", "04"])
        v.core.clock_seen = 0                   # 방어를 끈 것과 같음
        v.set_unix(self.E - 600)
        self.assertEqual(use(v, 9)[2:4], ["A", "00"])


class RtcFallbackTests(unittest.TestCase):
    """1128 RTC 고장(시각 0): B·D 기간 키는 04, 시계 오류용 1회 키(EXP=FFFFFFFF)는 그때만 횟수로 허용.
    같은 시나리오를 Python과 C(브리지)에 넣는다 (00 §6 14)."""
    T0 = 1_800_000_000
    E = T0 + 3600

    def python_vehicle(self, mode):
        clock = types.SimpleNamespace(unix=self.T0)
        fake = types.SimpleNamespace(time=lambda: clock.unix, monotonic=time.monotonic)
        p = patch("core.time", fake)
        p.start()
        self.addCleanup(p.stop)
        v = PythonVehicle()
        v.mode = mode
        v.boot()
        v.set_unix = lambda t: setattr(clock, "unix", t)
        return v

    def native_vehicle(self, mode):
        v = Native()
        DLL.bridge_mode(mode.encode())
        v.set_unix = DLL.bridge_unix
        v.set_unix(self.T0)
        return v

    def sync_valid(self, v, kids):
        req = v.sync_request()
        nonce = bytes.fromhex(req[2])
        entries = [(k, 0) for k in kids]
        return v.send(["SYNC", f"{VID:08X}", "00000002", hx(nonce), f"{len(entries):02X}",
                       enc_entries(entries), hx(sync_tag(2, nonce, entries))])

    def scenario(self, v):
        out = []
        self.assertEqual(recover(v)[0], "RECOVERED")
        for kid, exp, limit in ((9, self.E, 4), (0x70, EXP, 1)):
            tag = hx(key_tag(kid, exp, limit, 2, 3))
            self.assertEqual(v.send(["KEY", f"{kid:08X}", f"{exp:08X}", f"{limit:02X}", "02", "03", tag])[0],
                             "KEYOK")
        def step(t, kid, label):
            v.set_unix(t)
            r = use(v, kid)
            out.append((label, r[2], r[3], r[4]))
        step(self.T0, 9, "시계 정상: 기간 키")
        step(self.T0, 0x70, "시계 정상: 1회 키는 거부")
        step(0, 9, "RTC 고장: 기간 키 04")
        step(0, 0x70, "RTC 고장: 1회 키 허용")
        step(0, 0x70, "RTC 고장: 1회 키 두 번째 05")
        v.set_unix(0)
        self.assertEqual(self.sync_valid(v, [9, 0x70])[0], "SYNCACK")
        step(0, 0x70, "온라인 동기화 뒤 다시 1회")
        step(self.T0 + 10, 9, "시계 복구: 기간 키 다시 허용")
        step(self.E + 60, 9, "시계 복구 뒤 만료")
        return out

    def expected(self, mode):
        rem9 = ("03", "03") if mode == "D" else ("FF", "FF")   # 거부는 횟수를 줄이지 않음
        return [("시계 정상: 기간 키", "A", "00", rem9[0]), ("시계 정상: 1회 키는 거부", "D", "04", "01"),
                ("RTC 고장: 기간 키 04", "D", "04", rem9[1]), ("RTC 고장: 1회 키 허용", "A", "00", "00"),
                ("RTC 고장: 1회 키 두 번째 05", "D", "05", "00"), ("온라인 동기화 뒤 다시 1회", "A", "00", "00"),
                ("시계 복구: 기간 키 다시 허용", "A", "00", "03" if mode == "D" else "FF"),
                ("시계 복구 뒤 만료", "D", "04", "03" if mode == "D" else "FF")]

    def test_python_b_and_d(self):
        for mode in "BD":
            with self.subTest(mode=mode):
                v = self.python_vehicle(mode)
                self.assertEqual(self.scenario(v), self.expected(mode))
                self.assertIn("CLOCK INVALID: period keys denied (04)", v.logs)

    def test_python_c_mode_ignores_clock(self):
        v = self.python_vehicle("C")
        self.assertEqual(recover(v)[0], "RECOVERED")
        v.set_unix(0)
        self.assertEqual(use(v)[2:4], ["A", "00"])

    @unittest.skipUnless(DLL, "C bridge 필요")
    def test_c_matches_python_and_same_flash_bytes(self):
        for mode in "BD":
            with self.subTest(mode=mode):
                n = self.native_vehicle(mode)
                self.assertEqual(self.scenario(n), self.expected(mode))
                p = self.python_vehicle(mode)
                self.scenario(p)
                self.assertEqual(n.raw(), p.raw())


class ClockKeyServerTests(unittest.TestCase):
    """1128 서버: 시계 오류용 1회 키 발급 조건과 원래 키 종료 시 연쇄 취소."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.STATE_FILE = str(Path(self.temp.name) / "server_state.json")
        server.st = {"ver": 1, "net": 1, "keys": {"00000007":
                     dict(exp=int(time.time()) + 3600, limit=4, sit=2, perm=3, state=0)}}

    def tearDown(self):
        self.temp.cleanup()

    def ask(self, kid=7, new=0x70, proof=None):
        proof = clock_key_proof(kid, new) if proof is None else proof
        return server.handle(None, ["CLKISSUE", f"{kid:08X}", f"{new:08X}", hx(proof)])

    def test_issue_fields_and_idempotent(self):
        r = self.ask()
        self.assertEqual(r[:6], ["CLKISSUED", "00000070", "FFFFFFFF", "01", "02", "03"])
        self.assertEqual(r[6], hx(key_tag(0x70, EXP, 1, 2, 3)))
        self.assertEqual(self.ask(), r)
        self.assertEqual(server.st["ver"], 2)
        self.assertEqual(server.st["keys"]["00000007"]["state"], 0)   # 원래 키는 그대로 유효

    def test_rejections(self):
        self.assertEqual(self.ask(proof=bytes(32)), ["ERR", "01"])
        self.assertEqual(self.ask(kid=8), ["ERR", "08"])
        self.ask()
        self.assertEqual(self.ask(kid=0x70, new=0x71), ["ERR", "06"])  # 1회 키로 또 받기 금지
        for state, exp, why in ((1, None, "03"), (2, None, "09"), (0, 1, "04")):
            k = server.st["keys"]["00000007"]
            k.update(state=state, **({} if exp is None else {"exp": exp}))
            self.assertEqual(self.ask(new=0x72), ["ERR", why])
            k.update(state=0, exp=int(time.time()) + 3600)

    def test_one_active_child_and_cascade_revoke(self):
        self.ask()
        self.ask(new=0x71)
        self.assertEqual(server.st["keys"]["00000070"]["state"], 1)
        self.assertEqual(server.st["keys"]["00000071"]["state"], 0)
        server.handle(None, ["REVOKE", "00000007"])
        server.handle(None, ["NET", "1"])             # 다음 요청 때 연쇄 취소
        self.assertEqual(server.st["keys"]["00000071"]["state"], 1)
        server.st["keys"]["00000007"].update(state=0)
        server.st["keys"]["00000072"] = dict(exp=EXP, limit=1, sit=2, perm=3, state=0, parent="00000007")
        server.st["keys"]["00000007"]["exp"] = 1      # 원래 키 만료 → 연쇄 취소
        server.handle(None, ["NET", "1"])
        self.assertEqual(server.st["keys"]["00000072"]["state"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
