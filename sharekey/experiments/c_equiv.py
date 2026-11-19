"""C 동등성 확인 (docs/02_final_roadmap.md §5.5·§5.7 5단계, 00 §10 D6). PC 모의.

    python3 sharekey/experiments/c_equiv.py --out docs/results/

대표 30개 = 방식 A·C(N=4)·D(N=4) × 조건 10개
  (S1-R01~R04, S1-B1, S1-B2, S2-R01~R03, S2-B2: 무작위 + 대여 끝 1분 전·뒤 경계).
같은 조건을 Python(core.py, compare.py의 run_s12)과 C(firmware/stm32/Core의 sharekey.c를
c_equiv/harness.c로 PC 빌드)에 넣고, 시도마다 (허용/거부, 사유 코드)가 같은지 본다.
판단 코드는 바꾸지 않는다. C 빌드 산출물은 임시 폴더에 만들고 저장소에 남기지 않는다.
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import compare  # noqa: E402  (core.time 가짜 시계 교체 포함)
from compare import BASE, CLOCK, KID, PERM, label, n_of, online, parse, revoked_at  # noqa: E402
from common import VID, auth_tag, derive, enc_entries, hx, key_tag, sync_tag  # noqa: E402

CORE_DIR = os.path.join(ROOT, "firmware", "stm32", "Core")
SOURCES = ["Src/sharekey.c", "Src/sk_crypto.c", "Src/sk_store.c"]
PICK = ["S1-R01", "S1-R02", "S1-R03", "S1-R04", "S1-B1", "S1-B2", "S2-R01", "S2-R02", "S2-R03", "S2-B2"]
METHODS = [("A", None), ("C", 4), ("D", 4)]


def build(cc, outdir):
    exe = os.path.join(outdir, "c_equiv_harness")
    cmd = [cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-I", os.path.join(CORE_DIR, "Inc"),
           os.path.join(HERE, "c_equiv", "harness.c"), *[os.path.join(CORE_DIR, s) for s in SOURCES], "-o", exe]
    subprocess.run(cmd, check=True)
    return exe


class CCar:
    """harness를 통해 C 판단 코드를 compare.Car와 같은 방식으로 다룬다."""

    def __init__(self, exe, mode, limit, exp_min):
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.rid = 0
        self.cmd(f"INIT {mode}")
        exp = int(BASE + exp_min * 60)
        tag = hx(key_tag(KID, exp, limit, 2, PERM))
        out = self.send(["KEY", f"{KID:08X}", f"{exp:08X}", f"{limit:02X}", "02", f"{PERM:02X}", tag])
        assert out and out[0][0] == "KEYOK", out

    def cmd(self, text):
        self.tick()
        self.p.stdin.write(text + "\n")
        lines = []
        while True:
            line = self.p.stdout.readline().rstrip("\n")
            if line == ".":
                return lines
            lines.append(line.split("|"))

    def tick(self):
        ms = 1000 + int(round(CLOCK.now_min * 60000))
        self.p.stdin.write(f"T {ms} {int(round(BASE + CLOCK.now_min * 60))}\n")
        self.p.stdout.readline()

    def send(self, fields):
        self.rid = (self.rid + 1) % 256
        rid = f"{self.rid:02X}"
        return [f[1:] for f in self.cmd("|".join([rid, *fields])) if f[0] == rid]

    def sync(self, ver, revoked):
        req = [f for f in self.cmd("POLL") if len(f) > 1 and f[1] == "SYNCREQ"]
        assert req, "SYNCREQ 없음"
        rid, nonce = req[0][0], req[0][3]
        ents = [(KID, 1 if revoked else 0)]
        tag = sync_tag(ver, bytes.fromhex(nonce), ents)
        out = self.cmd("|".join([rid, "SYNC", f"{VID:08X}", f"{ver:08X}", nonce, f"{len(ents):02X}",
                                 enc_entries(ents), hx(tag)]))
        assert any(len(f) > 1 and f[1] == "SYNCACK" for f in out), out

    def use(self, cmd):
        chal = self.send(["REQ", f"{KID:08X}", f"{cmd:02X}"])[0]
        if chal[0] != "CHAL":
            return chal[2], chal[3]
        nonce = bytes.fromhex(chal[2])
        res = self.send(["RESP", f"{KID:08X}", f"{cmd:02X}", hx(nonce),
                         hx(auth_tag(derive(KID), KID, cmd, nonce))])[0]
        return res[2], res[3]

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def run_c(exe, row, method, param):
    c = parse(row, method, param)
    CLOCK.now_min = 0.0
    car = CCar(exe, method, n_of(method, param), c["rental"])
    car.sync(1, False)
    out = []
    for i in range(c["opens"]):
        t = round(c["first"] + i * c["interval"], 1)
        CLOCK.now_min = t
        if online(c, t):
            car.sync(2 if revoked_at(c, t) else 1, revoked_at(c, t))
        out.append(car.use(1))
    car.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="C 동등성 확인 (02 §5.5)")
    ap.add_argument("--out", default="docs/results/")
    ap.add_argument("--cc", default=os.environ.get("CC", "cc"))
    a = ap.parse_args()
    with open(os.path.join(a.out, "conditions.csv"), encoding="utf-8", newline="") as f:
        rows = {r["cond_id"]: r for r in csv.DictReader(f)}
    tmp = tempfile.mkdtemp(prefix="c_equiv_")
    try:
        exe = build(a.cc, tmp)
        lines, same_runs, total_tries, diff_tries = [], 0, 0, 0
        for cid in PICK:
            for m, p in METHODS:
                py = [(r["result"], r["reason"]) for r in compare.run_s12(rows[cid], m, p)]
                cc = run_c(exe, rows[cid], m, p)
                d = sum(1 for x, y in zip(py, cc) if x != y) + abs(len(py) - len(cc))
                total_tries += len(py)
                diff_tries += d
                same_runs += d == 0
                seq = lambda s: " ".join(f"{r}{w}" for r, w in s)
                lines.append(f"| {cid} | {label(m, p)} | {len(py)} | {'일치' if d == 0 else f'불일치 {d}'} | "
                             f"{seq(py)} | {seq(cc) if d else '(같음)'} |")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(PICK) * len(METHODS)
    head = ["# C 동등성 확인 (PC 모의)", "",
            "- 생성: `python3 sharekey/experiments/c_equiv.py --out docs/results/`",
            "- Python: `sharekey/core.py`(compare.py 가짜 시계). C: `firmware/stm32/Core`의 `sharekey.c`·`sk_crypto.c`·"
            "`sk_store.c`를 `sharekey/experiments/c_equiv/harness.c`와 PC 빌드(저장 영역 없음, RAM).",
            "- 같은 조건·같은 시각에 같은 메시지를 넣고 시도마다 (결과, 사유 코드)를 비교한다. 보드 결과가 아니다.",
            f"- 결과: **{same_runs}/{n} 실행 일치**, 시도 {total_tries}개 중 불일치 {diff_tries}개.", "",
            "| 조건 | 방식 | 시도 수 | 판정 | Python (결과+사유) | C (다를 때만) |", "|---|---|---|---|---|---|"]
    text = "\n".join(head + lines) + "\n"
    with open(os.path.join(a.out, "c_equiv.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{same_runs}/{n} 실행 일치, 시도 {total_tries}개 중 불일치 {diff_tries}개")
    sys.exit(0 if same_runs == n else 1)


if __name__ == "__main__":
    main()
