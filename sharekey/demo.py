"""중간발표 시연 자동 실행: A 방식과 C 방식을 같은 시나리오로 돌려 비교.
실행: python3 demo.py          (가짜 차량)
      python3 demo.py --relay  (Pi 중계 + STM32 흉내)
      python3 demo.py --relay-c (Pi 중계 + STM32 C 판단 코드 PC 실행판, firmware/stm32/Core 를 build/stm32_pc 로 자동 빌드)
             (server.py, vehicle_sim.py 를 자동으로 띄우고 종료함)"""
import subprocess, sys, time, os, glob
import app
import stm32_pc_build

SYNC = 1.0
SCENARIO_TRIES = 6
RELAY_C = "--relay-c" in sys.argv   # python3 demo.py --relay-c : Pi 중계 + STM32 C 코드(PC 빌드)
RELAY = "--relay" in sys.argv or RELAY_C


def run(mode):
    for f in glob.glob("keys/*.json") + ["server_state.json"]:
        os.remove(f) if os.path.exists(f) else None
    srv = subprocess.Popen([sys.executable, "server.py"])
    time.sleep(0.5)
    if RELAY:      # 앱 → Pi 중계 → STM32 흉내 경로 (--relay-c 면 STM32 C 코드의 PC 빌드)
        if RELAY_C:
            stm = subprocess.Popen([stm32_pc_build.EXE, mode, "9200", str(int(SYNC * 1000))])
        else:
            stm = subprocess.Popen([sys.executable, "stm32_sim.py", "--mode", mode, "--sync", str(SYNC)])
        time.sleep(0.5)
        veh = subprocess.Popen([sys.executable, "pi_relay.py", "--sim", "127.0.0.1:9200"])
        procs = [stm, veh]
    else:          # 가짜 차량 하나
        veh = subprocess.Popen([sys.executable, "vehicle_sim.py", "--mode", mode, "--sync", str(SYNC)])
        procs = [veh]
    time.sleep(0.8)
    rows = []
    try:
        print(f"\n========== 방식 {mode} ==========")
        app.main(["issue", "7", "--limit", "4"])
        app.main(["register", "7"])
        time.sleep(SYNC * 1.5)
        rows.append(("정상 (온라인)", app.main(["open", "7"])))
        print("--- 공격 시험 ---")
        rows.append(("변조", app.main(["tamper", "7"])))
        rows.append(("재전송", app.main(["replay", "7"])))
        time.sleep(SYNC * 1.5)                   # 마지막 동기화로 횟수 4 복구
        print("--- 서버↔차량 차단 후 주인이 취소 ---")
        app.main(["net", "off"]); time.sleep(SYNC * 2.5)
        app.main(["revoke", "7"])
        for i in range(SCENARIO_TRIES):
            rows.append((f"취소 후 {i+1}회", app.main(["open", "7"])))
        print("--- 서버 재연결 → 동기화 ---")
        app.main(["net", "on"]); time.sleep(SYNC * 2.5)
        rows.append(("동기화 후", app.main(["open", "7"])))
    finally:
        for p in procs + [srv]:
            p.terminate(); p.wait()
    return rows


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if RELAY_C:
        stm32_pc_build.build()
    res = {m: run(m) for m in "AC"}
    print("\n================ 결과 비교 ================")
    print(f"{'요청':<12}{'A 방식':<16}{'C 방식(N=4)':<16}")
    for (name, ra), (_, rc) in zip(res["A"], res["C"]):
        f = lambda r: f"{app.RESULT[r[0]]}({r[1]})"
        print(f"{name:<12}{f(ra):<16}{f(rc):<16}")
    for m in "AC":
        extra = sum(1 for n, r in res[m] if n.startswith("취소 후") and r[0] == "A")
        print(f"방식 {m}: 취소 후 추가 사용 {extra}회 / {SCENARIO_TRIES}회 시도")
