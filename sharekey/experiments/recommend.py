"""추천표 (docs/02_final_roadmap.md §7). compare.py가 만든 raw.csv를 읽어 공유 유형별 추천 방식을 고른다.

    python3 sharekey/experiments/recommend.py --out docs/results/

규칙 (02 §7.2)
  1. 정상 이용자 거부율(②, 상황 2)이 기준(5%) 이하인 방식만 남긴다.
  2. 그중 취소 뒤 최대 사용(①, 상황 1의 취소 뒤 허용 수 최댓값)이 가장 작은 방식.
  2-1. (11/19 추가) 최대가 같으면 취소 뒤 허용 수의 평균이 작은 방식.
  3. 그래도 같으면 재부팅 견고성(④) → 통신량(③). 지금 결과에서는 남은 후보끼리 둘 다 같아
     "공동"으로 적는다(④: 플래시 켬이면 C·D N 초과 0, A·B·D-현실은 횟수 없음 또는 같은 규칙,
     ③: 모든 방식 같은 SYNC).
  4. 남는 방식이 없으면 "기준으로는 막을 수 없음"과 거부율이 가장 낮은 방식을 적는다.
  5. 민감도: 기준 10%일 때 추천도 적는다.

유형 (02 §7.1, 조건 표에서 해당 범위만)
  단기 카셰어링: 대여 30분~6시간 / 장기 렌터카: 대여 1~3일 /
  지하 주차가 잦은 곳: 오프라인 길이 상위 25%(상황별) / 전체: 28개 모두.
  지인·가족 공유(기간 없음 또는 30일)는 조건 표(대여 최대 72시간)에 없어 계산하지 않는다.
B3·B4는 방식마다 시도 수가 달라 뺀다(compare.py 본표와 같음).
"""
import argparse
import csv
import os
import statistics

ORDER = ["A", "B", "C(N=2)", "C(N=4)", "C(N=8)", "C(N=16)", "D(N=4)"]


def load(out):
    with open(os.path.join(out, "conditions.csv"), encoding="utf-8", newline="") as f:
        conds = [c for c in csv.DictReader(f) if c["situation"] in ("1", "2")
                 and not c["kind"].startswith(("B3", "B4"))]
    with open(os.path.join(out, "raw.csv"), encoding="utf-8", newline="") as f:
        raw = [r for r in csv.DictReader(f) if r["situation"] in ("1", "2")]
    return conds, raw


def types(conds):
    def q75(sit):
        lens = sorted(float(c["offline_len"]) for c in conds if c["situation"] == sit)
        return lens[int(len(lens) * 0.75)]
    cut = {s: q75(s) for s in "12"}
    return [
        ("단기 카셰어링 (대여 30분~6시간)", lambda c: 30 <= float(c["rental_min"]) <= 360),
        ("장기 렌터카 (대여 1~3일)", lambda c: 1440 <= float(c["rental_min"]) <= 4320),
        ("지하 주차가 잦은 곳 (오프라인 길이 상위 25%)",
         lambda c: float(c["offline_len"]) >= cut[c["situation"]]),
        ("전체 (28개)", lambda c: True),
    ]


def metrics(conds, raw, pick):
    ids = {s: {c["cond_id"] for c in conds if c["situation"] == s and pick(c)} for s in "12"}
    by = {}
    for r in raw:
        if r["cond_id"] in ids[r["situation"]]:
            by.setdefault(r["variant"], {}).setdefault((r["situation"], r["cond_id"]), []).append(r)
    m = {}
    for v, d in by.items():
        cnt = [sum(1 for r in rs if r["result"] == "A") for (s, _), rs in d.items() if s == "1"]
        inr = [r for (s, _), rs in d.items() if s == "2" for r in rs if r["after_rental"] == "0"]
        deny = sum(1 for r in inr if r["result"] != "A")
        m[v] = dict(max=max(cnt), mean=statistics.mean(cnt), rate=100 * deny / len(inr) if inr else 0.0,
                    deny=deny, tries=len(inr))
    return m, len(ids["1"]), len(ids["2"])


def choose(m, limit):
    ok = {v: x for v, x in m.items() if x["rate"] <= limit}
    if not ok:
        best = min(m, key=lambda v: m[v]["rate"])
        return None, [best]
    key = lambda v: (ok[v]["max"], round(ok[v]["mean"], 6))
    top = min(key(v) for v in ok)
    return top, sorted((v for v in ok if key(v) == top), key=lambda v: (v not in ORDER, ORDER.index(v) if v in ORDER else v))


def block_table(out):
    """상황 1(취소 뒤 재사용)에서 오프라인 중 시도만 세어 막은 비율. 온라인 시도는 서버 취소(A)로도 막힌다."""
    with open(os.path.join(out, "conditions.csv"), encoding="utf-8", newline="") as f:
        ids = {c["cond_id"] for c in csv.DictReader(f) if c["situation"] == "1"
               and not c["kind"].startswith(("B3", "B4"))}
    by = {}
    with open(os.path.join(out, "raw.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["situation"] == "1" and r["cond_id"] in ids:
                by.setdefault(r["variant"], {}).setdefault(r["cond_id"], []).append(r)
    rows = []
    for v, cs in by.items():
        off = [r for rs in cs.values() for r in rs if r["online"] == "0"]
        blk = sum(1 for r in off if r["result"] != "A")
        zero = sum(1 for rs in cs.values() if all(r["result"] != "A" for r in rs))
        rows.append((v, blk, len(off), zero, len(cs)))
    rows.sort(key=lambda x: (x[0] not in ORDER, ORDER.index(x[0]) if x[0] in ORDER else 0, -x[1] / x[2], x[0]))
    L = ["", "## 오프라인 중 취소된 키 시도를 막은 비율 (상황 1)", "",
         "상황 1의 시도 중 **차량이 오프라인일 때**의 시도만 센다. 온라인 시도는 서버 취소가 반영돼 모든 방식이 03으로 "
         "거부하므로 뺐다. \"한 번도 못 쓴 조건\"은 취소 뒤 시도가 모두 거부된 조건 수다(조건 28개, B3·B4 제외).", "",
         "| 방식 | 막은 비율 (오프라인 시도) | 한 번도 못 쓴 조건 |", "|---|---|---|"]
    L += [f"| {v} | {100 * b / n:.1f}% ({b}/{n}) | {z}/{t} |" for v, b, n, z, t in rows]
    return L


def fmt(names):
    if len(names) <= 3:
        return " = ".join(names)
    return " = ".join(names[:3]) + f" 외 {len(names) - 3}개"


def main():
    ap = argparse.ArgumentParser(description="추천표 (02 §7)")
    ap.add_argument("--out", default="docs/results/")
    a = ap.parse_args()
    conds, raw = load(a.out)
    L = ["# 추천표 (PC 모의)", "",
         "- 생성: `python3 sharekey/experiments/recommend.py --out docs/results/` (입력: `raw.csv`, `conditions.csv`)",
         "- 규칙: 02 §7.2. ② 거부율 5% 이하 → ① 취소 뒤 최대 사용이 작은 순 → **같으면 ① 평균이 작은 순(11/19 추가)** "
         "→ ④ → ③. 끝까지 같은 방식은 \"=\"로 함께 적는다.",
         "- A·B·C·D는 PC 모의, D-현실은 Python 모의. 실물 결과가 아니다.",
         "- 조건 표의 시도 수는 최대 20이라 ① 최대 20은 조건의 상한이다. 유형별 조건 수가 적다(아래 표의 조건 수).",
         "- 지인·가족 공유(기간 없음 또는 30일)는 조건 표에 해당 범위가 없어 계산하지 않았다.", "",
         "| 유형 | 조건 수 (상황 1 / 2) | 추천 (기준 5%) | ① 최대 / 평균 | ② 거부율 | 기준 10%일 때 추천 | 같은가 |",
         "|---|---|---|---|---|---|---|"]
    detail = []
    for name, pick in types(conds):
        m, n1, n2 = metrics(conds, raw, pick)
        top5, rec5 = choose(m, 5)
        top10, rec10 = choose(m, 10)
        if top5 is None:
            r = m[rec5[0]]
            cell = f"기준 5%로는 막을 수 없음 (참고: 거부율 최저 {rec5[0]})"
        else:
            r = m[rec5[0]]
            cell = fmt(rec5)
        cell10 = fmt(rec10) if top10 is not None else f"막을 수 없음 (참고: {rec10[0]})"
        same = "같음" if rec5 == rec10 else "다름"
        L.append(f"| {name} | {n1} / {n2} | {cell} | {r['max']} / {r['mean']:.2f} | {r['rate']:.1f}% "
                 f"({r['deny']}/{r['tries']}) | {cell10} | {same} |")
        detail += ["", f"### {name}", "", "| 방식 | ① 최대 | ① 평균 | ② 거부율 | 5% 통과 |", "|---|---|---|---|---|"]
        for v in sorted(m, key=lambda v: (m[v]["rate"] > 5, m[v]["max"], m[v]["mean"], v)):
            x = m[v]
            detail.append(f"| {v} | {x['max']} | {x['mean']:.2f} | {x['rate']:.1f}% | {'O' if x['rate'] <= 5 else ''} |")
    L += block_table(a.out)
    L += ["", "## 유형별 전체 순위", "", "5% 통과 방식을 먼저, 그 안에서 ① 최대 → ① 평균 순."] + detail
    with open(os.path.join(a.out, "recommend.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
