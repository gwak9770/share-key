"""Pi 5 전원 레일 전력 기록 (00 §10 T08 전력, docs/test-records/T08_전력측정_절차.md).

Pi 5의 전원 관리 칩(PMIC)이 재는 레일별 전압·전류를 `vcgencmd pmic_read_adc`로 읽어
1초마다 합계 전력(W)을 출력한다. Pi 5에서만 동작한다. 측정기가 아니라 PMIC 값이므로
"Pi 자체 측정"으로 표기한다. 로그 파일은 저장소에 올리지 않는다(AGENTS §8).

    python3 pi_power_log.py --label idle --seconds 60
    python3 pi_power_log.py --label relay --seconds 60     (pi_relay.py 실행 중)

마지막 줄에 평균·최소·최대(W)를 출력한다. 표에 옮길 때는 이 줄만 쓴다.
"""
import argparse
import re
import statistics
import subprocess
import time

LINE = re.compile(r"^\s*(\S+)_([AV])\s+\S+\([0-9]+\)=([0-9.]+)[AV]\s*$")


def read_power():
    out = subprocess.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True, check=True).stdout
    amps, volts = {}, {}
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            (amps if m.group(2) == "A" else volts)[m.group(1)] = float(m.group(3))
    rails = sorted(set(amps) & set(volts))
    if not rails:
        raise SystemExit("pmic_read_adc 출력에서 레일을 찾지 못함 (Pi 5인지, vcgencmd가 최신인지 확인)")
    return sum(amps[r] * volts[r] for r in rails), len(rails)


def main():
    ap = argparse.ArgumentParser(description="Pi 5 PMIC 전력 기록")
    ap.add_argument("--label", required=True, help="상태 이름 (예: idle, relay)")
    ap.add_argument("--seconds", type=int, default=60)
    a = ap.parse_args()
    vals = []
    for i in range(a.seconds):
        w, n = read_power()
        vals.append(w)
        print(f"{a.label},{i},{w:.3f}", flush=True)
        time.sleep(1)
    print(f"# {a.label}: 평균 {statistics.mean(vals):.3f} W, 최소 {min(vals):.3f}, 최대 {max(vals):.3f}, "
          f"{len(vals)}초, 레일 {n}개 (Pi 자체 측정, 레일 합계. 5V 입력 손실은 빠짐)")


if __name__ == "__main__":
    main()
