"""STM32 판단 코드 PC 실행판 빌드 (demo.py --relay-c 가 자동으로 부름).
firmware/stm32/Core 의 판단 코드를 그대로 쓰고, 결과는 build/stm32_pc (저장소에 올리지 않음).
    python3 stm32_pc_build.py [--cc cc]"""
import argparse
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(os.path.dirname(HERE), "firmware", "stm32", "Core")
EXE = os.path.join(HERE, "build", "stm32_pc")


def build(cc=None):
    os.makedirs(os.path.dirname(EXE), exist_ok=True)
    cmd = [cc or os.environ.get("CC", "cc"), "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
           "-I", os.path.join(CORE, "Inc"), os.path.join(HERE, "stm32_pc.c"),
           *[os.path.join(CORE, "Src", s) for s in ("sharekey.c", "sk_crypto.c", "sk_store.c")], "-o", EXE]
    subprocess.run(cmd, check=True)
    return EXE


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc")
    print(build(ap.parse_args().cc))
