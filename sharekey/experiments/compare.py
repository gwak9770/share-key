"""비교 실험 v1 (docs/02_final_roadmap.md §5, 00 §10 T06). PC 모의.

    python3 sharekey/experiments/compare.py --seed 20261116 --out docs/results/

v1 범위: 방식 A, C(N = 2·4·8·16) × 상황 1(취소 뒤 재사용)·2(정상 이용자).
B·D·D-현실, 상황 3·4, 재인증은 v2에서 넣는다.

판단은 sharekey/core.py의 VehicleCore를 그대로 쓰고, 차량과 같은 메시지
(KEY → REQ/CHAL → RESP, SYNCREQ → SYNC)로 주고받는다. 판단 규칙은 바꾸지 않는다.
시간은 가짜 시계(분 단위 사건 순서)로 진행한다.

모의 규칙 (conditions.csv 한 줄마다)
  - 대여 시작(0분)에 키 등록, 서버와 동기화(온라인).
  - 온라인 구간: [0, offline_start) 와 [offline_start + offline_len, ∞).
    온라인 구간의 시도 직전에는 동기화가 한 번 된다고 본다(실제 주기 2초).
  - 오프라인 구간에는 동기화가 없다. 서버 취소(revoke_at)는 차량에 전달되지 않는다.
  - 시도 시각 = first_try + i × interval (i = 0 … opens-1). 명령은 문열기(01).
  - opens가 "N"/"N+1"이면 C는 그 방식의 N, A는 N = 4(D 기준값)로 정한다.
상황별 집계
  - 본표는 모든 방식의 시도가 같은 28개(무작위 24 + 경계 B1·B2·B5·B6)로 낸다.
    B3·B4는 시도 수가 방식의 N에 따라 달라 평균에 섞으면 방식끼리 비교가 안 되므로
    "N 경계 확인" 표로 따로 적는다.
  - 상황 1: 취소 뒤 허용 수, 취소 시각부터 마지막 허용까지 시간(분).
  - 상황 2: 대여 기간 안(시도 시각 ≤ rental_min) 시도의 거부 수 / 시도 수.
    대여가 끝난 뒤 시도(B2 등)는 거부율에서 빼고 따로 센다.
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # sharekey/

from common import VID, auth_tag, derive, enc_entries, hx, key_tag, sync_tag  # noqa: E402
from core import VehicleCore  # noqa: E402
import make_conditions  # noqa: E402

KID = 0x00000007
PERM = 0x03
N_DEFAULT = 4
METHODS = [("A", None)] + [("C", n) for n in (2, 4, 8, 16)]
RAW_FIELDS = ["situation", "cond_id", "kind", "method", "N", "try", "t_min", "online",
              "after_rental", "result", "reason"]


class Car:
    """VehicleCore를 메시지로만 다룬다. 가짜 시계는 분 단위."""

    def __init__(self, mode, limit):
        self.now_min = 0.0
        self.core = VehicleCore(mode, log=lambda *a: None, clock=lambda: self.now_min * 60)
        p = ["KEY", f"{KID:08X}", "FFFFFFFF", f"{limit:02X}", "02", f"{PERM:02X}"]
        p.append(hx(key_tag(KID, 0xFFFFFFFF, limit, 2, PERM)))
        assert self.core.handle(p) == ["KEYOK", f"{KID:08X}"]

    def sync(self, ver, revoked):
        req = self.core.make_syncreq()
        nonce = bytes.fromhex(req[2])
        ents = [(KID, 1 if revoked else 0)]
        tag = sync_tag(ver, nonce, ents)
        msg = ["SYNC", f"{VID:08X}", f"{ver:08X}", req[2], f"{len(ents):02X}", enc_entries(ents), hx(tag)]
        assert self.core.apply_sync(msg)

    def open(self):
        chal = self.core.handle(["REQ", f"{KID:08X}", "01"])
        if chal[0] != "CHAL":
            return chal[2], chal[3]
        nonce = bytes.fromhex(chal[2])
        tag = auth_tag(derive(KID), KID, 1, nonce)
        res = self.core.handle(["RESP", f"{KID:08X}", "01", hx(nonce), hx(tag)])
        return res[2], res[3]


def num(v):
    return float(v) if v != "" else None


def run_one(row, method, n):
    sit = int(row["situation"])
    n_eff = n if n is not None else N_DEFAULT
    opens = {"N": n_eff, "N+1": n_eff + 1}.get(row["opens"])
    opens = opens if opens is not None else int(row["opens"])
    rental, off_start, off_len = num(row["rental_min"]), num(row["offline_start"]), num(row["offline_len"])
    revoke, first, interval = num(row["revoke_at"]), num(row["first_try"]), num(row["interval"])
    off_end = off_start + off_len

    car = Car(method, n_eff)
    car.sync(1, False)                       # 대여 시작: 온라인
    out = []
    for i in range(opens):
        t = round(first + i * interval, 1)
        car.now_min = t
        online = not (off_start <= t < off_end)
        revoked = revoke is not None and t >= revoke
        if online:
            car.sync(2 if revoked else 1, revoked)
        res, why = car.open()
        out.append({"situation": sit, "cond_id": row["cond_id"], "kind": row["kind"],
                    "method": method, "N": n if n is not None else "", "try": i + 1, "t_min": t,
                    "online": int(online), "after_rental": int(t > rental), "result": res,
                    "reason": why})
    return out


def label(method, n):
    return method if n is None else f"C(N={n})"


def summarize(raw, conds):
    by = {}
    for r in raw:
        by.setdefault((r["method"], r["N"]), {}).setdefault(r["cond_id"], []).append(r)
    revoke_at = {c["cond_id"]: num(c["revoke_at"]) for c in conds}
    lines = []
    same = lambda c: c["kind"] == "random" or not c["kind"].startswith(("B3", "B4"))
    s1 = [c["cond_id"] for c in conds if c["situation"] == "1" and same(c)]
    s2 = [c["cond_id"] for c in conds if c["situation"] == "2" and same(c)]
    nb = [c["cond_id"] for c in conds if not same(c)]

    lines += ["## 상황 1 — 취소 뒤 재사용 (평가 축 ①)", "",
              f"조건 {len(s1)}개(무작위 24 + 경계 B1·B2·B5·B6). 값은 조건별 최댓값·평균.", "",
              "| 방식 | 취소 뒤 허용 최대 | 평균 | 허용이 1회 이상인 조건 | 취소→마지막 허용 최대(분) | 평균(분) |",
              "|---|---|---|---|---|---|"]
    for method, n in METHODS:
        d = by[(method, n if n is not None else "")]
        cnt, span = [], []
        for cid in s1:
            allow = [r for r in d[cid] if r["result"] == "A"]
            cnt.append(len(allow))
            span.append(max(r["t_min"] for r in allow) - revoke_at[cid] if allow else 0.0)
        lines.append(f"| {label(method, n)} | {max(cnt)} | {statistics.mean(cnt):.2f} | "
                     f"{sum(1 for c in cnt if c)}/{len(cnt)} | {max(span):.1f} | {statistics.mean(span):.1f} |")

    lines += ["", "## 상황 2 — 정상 이용자 거부율 (평가 축 ②)", "",
              f"조건 {len(s2)}개. 거부율 = 대여 기간 안 시도의 거부 수 / 시도 수 ({len(s2)}개 합산).", "",
              "| 방식 | 거부 / 시도 | 거부율 | 거부가 1회 이상인 조건 | 대여 끝 뒤 시도(허용/전체) |",
              "|---|---|---|---|---|"]
    for method, n in METHODS:
        d = by[(method, n if n is not None else "")]
        tries = deny = hit = late = late_ok = 0
        for cid in s2:
            inr = [r for r in d[cid] if not r["after_rental"]]
            dn = sum(1 for r in inr if r["result"] != "A")
            tries, deny, hit = tries + len(inr), deny + dn, hit + (dn > 0)
            out = [r for r in d[cid] if r["after_rental"]]
            late, late_ok = late + len(out), late_ok + sum(1 for r in out if r["result"] == "A")
        rate = 100 * deny / tries if tries else 0
        lines.append(f"| {label(method, n)} | {deny}/{tries} | {rate:.1f}% | {hit}/{len(s2)} | {late_ok}/{late} |")

    lines += ["", "## N 경계 확인 (B3 정확히 N번째, B4 N+1번째)", "",
              "시도 수가 방식의 N에 따라 달라 본표에서 뺐다. A는 N = 4로 시도한다. 칸은 허용 / 시도.", "",
              "| 방식 | " + " | ".join(nb) + " |", "|---" * (len(nb) + 1) + "|"]
    for method, n in METHODS:
        d = by[(method, n if n is not None else "")]
        cells = [f"{sum(1 for r in d[c] if r['result'] == 'A')}/{len(d[c])}" for c in nb]
        lines.append(f"| {label(method, n)} | " + " | ".join(cells) + " |")
    return lines


def main():
    ap = argparse.ArgumentParser(description="비교 실험 v1 (02 §5)")
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

    conds = [c for c in conds if c["situation"] in ("1", "2")]
    raw = [r for c in conds for m, n in METHODS for r in run_one(c, m, n)]

    with open(os.path.join(a.out, "raw.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(raw)

    head = ["# 비교 실험 결과 요약 — v1 초안 (PC 모의)", "",
            f"- 생성: `python3 sharekey/experiments/compare.py --seed {a.seed} --out {a.out}`",
            "- 범위: 방식 A, C(N = 2·4·8·16) × 상황 1·2. B·D·D-현실, 상황 3·4, 재인증은 v2.",
            "- 판단은 `sharekey/core.py` 그대로, 가짜 시계. 실물 결과가 아니다.",
            "- 모의 규칙은 `sharekey/experiments/compare.py` 머리말. 시도별 결과는 `raw.csv`.",
            "- 축 ③ 통신량(계산값)과 ④ 재부팅 견고성(상황 4)은 v2에서 채운다.", ""]
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(head + summarize(raw, conds)) + "\n")
    print(f"raw.csv {len(raw)}줄, summary.md → {a.out}")


if __name__ == "__main__":
    main()
