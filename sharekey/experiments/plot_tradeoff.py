"""손익 그래프 (docs/02_final_roadmap.md §7.3). 가로 ② 정상 이용자 거부율, 세로 ① 취소 뒤 평균 사용.

    python3 sharekey/experiments/plot_tradeoff.py --out docs/results/

입력: raw.csv·conditions.csv (compare.py 결과), 계산은 recommend.py와 같다(전체 28개 조건).
세로축은 ① 평균이다. ① 최대는 조건 표의 시도 수 상한(20)에 걸려 방식 차이를 잘 보여 주지 못한다.
D-현실은 M=0 후보만 그린다(M이 늘면 ①만 조금 늘고 ②는 같다). 외부 라이브러리 없이 SVG를 쓴다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recommend  # noqa: E402

W, H = 860, 520
L, R, T, B = 80, 230, 56, 70           # 여백 (오른쪽은 범례·라벨)
X_MAX, Y_MAX = 70.0, 6.0
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
CORE, REAL = "#2a78d6", "#eb6834"      # 범주 슬롯 1·2 (validate_palette.js 통과)

CORE_V = ["A", "B", "C(N=2)", "C(N=4)", "C(N=8)", "C(N=16)", "D(N=4)"]
REAL_V = [f"D-현실({c}, M=0)" for c in ("무제한", "20회", "24시간", "10회", "12시간")]
# 같은 점에 겹치는 방식은 라벨 하나로 합친다
MERGE = {"B": "B = D-현실(무제한·20회)", "D-현실(무제한, M=0)": None, "D-현실(20회, M=0)": None}
NUDGE = {"C(N=4)": (8, -10, "start"), "D(N=4)": (10, 16, "start"), "A": (10, 4, "start"),
         "C(N=16)": (8, -8, "start"), "D-현실(12시간, M=0)": (-10, 4, "end")}


def sx(x):
    return L + (W - L - R) * x / X_MAX


def sy(y):
    return T + (H - T - B) * (1 - y / Y_MAX)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/")
    a = ap.parse_args()
    conds, raw = recommend.load(a.out)
    m, n1, n2 = recommend.metrics(conds, raw, lambda c: True)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'font-family="Pretendard, Apple SD Gothic Neo, Noto Sans KR, sans-serif" role="img" '
         f'aria-label="방식별 정상 이용자 거부율과 취소 뒤 평균 사용">',
         f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         f'<text x="{L}" y="26" font-size="17" font-weight="700" fill="{INK}">정상 이용자 거부율 vs 취소 뒤 평균 사용</text>',
         f'<text x="{L}" y="44" font-size="12" fill="{INK2}">PC 모의(D-현실은 Python 모의), 조건 상황 1·2 각 {n1}개. 왼쪽 아래일수록 좋다</text>']
    for v in range(0, int(X_MAX) + 1, 10):
        o.append(f'<line x1="{sx(v)}" y1="{T}" x2="{sx(v)}" y2="{H - B}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text x="{sx(v)}" y="{H - B + 18}" font-size="12" fill="{INK2}" text-anchor="middle">{v}%</text>')
    for v in range(0, int(Y_MAX) + 1):
        o.append(f'<line x1="{L}" y1="{sy(v)}" x2="{W - R}" y2="{sy(v)}" stroke="{GRID}" stroke-width="1"/>')
        o.append(f'<text x="{L - 8}" y="{sy(v) + 4}" font-size="12" fill="{INK2}" text-anchor="end">{v}</text>')
    o.append(f'<text x="{(L + W - R) / 2}" y="{H - 24}" font-size="13" fill="{INK}" text-anchor="middle">② 정상 이용자 거부율 (상황 2, 대여 기간 안 시도)</text>')
    o.append(f'<text transform="translate(22 {(T + H - B) / 2}) rotate(-90)" font-size="13" fill="{INK}" text-anchor="middle">① 취소 뒤 평균 허용 수 (상황 1)</text>')
    x5 = sx(5)
    o.append(f'<line x1="{x5}" y1="{T}" x2="{x5}" y2="{H - B}" stroke="{INK2}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    o.append(f'<text x="{x5 + 5}" y="{H - B - 8}" font-size="12" fill="{INK2}">기준 5% (00 §7)</text>')
    # D-현실을 먼저 그려서 같은 점의 B(원)가 위에 보이게 한다
    for group, color, shape in ((REAL_V, REAL, "diamond"), (CORE_V, CORE, "circle")):
        for v in group:
            x, y = m[v]["rate"], m[v]["mean"]
            cx, cy = sx(x), sy(y)
            tip = f"{v}: 거부율 {x:.1f}%, 취소 뒤 평균 {y:.2f}회 (최대 {m[v]['max']})"
            if shape == "circle":
                mark = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}" stroke="{SURF}" stroke-width="2">'
                o.append(mark + f'<title>{esc(tip)}</title></circle>')
            else:
                pts = f"{cx:.1f},{cy - 7:.1f} {cx + 7:.1f},{cy:.1f} {cx:.1f},{cy + 7:.1f} {cx - 7:.1f},{cy:.1f}"
                o.append(f'<polygon points="{pts}" fill="{color}" stroke="{SURF}" stroke-width="2"><title>{esc(tip)}</title></polygon>')
            name = MERGE.get(v, v)
            if name is None:
                continue
            dx, dy, anchor = NUDGE.get(v, (10, 4, "start"))
            name = name.replace(", M=0", "")
            o.append(f'<text x="{cx + dx:.1f}" y="{cy + dy:.1f}" font-size="12" fill="{INK}" text-anchor="{anchor}">{esc(name)}</text>')
    lx = W - R + 24
    o.append(f'<circle cx="{lx}" cy="{T + 8}" r="6" fill="{CORE}"/>')
    o.append(f'<text x="{lx + 12}" y="{T + 12}" font-size="12" fill="{INK}">A·B·C·D</text>')
    o.append(f'<text x="{lx + 12}" y="{T + 26}" font-size="12" fill="{INK2}">(core.py, PC 모의)</text>')
    o.append(f'<polygon points="{lx},{T + 41} {lx + 7},{T + 48} {lx},{T + 55} {lx - 7},{T + 48}" fill="{REAL}"/>')
    o.append(f'<text x="{lx + 12}" y="{T + 52}" font-size="12" fill="{INK}">D-현실, 유예 M=0</text>')
    o.append(f'<text x="{lx + 12}" y="{T + 66}" font-size="12" fill="{INK2}">(Python 모의)</text>')
    o.append("</svg>")
    path = os.path.join(a.out, "tradeoff.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(o) + "\n")
    print(path)
    for v in CORE_V + REAL_V:
        print(f"  {v}: {m[v]['rate']:.1f}% / {m[v]['mean']:.2f}")


if __name__ == "__main__":
    main()
