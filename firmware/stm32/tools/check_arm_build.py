#!/usr/bin/env python3
"""Compile and link this source package against a local STM32CubeF4 release.

This is a reproducible standalone ARM build check, not a CubeIDE import and not
a flash/upload command. No network access or system installation is performed.
The user's existing CubeIDE main/startup/linker remain the integration base.

Example:
  python tools/check_arm_build.py --cube-root /path/STM32Cube_FW_F4_V1.28.3 \
      --gcc /path/bin/arm-none-eabi-gcc --variant default
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cube-root", required=True, type=Path)
    parser.add_argument("--gcc", default="arm-none-eabi-gcc")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--variant", choices=["default", "all-features", "policy-a", "servo", "demo"], default="default")
    args = parser.parse_args()

    compiler = shutil.which(args.gcc)
    if compiler is None:
        parser.error("ARM compiler not found; supply --gcc with its absolute path")
    compiler = Path(compiler).resolve()
    suffix = ".exe" if compiler.name.endswith(".exe") else ""
    tool_prefix = compiler.name.removesuffix(suffix).removesuffix("gcc")
    objcopy = compiler.with_name(tool_prefix + "objcopy" + suffix)
    size = compiler.with_name(tool_prefix + "size" + suffix)
    readelf = compiler.with_name(tool_prefix + "readelf" + suffix)

    cube = args.cube_root.resolve()
    hal = cube / "Drivers/STM32F4xx_HAL_Driver"
    cmsis = cube / "Drivers/CMSIS"
    device = cmsis / "Device/ST/STM32F4xx"
    core_include = cmsis / "Include"
    if not (core_include / "core_cm4.h").is_file():
        core_include = cmsis / "Core/Include"
    startup = device / "Source/Templates/gcc/startup_stm32f429xx.s"
    system = device / "Source/Templates/system_stm32f4xx.c"
    required = [hal / "Inc/stm32f4xx_hal.h", device / "Include/stm32f429xx.h",
                core_include / "core_cm4.h", startup, system, objcopy, size, readelf]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        parser.error("Missing toolchain/CubeF4 dependency:\n" + "\n".join(missing))

    out = (args.out or ROOT / "build-arm" / args.variant).resolve()
    out.mkdir(parents=True, exist_ok=True)
    objects = out / "objects"
    objects.mkdir(exist_ok=True)
    log_lines: list[str] = []
    commands: list[list[str]] = []

    def run(command: list[str]) -> str:
        commands.append(command)
        result = subprocess.run(command, capture_output=True, text=True)
        text = result.stdout + result.stderr
        log_lines.append("COMMAND " + repr(command) + "\n" + text)
        if text:
            print(text, end="" if text.endswith("\n") else "\n")
        if result.returncode:
            (out / "build.log").write_text("\n".join(log_lines), encoding="utf-8")
            (out / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
            raise subprocess.CalledProcessError(result.returncode, command)
        return text

    compiler_version = run([str(compiler), "--version"]).splitlines()[0]
    cpu = ["-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"]
    defines = ["-DSTM32F429xx", "-DUSE_HAL_DRIVER", "-DHSE_VALUE=8000000U"]
    if args.variant == "all-features":
        defines += ["-DCONTROL_USE_ENDPOINTS=1", "-DVC_ENABLE_MOTORS=1", "-DVC_ENABLE_RTC=1",
                    "-DVC_ENABLE_OLED=1", "-DVC_ENABLE_RETURN_BUTTON=1", "-DVC_ENABLE_IWDG=1", "-DTEST_BUILD=1"]
    elif args.variant == "policy-a":
        defines += ["-DAPP_POLICY_MODE='A'"]
    elif args.variant == "servo":
        defines += ["-DVC_BUILD_SERVO_TEST=1"]
    elif args.variant == "demo":   # 1103: presentation build (mode select ON)
        defines += ["-DVC_DEMO_MODE_SELECT=1"]

    include_dirs = [ROOT / "Core/Inc", ROOT / "vendor/sharekey", ROOT / "build_support",
                    hal / "Inc", hal / "Inc/Legacy", device / "Include", core_include]
    if args.variant == "servo":
        include_dirs += [ROOT / "examples/servo_test_f429"]
        application_sources = sorted((ROOT / "examples/servo_test_f429").glob("*.c"))
        application_sources += [ROOT / "Core/Src/pwm_clock.c"]
        if not application_sources[0].is_file():
            parser.error("Servo source not found")
    else:
        application_sources = sorted((ROOT / "Core/Src").glob("*.c"))
        # The distribution keeps the unchanged policy sources in Core/Src for
        # direct CubeIDE copying. A vendor layout is also accepted by the check.
        for name in ["sharekey.c", "sk_crypto.c"]:
            if not (ROOT / "Core/Src" / name).is_file():
                application_sources.append(ROOT / "vendor/sharekey" / name)
    application_sources += [ROOT / "build_support/main_f429.c", ROOT / "build_support/syscalls.c"]
    for path in application_sources:
        if not path.is_file():
            parser.error("Application source not found: " + str(path))

    hal_modules = ["hal", "hal_cortex", "hal_dma", "hal_dma_ex", "hal_flash", "hal_flash_ex",
                   "hal_gpio", "hal_i2c", "hal_i2c_ex", "hal_iwdg", "hal_pwr", "hal_pwr_ex",
                   "hal_rcc", "hal_rcc_ex", "hal_rng", "hal_tim", "hal_tim_ex", "hal_uart"]
    vendor_sources = [hal / "Src" / ("stm32f4xx_" + name + ".c") for name in hal_modules]
    vendor_sources += [system, startup]
    common = cpu + defines + ["-Os", "-g3", "-ffunction-sections", "-fdata-sections", "-fstack-usage"]
    for path in include_dirs:
        common += ["-I", str(path)]

    compiled_objects: list[str] = []
    source_manifest: list[dict[str, str]] = []
    try:
        for index, source in enumerate(application_sources + vendor_sources):
            object_path = objects / (f"{index:03d}_" + source.stem + ".o")
            language = ["-x", "assembler-with-cpp"] if source.suffix == ".s" else ["-std=c11", "-Wall", "-Wextra"]
            # Strict warnings for our application. Vendor packages are compiled as delivered.
            if source in application_sources and source.suffix == ".c":
                language += ["-Werror"]
            run([str(compiler), *common, *language, "-c", str(source), "-o", str(object_path)])
            compiled_objects.append(str(object_path))
            source_manifest.append({"path": str(source), "sha256": digest(source)})

        elf = out / "f429_build_check.elf"
        run([str(compiler), *cpu, *compiled_objects, "-T", str(ROOT / "build_support/stm32f429zi.ld"),
             "--specs=nano.specs", "--specs=nosys.specs", "-Wl,--gc-sections", "-Wl,--print-memory-usage",
             "-Wl,-Map=" + str(out / "f429_build_check.map"), "-o", str(elf)])
        run([str(objcopy), "-O", "ihex", str(elf), str(out / "f429_build_check.hex")])
        run([str(objcopy), "-O", "binary", str(elf), str(out / "f429_build_check.bin")])
        initial_stack = int.from_bytes((out / "f429_build_check.bin").read_bytes()[:4], "little")
        if initial_stack != 0x20030000:
            raise RuntimeError(f"Unexpected F429 initial stack vector: 0x{initial_stack:08X}")
        size_result = run([str(size), str(elf)])
        attributes = run([str(readelf), "-A", str(elf)])
        headers = run([str(readelf), "-h", str(elf)])
        (out / "source_manifest.json").write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")
        (out / "result.json").write_text(json.dumps({
            "status": "PASS", "scope": "Standalone ARM compile and link; no hardware execution or CubeIDE project validation",
            "variant": args.variant, "compiler": compiler_version, "cube_root": str(cube),
            "initial_stack_pointer": f"0x{initial_stack:08X}",
            "application_source_count": len(application_sources), "vendor_source_count": len(vendor_sources),
            "elf_sha256": digest(elf), "size": size_result, "attributes": attributes, "elf_header": headers,
        }, indent=2), encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        print("ARM build failed; see " + str(out / "build.log"), file=sys.stderr)
        return exc.returncode
    finally:
        (out / "build.log").write_text("\n".join(log_lines), encoding="utf-8")
        (out / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
    print("PASS: " + args.variant + " ARM compile/link. No flash/upload was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
