"""비교 실험 조건 표 생성 (docs/02_final_roadmap.md §5.3, 00 §10 T06).

실험 전에 한 번 만들어 커밋하고, 결과를 본 뒤에는 조건을 바꾸지 않는다.
같은 시드면 항상 같은 표가 나온다(표준 라이브러리 random, 시드 20261116).

    python3 sharekey/experiments/make_conditions.py --out docs/results/conditions.csv

상황마다 무작위 24개 + 경계 6개 = 30개, 상황 4종 = 120줄.
같은 120줄을 모든 방식(A·B·C·D·D-현실)에 똑같이 넣는다.

열 (시간은 모두 대여 시작 = 0분 기준, 단위 분)
  situation      1 취소 뒤 재사용 / 2 정상 이용자 / 3 계속 운행 / 4 재부팅
  cond_id        S{상황}-R01~R24 (무작위), S{상황}-B1~B6 (경계)
  kind           random 또는 경계 이름
  rental_min     대여 기간. 30분 ~ 72시간 로그 균등, 30분 단위로 반올림
  offline_start  오프라인 시작. 0 ~ 대여 끝 균등
  offline_len    오프라인 길이. 10분 ~ 14일 로그 균등
  revoke_at      취소 시각 = 오프라인 시작 + (0 ~ 오프라인 길이의 50% 균등).
                 상황 2는 취소가 없으므로 빈칸
  first_try      첫 시도 시각. 상황 2는 오프라인 시작, 나머지는 취소 시각
                 (상황 3은 이 시각에 시동 1회)
  opens          시도 횟수. 1 ~ 20 균등 정수. 경계 B3·B4는 방식의 N에 따라
                 정해지므로 "N", "N+1"로 적는다(N이 없는 방식은 compare.py가 정함)
  interval       시도 간격. 5 ~ 120분 균등
  reboots        상황 4의 재부팅·재등록 반복 수 r. 1 ~ 5 균등 정수. 나머지 빈칸

경계 6개 (값은 아래 BOUNDARY에 고정)
  B1 대여 끝 1분 전 시도, B2 대여 끝 1분 뒤 시도,
  B3 정확히 N번째 시도, B4 N+1번째 시도,
  B5 오프라인 직후 바로 취소(상황 2는 취소가 없어 오프라인 직후 바로 시도),
  B6 오프라인 14일
"""
import argparse
import csv
import math
import random

SEED = 20261116
N_RANDOM = 24
FIELDS = ["situation", "cond_id", "kind", "rental_min", "offline_start", "offline_len",
          "revoke_at", "first_try", "opens", "interval", "reboots"]


def log_uniform(rng, lo, hi):
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


def r1(x):
    return round(x, 1)


def random_row(rng, sit, i):
    # 뽑는 순서를 바꾸면 표 전체가 바뀌므로 순서를 고정한다.
    rental = min(4320, max(30, round(log_uniform(rng, 30, 4320) / 30) * 30))
    off_start = r1(rng.uniform(0, rental))
    off_len = r1(log_uniform(rng, 10, 14 * 24 * 60))
    revoke = r1(off_start + rng.uniform(0, 0.5 * off_len))
    opens = rng.randint(1, 20)
    interval = r1(rng.uniform(5, 120))
    reboots = rng.randint(1, 5) if sit == 4 else ""
    return {
        "situation": sit, "cond_id": f"S{sit}-R{i:02d}", "kind": "random",
        "rental_min": rental, "offline_start": off_start, "offline_len": off_len,
        "revoke_at": "" if sit == 2 else revoke,
        "first_try": off_start if sit == 2 else revoke,
        "opens": opens, "interval": interval, "reboots": reboots,
    }


# 경계 조건: (이름, 대여, 오프라인 시작, 오프라인 길이, 취소 시각, 첫 시도, 시도 수, 간격)
BOUNDARY = [
    ("B1_rental_end_minus_1", 180, 60, 600, 60, 179, 1, 5),
    ("B2_rental_end_plus_1", 180, 60, 600, 60, 181, 1, 5),
    ("B3_exactly_N", 1440, 60, 1440, 60, 60, "N", 5),
    ("B4_N_plus_1", 1440, 60, 1440, 60, 60, "N+1", 5),
    ("B5_revoke_at_offline_start", 360, 30, 600, 30, 30, 5, 30),
    ("B6_offline_14_days", 4320, 60, 20160, 120, 120, 20, 120),
]


def boundary_rows(sit):
    rows = []
    for k, (name, rental, start, length, revoke, first, opens, interval) in enumerate(BOUNDARY, 1):
        if sit == 2:
            revoke = ""
            if name.startswith("B5"):
                name, first = "B5_try_at_offline_start", start
        rows.append({
            "situation": sit, "cond_id": f"S{sit}-B{k}", "kind": name,
            "rental_min": rental, "offline_start": start, "offline_len": length,
            "revoke_at": revoke, "first_try": first, "opens": opens,
            "interval": interval, "reboots": 3 if sit == 4 else "",
        })
    return rows


def make_rows(seed=SEED):
    rng = random.Random(seed)
    rows = []
    for sit in (1, 2, 3, 4):
        rows += [random_row(rng, sit, i) for i in range(1, N_RANDOM + 1)]
        rows += boundary_rows(sit)
    return rows


def main():
    ap = argparse.ArgumentParser(description="비교 실험 조건 표 생성 (02 §5.3)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default="docs/results/conditions.csv")
    a = ap.parse_args()
    rows = make_rows(a.seed)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{a.out}: {len(rows)}줄 (seed {a.seed})")


if __name__ == "__main__":
    main()
