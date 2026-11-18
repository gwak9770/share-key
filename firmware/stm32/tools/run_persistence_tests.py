"""Build the production C policy as a host bridge and run Python/C recovery tests."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc", default="gcc")
    ap.add_argument("--build-dir", type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = (args.build_dir or root / "build-host/persistence").resolve()
    out.mkdir(parents=True, exist_ok=True)
    cc = shutil.which(args.cc)
    if not cc:
        ap.error("C compiler not found")
    sources = [root / p for p in ("Core/Src/sharekey.c", "Core/Src/sk_crypto.c",
                                  "Core/Src/sk_store.c", "tests/test_persistence.c")]
    dll = out / ("policy_bridge.dll" if os.name == "nt" else "policy_bridge.so")
    if Path(cc).name.lower() in ("cl", "cl.exe"):
        cmd = [cc, "/nologo", "/LD", "/std:c11", "/utf-8", "/W4", "/D_CRT_SECURE_NO_WARNINGS",
               "/DSK_BRIDGE_LIBRARY", "/I" + str(root / "Core/Inc"),
               *map(str, sources), "/link", "/OUT:" + str(dll)]
    else:
        cmd = [cc, "-shared", "-fPIC", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
               "-DSK_BRIDGE_LIBRARY", "-I", str(root / "Core/Inc"), *map(str, sources), "-o", str(dll)]
    comp = subprocess.run(cmd, cwd=out, capture_output=True, text=True, errors="replace")
    (out / "build.log").write_text(comp.stdout + comp.stderr, encoding="utf-8")
    if comp.returncode:
        print(comp.stdout + comp.stderr)
        return comp.returncode
    env = dict(os.environ, SHAREKEY_TEST_BRIDGE=str(dll), PYTHONUTF8="1")
    test = root.parents[1] / "sharekey/tests/test_recovery.py"
    result = subprocess.run([sys.executable, "-X", "utf8", str(test)], env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    (out / "tests.log").write_text(output, encoding="utf-8")
    print(output)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
