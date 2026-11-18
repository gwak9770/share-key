"""C sk_store.c와 같은 두 구역 플래시 모의. 실제 하드웨어 시험을 대신하지 않는다."""
import os
import struct
import zlib
from pathlib import Path

RECORD_SIZE = 256
IMAGE_SIZE = 132
VID = 0xCAFE


class MemoryFlash:
    """1→0 쓰기, 구역 단위 지우기. path를 주면 재실행 간 파일에 보존한다."""
    def __init__(self, sector_size=128 * 1024, path=None):
        if sector_size < 512 or sector_size % RECORD_SIZE:
            raise ValueError("잘못된 저장 구역 크기")
        self.sector_size = sector_size
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            self.data = bytearray(self.path.read_bytes())
            if len(self.data) != 2 * sector_size:
                raise ValueError("저장 파일 크기 불일치: 자동 초기화하지 않음")
        else:
            self.data = bytearray(b"\xff" * (2 * sector_size))
        self.budget = None  # PC 시험 전용: N번의 4바이트 쓰기/지우기 뒤 실패
        self.operations = 0

    def _step(self):
        if self.budget == 0:
            raise OSError("PC 모의 전원 차단")
        if self.budget is not None:
            self.budget -= 1
        self.operations += 1

    def _flush(self):
        if self.path:
            # 보드 플래시가 아닌 PC 파일 모의. 덮어쓰기/전원 차단 내성은 동일하지 않음.
            with self.path.open("wb") as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())

    def read(self, bank, offset, size):
        if bank not in (0, 1) or offset < 0 or size < 0 or offset + size > self.sector_size:
            raise OSError("플래시 범위 초과")
        start = bank * self.sector_size + offset
        return bytes(self.data[start:start + size])

    def program(self, bank, offset, data):
        if offset % 4 or len(data) % 4:
            raise OSError("4바이트 정렬 필요")
        old = self.read(bank, offset, len(data))
        if any((a & b) != b for a, b in zip(old, data)):
            raise OSError("지우기 없이 0→1 쓰기 불가")
        start = bank * self.sector_size + offset
        try:
            for i in range(0, len(data), 4):
                self._step()
                self.data[start + i:start + i + 4] = data[i:i + 4]
        finally:
            self._flush()

    def erase(self, bank):
        self.read(bank, 0, self.sector_size)
        start = bank * self.sector_size
        try:
            for i in range(0, self.sector_size, 4):
                self._step()
                self.data[start + i:start + i + 4] = b"\xff" * 4
        finally:
            self._flush()


class FlashJournal:
    def __init__(self, flash):
        self.flash = flash
        self.sequence = 0
        self.bank = 0
        self.next_offset = 0
        self.image = None
        self.ready = False
        self.damaged_bank = 0
        self.barrier_bank = None

    def load(self):
        best = barrier = highest = 0
        bad = False
        image = None
        self.ready = False
        self.barrier_bank = None
        try:
            for bank in range(2):
                end = 0
                for off in range(0, self.flash.sector_size, RECORD_SIZE):
                    rec = self.flash.read(bank, off, RECORD_SIZE)
                    if rec == b"\xff" * RECORD_SIZE:
                        continue
                    end = off + RECORD_SIZE
                    commit = int.from_bytes(rec[252:], "big")
                    if commit == 0xFFFFFFFF:
                        continue
                    seq = int.from_bytes(rec[8:12], "big")
                    valid = (commit == 0 and rec[:4] == b"SKJ1" and rec[4] == 1
                             and rec[5] <= 1 and int.from_bytes(rec[12:16], "big") == VID
                             and int.from_bytes(rec[248:252], "big") == zlib.crc32(rec[:248])
                             and seq > 0)
                    if not valid:
                        bad = True
                        self.damaged_bank = bank
                        continue
                    highest = max(highest, seq)
                    if rec[5] == 1:
                        if seq > barrier:
                            barrier, self.barrier_bank = seq, bank
                    elif image is not None and seq == best:
                        bad = True
                        self.damaged_bank = bank
                    elif seq > best:
                        best = seq
                        image = rec[16:148]
                        self.bank = bank
                if image is not None and self.bank == bank:
                    self.next_offset = end
            self.sequence = highest
            if not bad:
                self.damaged_bank = self.bank if image is not None else 0
            self.ready = not bad and image is not None and best > barrier
            self.image = image
            return image if self.ready else None
        except OSError:
            self.read_failed = True
            return None

    def _erase(self, bank):
        self.flash.erase(bank)
        if self.flash.read(bank, 0, self.flash.sector_size) != b"\xff" * self.flash.sector_size:
            raise OSError("지우기 검증 실패")

    def _write(self, bank, off, image, barrier=False):
        if self.sequence >= 0xFFFFFFFF:
            raise OSError("기록 순번 소진")
        self.sequence += 1
        rec = bytearray(b"\xff" * RECORD_SIZE)
        rec[:6] = b"SKJ1" + bytes((1, int(barrier)))
        rec[8:16] = struct.pack(">II", self.sequence, VID)
        if image is not None:
            rec[16:148] = image
        rec[248:252] = struct.pack(">I", zlib.crc32(rec[:248]))
        self.flash.program(bank, off, rec[:252])
        if self.flash.read(bank, off, RECORD_SIZE) != rec:
            raise OSError("기록 검증 실패")
        rec[252:] = b"\0" * 4
        self.flash.program(bank, off + 252, rec[252:])
        if self.flash.read(bank, off, RECORD_SIZE) != rec:
            raise OSError("완료 검증 실패")

    def save(self, image):
        if not self.ready:
            return False
        if image == self.image:
            return True
        self.ready = False
        try:
            bank, off = self.bank, self.next_offset
            if off >= self.flash.sector_size:
                bank, off = 1 - bank, 0
                self._erase(bank)
            self._write(bank, off, image)
            self.bank, self.next_offset = bank, off + RECORD_SIZE
            self.image, self.ready = image, True
            return True
        except OSError:
            return False

    def recover(self, image):
        self.read_failed = False
        self.load()
        self.ready = False
        if self.read_failed or self.sequence > 0xFFFFFFFF - 2:
            return False
        try:
            if self.barrier_bank is not None:
                locked = self.barrier_bank
                dest = 1 - locked
                self._erase(dest)
                self._write(dest, 0, image)
                self._erase(locked)
                self.bank, self.next_offset = dest, RECORD_SIZE
                self.image, self.ready = image, True
                return True
            old = self.damaged_bank
            barrier = 1 - old
            self._erase(barrier)
            self._write(barrier, 0, None, barrier=True)
            self._erase(old)
            self._write(old, 0, image)
            self.bank, self.next_offset = old, RECORD_SIZE
            self.image, self.ready = image, True
            return True
        except OSError:
            return False


def encode_state(ver, keys):
    if len(keys) > 8:
        raise ValueError("최대 8키")
    image = bytearray(IMAGE_SIZE)
    image[:4] = struct.pack(">I", ver)
    for i, (kid, k) in enumerate(keys.items()):
        image[4 + i * 16:20 + i * 16] = struct.pack(
            ">IIBBBBBB2x", kid, k["exp"], k["limit"], k["remaining"],
            k["sit"], k["perm"], k["state"], 1)
    return bytes(image)


def decode_state(image):
    if len(image) != IMAGE_SIZE:
        raise ValueError("상태 길이 불일치")
    ver = int.from_bytes(image[:4], "big")
    keys = {}
    for off in range(4, IMAGE_SIZE, 16):
        slot = image[off:off + 16]
        kid, exp, limit, rem, sit, perm, state, used = struct.unpack(">IIBBBBBB2x", slot)
        if used > 1 or slot[14:] != b"\0\0":
            raise ValueError("잘못된 슬롯")
        if not used:
            if any(slot):
                raise ValueError("빈 슬롯 손상")
            continue
        if rem > limit or state > 3 or kid in keys:
            raise ValueError("잘못된 키 상태")
        keys[kid] = dict(exp=exp, limit=limit, remaining=rem, sit=sit, perm=perm, state=state)
    return ver, keys
