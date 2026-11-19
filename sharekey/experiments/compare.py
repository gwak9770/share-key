"""비교 실험 v2 (docs/02_final_roadmap.md §5, 00 §10 T06). PC 모의.

    python3 sharekey/experiments/compare.py --seed 20261116 --out docs/results/

방식
  A, B(대여 기간), C(N = 2·4·8·16), D(B + C N=4)  ── sharekey/core.py 판단 그대로
  D-현실(00 §7 D3 후보)                          ── core.py에 없는 규칙이라 이 파일 안의
      Python 모의(Realistic). 대여 기간 안 오프라인 상한 {무제한, 10회, 20회, 12시간, 24시간}
      × 기간 끝 뒤 유예 M {0, 15, 30, 60분}. 반납 즉시 무효는 이 상황들에 나오지 않는다.

시간
  분 단위 사건 순서. core.py의 판단 코드는 바꾸지 않고, 이 실험 안에서만 core.py가 읽는
  time 모듈을 가짜 시계(FakeTime)로 바꿔 끼운다(유효기간 EXP·nonce 수명용).
  운행 재인증 시계는 VehicleCore의 clock= 인자로 같은 가짜 시계를 준다.

모의 규칙 (conditions.csv 한 줄마다, 시간은 대여 시작 = 0분)
  - 대여 시작에 키 등록(EXP = 대여 끝), 서버와 동기화(온라인).
  - 온라인 구간: [0, offline_start) 와 [offline_start + offline_len, ∞).
    온라인 구간의 사건 직전에는 동기화가 한 번 된다고 본다(실제 주기 2초).
  - 오프라인 구간에는 동기화가 없다. 서버 취소(revoke_at)는 차량에 전달되지 않는다.
  - opens가 "N"/"N+1"이면 그 방식의 N(C·D-현실 횟수 상한), 없으면 N = 4로 정한다.

상황 1·2: 시도 시각 = first_try + i × interval (i = 0 … opens-1), 문열기(01).
  - 상황 1: 취소 뒤 허용 수, 취소 시각부터 마지막 허용까지 시간(분).
  - 상황 2: 대여 기간 안 시도의 거부 수 / 시도 수. 대여 끝 뒤 시도는 따로 센다.
상황 3 (계속 운행): first_try(= 취소 시각)에 시동(02). 그 뒤 opens개 주기, 주기 길이 interval:
  주기 앞 절반은 주행, 뒤 절반은 정차(차량 로컬 정차 입력). 주기 시작에 시동이 꺼져 있으면
  다시 시동(02)을 시도한다. 이용자 앱은 시동 중 재인증(04)을 T분마다 보낸다.
  재인증 {끔, T = 10·30·60분}, 유예 G = T/2, 정차 컷오프 600초(00 §6 12). 1분 간격으로 진행.
  - 시동 허용 수, 시동이 켜져 있던 시간(분), 첫 경고까지 시간(분).
  - 관찰 구간은 opens × interval. 재인증 끔은 정차해도 끄지 않으므로 관찰 구간 전체가 상한이다.
상황 4 (재부팅): 상황 1과 같은 시도. 05(횟수 초과)로 거부되면 재부팅 → 키 재등록 → 같은 시도를
  다시 한다. 재부팅은 reboots(r)번까지. 플래시 끔(RAM, 재부팅 때 초기화) / 켬(core.py 저장 그대로).
  - 취소 뒤 총 허용 수, 그 수가 N을 넘는가(평가 축 ④).

본표는 모든 방식의 시도가 같은 조건만 쓴다(B3·B4는 방식의 N에 따라 시도 수가 달라 뺀다).
"""
import argparse
import csv
import math
import os
import statistics
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # sharekey/

import core  # noqa: E402
from common import VID, auth_tag, derive, enc_entries, hx, key_tag, sync_tag  # noqa: E402
from core import VehicleCore  # noqa: E402
from storage import FlashJournal, MemoryFlash, encode_state  # noqa: E402
import make_conditions  # noqa: E402

KID = 0x00000007
PERM = 0x03
N_DEFAULT = 4
BASE = 1_800_000_000          # 가짜 시계의 대여 시작 시각(초). EXP가 32비트 안에 들도록
CUTOFF_S = 600
REAUTH_T = [None, 10, 30, 60]


class FakeTime:
    """core.py 안의 time.time()·time.monotonic()이 읽는 가짜 시계 (분 단위로 진행)."""

    def __init__(self):
        self.now_min = 0.0

    def time(self):
        return BASE + self.now_min * 60

    def monotonic(self):
        return self.now_min * 60


CLOCK = FakeTime()
core.time = types.SimpleNamespace(time=CLOCK.time, monotonic=CLOCK.monotonic)   # 이 실험 안에서만

CORE_METHODS = [("A", None), ("B", None)] + [("C", n) for n in (2, 4, 8, 16)] + [("D", 4)]
REAL_CAPS = [("inf", None), ("n", 10), ("n", 20), ("h", 12), ("h", 24)]
REAL_M = [0, 15, 30, 60]
REAL_METHODS = [("R", (cap, v, m)) for cap, v in REAL_CAPS for m in REAL_M]
S12_METHODS = CORE_METHODS + REAL_METHODS

RAW_FIELDS = ["situation", "cond_id", "kind", "method", "variant", "try", "t_min", "online",
              "after_rental", "result", "reason"]
S3_FIELDS = ["cond_id", "kind", "method", "variant", "starts_ok", "starts_tried",
             "engine_min", "horizon_min", "first_warn_min"]


def label(method, param):
    if method == "C":
        return f"C(N={param})"
    if method == "D":
        return "D(N=4)"
    if method == "R":
        cap, v, m = param
        c = "무제한" if cap == "inf" else (f"{v}회" if cap == "n" else f"{v}시간")
        return f"D-현실({c}, M={m})"
    return method


def n_of(method, param):
    if method in ("C", "D"):
        return param
    if method == "R" and param[0] == "n":
        return param[1]
    return N_DEFAULT


def num(v):
    return float(v) if v != "" else None


# ---------------------------------------------------------------- 차량 (core.py)
class Car:
    """VehicleCore를 메시지로만 다룬다."""

    def __init__(self, mode, limit, exp_min, storage=None, reauth_t=None):
        kw = dict(clock=CLOCK.monotonic, stop_cutoff=CUTOFF_S, reauth_enabled=reauth_t is not None)
        if reauth_t is not None:
            kw.update(reauth_period=reauth_t * 60, reauth_grace=reauth_t * 30)
        self.core = VehicleCore(mode, log=lambda *a: None, storage=storage, **kw)
        exp = int(BASE + exp_min * 60)
        self.key = ["KEY", f"{KID:08X}", f"{exp:08X}", f"{limit:02X}", "02", f"{PERM:02X}",
                    hx(key_tag(KID, exp, limit, 2, PERM))]
        self.register()

    def register(self):
        assert self.core.handle(self.key) == ["KEYOK", f"{KID:08X}"]

    def sync(self, ver, revoked):
        req = self.core.make_syncreq()
        ents = [(KID, 1 if revoked else 0)]
        tag = sync_tag(ver, bytes.fromhex(req[2]), ents)
        msg = ["SYNC", f"{VID:08X}", f"{ver:08X}", req[2], f"{len(ents):02X}", enc_entries(ents), hx(tag)]
        assert self.core.apply_sync(msg)

    def use(self, cmd):
        chal = self.core.handle(["REQ", f"{KID:08X}", f"{cmd:02X}"])
        if chal[0] != "CHAL":
            return chal[2], chal[3]
        nonce = bytes.fromhex(chal[2])
        tag = auth_tag(derive(KID), KID, cmd, nonce)
        res = self.core.handle(["RESP", f"{KID:08X}", f"{cmd:02X}", hx(nonce), hx(tag)])
        return res[2], res[3]


# ---------------------------------------------------------------- D-현실 (Python 모의)
class Realistic:
    """00 §7 D3 후보. 대여 기간(+유예 M) 안에서만, 오프라인 상한(횟수/시간) 안이면 허용."""

    def __init__(self, param, exp_min):
        self.cap, self.v, self.m = param
        self.exp_min = exp_min
        self.revoked, self.last_sync, self.used = False, 0.0, 0

    def sync(self, revoked):
        self.revoked, self.last_sync, self.used = revoked, CLOCK.now_min, 0

    def use(self, cmd):
        t = CLOCK.now_min
        if self.revoked:
            return "D", "03"
        if t > self.exp_min + self.m:
            return "D", "04"
        if self.cap == "n" and self.used >= self.v:
            return "D", "05"
        if self.cap == "h" and t - self.last_sync > self.v * 60:
            return "D", "05"
        self.used += 1
        return "A", "00"


class Vehicle:
    """상황 1·2에서 방식에 따라 Car 또는 Realistic을 쓴다."""

    def __init__(self, method, param, row):
        rental = num(row["rental_min"])
        if method == "R":
            self.v, self.ver = Realistic(param, rental), None
        else:
            self.v = Car(method, n_of(method, param), rental)

    def sync(self, revoked):
        if isinstance(self.v, Realistic):
            self.v.sync(revoked)
        else:
            self.v.sync(2 if revoked else 1, revoked)

    def use(self, cmd):
        return self.v.use(cmd)


# ---------------------------------------------------------------- 상황별 실행
def parse(row, method, param):
    n_eff = n_of(method, param)
    opens = {"N": n_eff, "N+1": n_eff + 1}.get(row["opens"])
    opens = opens if opens is not None else int(row["opens"])
    off_start, off_len = num(row["offline_start"]), num(row["offline_len"])
    return dict(sit=int(row["situation"]), rental=num(row["rental_min"]), off_start=off_start,
                off_end=off_start + off_len, revoke=num(row["revoke_at"]), first=num(row["first_try"]),
                interval=num(row["interval"]), opens=opens,
                reboots=int(row["reboots"]) if row["reboots"] else 0, n=n_eff)


def online(c, t):
    return not (c["off_start"] <= t < c["off_end"])


def revoked_at(c, t):
    return c["revoke"] is not None and t >= c["revoke"]


def raw_row(row, method, variant, i, t, c, res, why):
    return {"situation": row["situation"], "cond_id": row["cond_id"], "kind": row["kind"],
            "method": method, "variant": variant, "try": i, "t_min": t, "online": int(online(c, t)),
            "after_rental": int(t > c["rental"]), "result": res, "reason": why}


def run_s12(row, method, param):
    c = parse(row, method, param)
    CLOCK.now_min = 0.0
    car = Vehicle(method, param, row)
    car.sync(False)
    out = []
    for i in range(c["opens"]):
        t = round(c["first"] + i * c["interval"], 1)
        CLOCK.now_min = t
        if online(c, t):
            car.sync(revoked_at(c, t))
        res, why = car.use(1)
        out.append(raw_row(row, method, label(method, param), i + 1, t, c, res, why))
    return out


def run_s4(row, method, param, flash_on):
    c = parse(row, method, param)
    CLOCK.now_min = 0.0
    flash = None
    if flash_on:
        flash = MemoryFlash(sector_size=4096)
        assert FlashJournal(flash).recover(encode_state(0, {}))   # 빈 저장 영역 초기화(서버 승인 복구에 해당)

    def boot():
        return Car(method, c["n"], c["rental"], storage=FlashJournal(flash) if flash_on else None)

    car = boot()
    car.sync(1, False)
    variant = label(method, param) + (" 플래시 켬" if flash_on else " 플래시 끔")
    out, left = [], c["reboots"]
    for i in range(c["opens"]):
        t = round(c["first"] + i * c["interval"], 1)
        CLOCK.now_min = t
        while True:
            if online(c, t):
                car.sync(2 if revoked_at(c, t) else 1, revoked_at(c, t))
            res, why = car.use(1)
            out.append(raw_row(row, method, variant, i + 1, t, c, res, why))
            if res == "A" or why != "05" or left == 0:
                break
            left -= 1
            car = boot()                       # 전원 차단 → 재부팅 → KEY 재등록(boot 안에서)
    return out


def run_s3(row, method, param, reauth_t):
    c = parse(row, method, param)
    CLOCK.now_min = 0.0
    car = Car(method, c["n"], c["rental"], reauth_t=reauth_t)
    car.sync(1, False)
    k = car.core
    t0 = c["first"]
    horizon = c["opens"] * c["interval"]
    ok = tried = 0
    engine = 0.0
    first_warn = None
    next_reauth = None
    steps = int(math.ceil(horizon))
    for s in range(steps + 1):
        t = round(t0 + s, 1)
        CLOCK.now_min = t
        cyc_pos = (s % c["interval"]) if c["interval"] else 0
        k.set_stopped(cyc_pos >= c["interval"] / 2)
        if online(c, t):
            car.sync(2 if revoked_at(c, t) else 1, revoked_at(c, t))
        k.poll()
        cycle_start = s == 0 or int(s // c["interval"]) != int((s - 1) // c["interval"])
        if cycle_start and s < horizon and not k.engine_running:
            tried += 1
            res, _ = car.use(2)
            if res == "A":
                ok += 1
                next_reauth = t + reauth_t if reauth_t else None
        if reauth_t and k.engine_running and next_reauth is not None and t >= next_reauth:
            car.use(4)
            next_reauth += reauth_t
        k.poll()
        if k.engine_warning and first_warn is None:
            first_warn = round(t - t0, 1)
        if k.engine_running and s < steps:
            engine += 1
    return {"cond_id": row["cond_id"], "kind": row["kind"], "method": method,
            "variant": label(method, param) + (f" 재인증 {reauth_t}분" if reauth_t else " 재인증 끔"),
            "starts_ok": ok, "starts_tried": tried, "engine_min": engine,
            "horizon_min": steps, "first_warn_min": "" if first_warn is None else first_warn}


# ---------------------------------------------------------------- 요약
def same_tries(c):
    return c["kind"] == "random" or not c["kind"].startswith(("B3", "B4"))


def summarize(raw, s3, conds):
    by = {}
    for r in raw:
        by.setdefault((r["situation"], r["variant"]), {}).setdefault(r["cond_id"], []).append(r)
    revoke_at = {c["cond_id"]: num(c["revoke_at"]) for c in conds}
    ids = {s: [c["cond_id"] for c in conds if c["situation"] == s and same_tries(c)] for s in "1234"}
    nb = {s: [c["cond_id"] for c in conds if c["situation"] == s and not same_tries(c)] for s in "12"}
    L = []

    def s1_line(name, d, cids):
        cnt, span = [], []
        for cid in cids:
            allow = [r for r in d[cid] if r["result"] == "A"]
            cnt.append(len(allow))
            span.append(max(r["t_min"] for r in allow) - revoke_at[cid] if allow else 0.0)
        return (f"| {name} | {max(cnt)} | {statistics.mean(cnt):.2f} | {sum(1 for x in cnt if x)}/{len(cnt)} | "
                f"{max(span):.1f} | {statistics.mean(span):.1f} |")

    def s2_line(name, d, cids):
        tries = deny = hit = late = late_ok = 0
        for cid in cids:
            inr = [r for r in d[cid] if not r["after_rental"]]
            dn = sum(1 for r in inr if r["result"] != "A")
            tries, deny, hit = tries + len(inr), deny + dn, hit + (dn > 0)
            out = [r for r in d[cid] if r["after_rental"]]
            late, late_ok = late + len(out), late_ok + sum(1 for r in out if r["result"] == "A")
        rate = 100 * deny / tries if tries else 0
        return f"| {name} | {deny}/{tries} | {rate:.1f}% | {hit}/{len(cids)} | {late_ok}/{late} |"

    H1 = ["| 방식 | 취소 뒤 허용 최대 | 평균 | 허용이 1회 이상인 조건 | 취소→마지막 허용 최대(분) | 평균(분) |",
          "|---|---|---|---|---|---|"]
    H2 = ["| 방식 | 거부 / 시도 | 거부율 | 거부가 1회 이상인 조건 | 대여 끝 뒤 시도(허용/전체) |",
          "|---|---|---|---|---|"]
    L += ["## 상황 1 — 취소 뒤 재사용 (평가 축 ①)", "",
          f"조건 {len(ids['1'])}개(무작위 24 + 경계 B1·B2·B5·B6). 값은 조건별 최댓값·평균.", ""] + H1
    L += [s1_line(label(m, p), by[("1", label(m, p))], ids["1"]) for m, p in CORE_METHODS]
    L += ["", "D-현실 (Python 모의, 00 §7 D3 후보):", ""] + H1
    L += [s1_line(label(m, p), by[("1", label(m, p))], ids["1"]) for m, p in REAL_METHODS]

    L += ["", "## 상황 2 — 정상 이용자 거부율 (평가 축 ②)", "",
          f"조건 {len(ids['2'])}개. 거부율 = 대여 기간 안 시도의 거부 수 / 시도 수 ({len(ids['2'])}개 합산).", ""] + H2
    L += [s2_line(label(m, p), by[("2", label(m, p))], ids["2"]) for m, p in CORE_METHODS]
    L += ["", "D-현실 (Python 모의):", ""] + H2
    L += [s2_line(label(m, p), by[("2", label(m, p))], ids["2"]) for m, p in REAL_METHODS]

    L += ["", "## 상황 3 — 계속 운행 (S3)", "",
          f"조건 {len(ids['3'])}개. 시동 허용 수와 시동이 켜져 있던 시간은 조건별 최댓값·평균. "
          "관찰 구간(opens × interval) 안에서만 센다. 경고는 재인증 실패로 생긴 첫 경고.", "",
          "| 방식 | 재인증 | 시동 허용 최대 | 평균 | 시동 켜진 시간 최대(분) | 평균(분) | 관찰 구간 대비 평균 | 경고가 난 조건 |",
          "|---|---|---|---|---|---|---|---|"]
    s3by = {}
    for r in s3:
        s3by.setdefault(r["variant"], {})[r["cond_id"]] = r
    for m, p in CORE_METHODS:
        for T in REAUTH_T:
            v = label(m, p) + (f" 재인증 {T}분" if T else " 재인증 끔")
            rs = [s3by[v][cid] for cid in ids["3"]]
            ok = [r["starts_ok"] for r in rs]
            eng = [r["engine_min"] for r in rs]
            ratio = statistics.mean(r["engine_min"] / r["horizon_min"] for r in rs)
            warned = sum(1 for r in rs if r["first_warn_min"] != "")
            L.append(f"| {label(m, p)} | {'끔' if T is None else f'{T}분'} | {max(ok)} | {statistics.mean(ok):.2f} | "
                     f"{max(eng):.0f} | {statistics.mean(eng):.1f} | {100 * ratio:.0f}% | {warned}/{len(rs)} |")

    L += ["", "## 상황 4 — 재부팅 뒤 재등록 (평가 축 ④)", "",
          f"조건 {len(ids['4'])}개, 재부팅은 조건의 r번까지(05로 거부될 때만). 값은 취소 뒤 총 허용 수.", "",
          "| 방식 | 플래시 | 총 허용 최대 | 평균 | N을 넘은 조건 |", "|---|---|---|---|---|"]
    for m, p in CORE_METHODS:
        for fl in (False, True):
            v = label(m, p) + (" 플래시 켬" if fl else " 플래시 끔")
            d = by[("4", v)]
            cnt = [sum(1 for r in d[cid] if r["result"] == "A") for cid in ids["4"]]
            over = sum(1 for x in cnt if x > n_of(m, p)) if m in ("C", "D") else "—"
            L.append(f"| {label(m, p)} | {'켬' if fl else '끔'} | {max(cnt)} | {statistics.mean(cnt):.2f} | "
                     f"{over if over == '—' else f'{over}/{len(cnt)}'} |")

    L += ["", "## 평가 축 ③ — 갱신 통신량 (계산값, 모든 방식 공통)", "",
          "00 §7 계산값: 2초마다 SYNCREQ 62B + SYNC 약 128B + 키당 12B + SYNCACK 29B = 약 220B + 키당 12B. "
          "실측(T08) 전까지 계산값이다. D-현실도 같은 SYNC를 쓴다고 본다.", "",
          "| 키 수 | 2초당 | 1분당 |", "|---|---|---|"]
    for keys in (1, 8):
        b = 220 + 12 * keys
        L.append(f"| {keys} | {b}B | {b * 30 / 1000:.2f}KB |")

    L += ["", "## N 경계 확인 (B3 정확히 N번째, B4 N+1번째)", "",
          "시도 수가 방식의 N에 따라 달라 본표에서 뺐다. N이 없는 방식은 N = 4로 시도한다. 칸은 허용 / 시도.", ""]
    cols = nb["1"] + nb["2"]
    L += ["| 방식 | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for m, p in S12_METHODS:
        cells = []
        for cid in cols:
            d = by[(cid[1], label(m, p))][cid]
            cells.append(f"{sum(1 for r in d if r['result'] == 'A')}/{len(d)}")
        L.append(f"| {label(m, p)} | " + " | ".join(cells) + " |")
    return L


def main():
    ap = argparse.ArgumentParser(description="비교 실험 v2 (02 §5)")
    ap.add_argument("--seed", type=int, default=make_conditions.SEED)
    ap.add_argument("--conditions", default=None, help="기본: <out>/conditions.csv")
    ap.add_argument("--out", default="docs/results/")
    a = ap.parse_args()

    cpath = a.conditions or os.path.join(a.out, "conditions.csv")
    with open(cpath, encoding="utf-8", newline="") as f:
        conds = list(csv.DictReader(f))
    expect = [{k: str(v) for k, v in r.items()} for r in make_conditions.make_rows(a.seed)]
    if conds != expect:
        sys.exit(f"{cpath}가 seed {a.seed}로 만든 표와 다르다. 조건 표를 바꾸지 말 것.")

    raw, s3 = [], []
    for c in conds:
        sit = c["situation"]
        if sit in ("1", "2"):
            raw += [r for m, p in S12_METHODS for r in run_s12(c, m, p)]
        elif sit == "3":
            s3 += [run_s3(c, m, p, T) for m, p in CORE_METHODS for T in REAUTH_T]
        else:
            raw += [r for m, p in CORE_METHODS for fl in (False, True) for r in run_s4(c, m, p, fl)]

    with open(os.path.join(a.out, "raw.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(raw)
    with open(os.path.join(a.out, "raw_s3.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=S3_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(s3)

    head = ["# 비교 실험 결과 요약 — v2 (PC 모의)", "",
            f"- 생성: `python3 sharekey/experiments/compare.py --seed {a.seed} --out {a.out}`",
            "- 방식: A, B, C(N = 2·4·8·16), D(N = 4) × 상황 1~4, D-현실 20개 후보 × 상황 1·2.",
            "- A·B·C·D는 `sharekey/core.py` 판단 그대로(가짜 시계). D-현실은 core.py에 없는 규칙이라 "
            "`compare.py` 안의 **Python 모의**다.",
            "- 실물 결과가 아니다. 모의 규칙은 `sharekey/experiments/compare.py` 머리말.",
            "- 시도별 결과는 `raw.csv`(상황 1·2·4), 상황 3은 `raw_s3.csv`.",
            "- 읽을 때 주의:",
            "  - 조건 표의 시도 수는 최대 20이다. 그래서 A·B의 \"최대 20\"은 조건의 상한이고, "
            "D-현실 20회 상한은 이 조건 표에서 무제한과 구별되지 않는다.",
            "  - 상황 3의 경고에는 재인증 실패뿐 아니라 다시 온라인이 되어 취소가 동기화된 경우도 들어간다. "
            "재인증 끔은 경고가 나도 정차 컷오프가 없어 관찰 구간 내내 시동이 켜져 있다.",
            "  - D-현실은 상황 1·2만 돌렸다. 상황 3·4에서 D-현실은 D와 같은 재인증·플래시 규칙을 쓴다고 보고 따로 돌리지 않았다.",
            ""]
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(head + summarize(raw, s3, conds)) + "\n")
    print(f"raw.csv {len(raw)}줄, raw_s3.csv {len(s3)}줄, summary.md → {a.out}")


if __name__ == "__main__":
    main()
