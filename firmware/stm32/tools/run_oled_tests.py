#!/usr/bin/env python3
"""Run portable C tests with GCC/Clang or MSVC (no target board required).

For MSVC run from an x64 Native Tools prompt: python tools/run_host_tests.py --cc cl
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    ap.add_argument("--build-dir", type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    build = (args.build_dir or root / "build-host").resolve()
    build.mkdir(parents=True, exist_ok=True)
    cc = shutil.which(args.cc)
    if not cc:
        raise SystemExit("C compiler not found. Use GCC/Clang, or --cc cl in an MSVC developer prompt.")
    msvc = Path(cc).name.lower() in {"cl", "cl.exe"}
    common = ["Core/Src/control.c", "Core/Src/line_reader.c", "Core/Src/vehicle_app.c",
              "Core/Src/sharekey.c", "Core/Src/sk_crypto.c"]
    oled = ["Core/Src/control.c", "Core/Src/oled.c", "tests/test_oled.c"]
    cases = [
        ("control_no_endpoints", ["-DCONTROL_USE_ENDPOINTS=0"], ["Core/Src/control.c", "tests/test_control.c"]),
        ("control_endpoints", ["-DCONTROL_USE_ENDPOINTS=1"], ["Core/Src/control.c", "tests/test_control.c"]),
        ("pwm_clock", [], ["Core/Src/pwm_clock.c", "tests/test_pwm_clock.c"]),
        ("line_reader", [], ["Core/Src/line_reader.c", "tests/test_line_reader.c"]),
        ("auth_vectors", [], ["Core/Src/sharekey.c", "Core/Src/sk_crypto.c", "tests/test_vectors.c"]),
        ("app_c", ["-DAPP_POLICY_MODE='C'"], common + ["tests/test_app.c"]),
        ("app_a", ["-DAPP_POLICY_MODE='A'"], common + ["tests/test_app.c"]),
        ("app_c_motor", ["-DAPP_POLICY_MODE='C'", "-DVC_ENABLE_MOTORS=1"], common + ["tests/test_app.c"]),
        ("app_c_endpoints", ["-DAPP_POLICY_MODE='C'", "-DCONTROL_USE_ENDPOINTS=1"], common + ["tests/test_app.c"]),
        ("app_a_endpoints", ["-DAPP_POLICY_MODE='A'", "-DCONTROL_USE_ENDPOINTS=1"], common + ["tests/test_app.c"]),
        ("app_c_relock_off", ["-DAPP_POLICY_MODE='C'", "-DVC_RELOCK_ON_DOOR_CLOSE=0"], common + ["tests/test_app.c"]),
        ("app_c_modeselect", ["-DAPP_POLICY_MODE='C'", "-DVC_DEMO_MODE_SELECT=1"], common + ["tests/test_app.c"]),
        ("app_a_modeselect", ["-DAPP_POLICY_MODE='A'", "-DVC_DEMO_MODE_SELECT=1"], common + ["tests/test_app.c"]),
        ("app_a_relock_off", ["-DAPP_POLICY_MODE='A'", "-DVC_RELOCK_ON_DOOR_CLOSE=0"], common + ["tests/test_app.c"]),
        ("oled_large_c", ["-DSTM32F429xx", "-DAPP_POLICY_MODE='C'"], oled),
        ("oled_large_a", ["-DSTM32F429xx", "-DAPP_POLICY_MODE='A'"], oled),
        ("oled_large_endpoints", ["-DSTM32F429xx", "-DCONTROL_USE_ENDPOINTS=1"], oled),
        ("oled_legacy", ["-DSTM32F429xx", "-DVC_OLED_LARGE_TEXT=0"], oled),
        ("oled_off", ["-DVC_ENABLE_OLED=0"], oled),
    ]
    cases = [c for c in cases if c[0].startswith("oled_")]
    summary = []
    failed = False
    for name, definitions, sources in cases:
        executable = build / (name + (".exe" if os.name == "nt" else ""))
        command = [cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(root/"Core/Inc"),
                   "-I", str(root/"tests/oled_stubs"),
                   *definitions, *[str(root/s) for s in sources], "-o", str(executable)]
        if msvc:
            # Keep MSVC warnings visible, including conversions in the unchanged
            # shared authentication code; do not edit that code for a host toolchain.
            command = [cc, "/nologo", "/std:c11", "/utf-8", "/W4",
                       "/D_CRT_SECURE_NO_WARNINGS", "/I" + str(root/"Core/Inc"),
                       "/I" + str(root/"tests/oled_stubs"),
                       *["/D" + d[2:] for d in definitions],
                       *[str(root/s) for s in sources], "/Fe" + str(executable)]
        comp = subprocess.run(command, cwd=build, text=True, capture_output=True, errors="replace")
        item = {"name": name, "compile": comp.returncode, "command": command,
                "build_output": comp.stdout + comp.stderr}
        if comp.returncode == 0:
            run = subprocess.run([str(executable)], cwd=build, text=True, capture_output=True, timeout=20)
            item.update(run=run.returncode, output=run.stdout+run.stderr)
        else:
            item.update(run=None, output="")
        ok = item["compile"] == 0 and item["run"] == 0
        failed |= not ok
        print(("PASS " if ok else "FAIL ") + name)
        if not ok: print(item["build_output"] + item["output"])
        (build/(name+".log")).write_text(item["build_output"]+item["output"], encoding="utf-8")
        summary.append(item)
    (build/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
