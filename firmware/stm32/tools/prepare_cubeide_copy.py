#!/usr/bin/env python3
"""Create a new F429 CubeIDE project copy with v2 source. Never edits the source project.

python prepare_cubeide_copy.py --project C:\\work\\sharekey_f429 \
    --cube-f4-root C:\\Users\\USER\\STM32Cube\\Repository\\STM32Cube_FW_F4_V1.28.3 \
    --output C:\\work\\sharekey_f429_control_v2
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

IGNORED_DIRECTORIES = {"Debug", "Release", "build-host", ".git", ".metadata"}


def strip_c_comments(text):
    """Sufficient for generated linker/C configuration text, not a C parser."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def project_files(source):
    """Walk only files that will be copied; never follow embedded symlinks."""
    result = []
    for folder, directories, filenames in os.walk(source, followlinks=False):
        directories[:] = [n for n in directories if n not in IGNORED_DIRECTORIES]
        for name in list(directories) + filenames:
            path = Path(folder) / name
            if path.is_symlink():
                raise SystemExit("Embedded symlink is not supported: " + str(path))
        result.extend(Path(folder) / name for name in filenames if not name.endswith(".launch"))
    return result


def validate_linker(path):
    text = strip_c_comments(path.read_text(encoding="utf-8-sig"))
    regions = re.findall(r"\bMEMORY\s*\{(.*?)\}", text, re.S)
    if len(regions) != 1:
        raise SystemExit("Unsupported linker MEMORY layout; review manually: " + path.name)
    ram = re.findall(
        r"\bRAM\s*(?:\([^)]*\))?\s*:\s*ORIGIN\s*=\s*"
        r"(0[xX][0-9a-fA-F]+|[0-9]+)\s*,\s*LENGTH\s*=\s*"
        r"(0[xX][0-9a-fA-F]+|[0-9]+)\s*([kKmM]?)\b", regions[0])
    if len(ram) != 1:
        raise SystemExit("Expected standard F429 RAM region; custom split SRAM needs manual review: " + path.name)
    origin, size, unit = ram[0]
    length = int(size, 0) * {"": 1, "K": 1024, "M": 1024 * 1024}[unit.upper()]
    if int(origin, 0) != 0x20000000 or length != 192 * 1024:
        raise SystemExit("Wrong F429 linker RAM: require ORIGIN 0x20000000, LENGTH 192K: " + path.name)
    stacks = re.findall(r"\b_estack\s*=\s*([^;]+);", text)
    if len(stacks) != 1:
        raise SystemExit("Expected one standard F429 _estack assignment: " + path.name)
    stack = re.sub(r"\s+", "", stacks[0]).upper()
    if stack not in {"0X20030000", "ORIGIN(RAM)+LENGTH(RAM)"}:
        # Also accept the exact decimal address, but not arbitrary expressions.
        if not re.fullmatch(r"[0-9]+", stack) or int(stack, 10) != 0x20030000:
            raise SystemExit("Wrong/unsupported F429 _estack; require 0x20030000 or ORIGIN(RAM)+LENGTH(RAM): " + path.name)


def validate_target(source, project_tree, cproject_tree):
    if project_tree.getroot().find("name") is None:
        raise SystemExit("Malformed .project: missing project name")
    if project_tree.getroot().find("linkedResources") is not None:
        if list(project_tree.getroot().find("linkedResources")):
            raise SystemExit("Linked project resources are not supported. Copy resources into the project before using this tool.")
    metadata = ET.tostring(cproject_tree.getroot(), encoding="unicode")
    if not re.search(r"\bSTM32F429(?:ZI[A-Za-z0-9]*|xx)\b", metadata, re.I):
        raise SystemExit("The .cproject must identify STM32F429ZI/STM32F429xx, not only the .ioc.")
    if re.search(r"STM32F7|F767|cortex[-_]m7|fpv5", metadata, re.I):
        raise SystemExit("F7/M7 build settings remain in .cproject. Recreate a real F429 project.")
    for element in cproject_tree.iter():
        for value in element.attrib.values():
            # A literal workspace project path could make the copied builder write
            # into the original project. Only the dynamic current-project form is safe.
            remaining = re.sub(
                r"\$\{workspace_loc:/\$\{ProjName\}(?:/([^}]*))?\}",
                lambda match: "PROJECT_ROOT" + ("/" + match.group(1) if match.group(1) else ""), value)
            if "${workspace_loc:" in remaining:
                raise SystemExit("Literal/external workspace path in .cproject needs manual conversion to ${ProjName}.")
            if element.tag in {"sourceEntry", "entry"} and element.get("kind") in {"sourcePath", "includePath", "libraryPath"}:
                if re.match(r"(?:[A-Za-z]:[\\/]|/)", value):
                    raise SystemExit("External absolute source/include path is not supported in a copied project.")
            # A valid local script does not prove the build uses it. Reject a
            # linker option that points outside the copied project as well.
            candidate = remaining.strip().strip('"')
            if candidate.lower().endswith(".ld"):
                candidate = candidate.replace("\\", "/")
                for prefix in ["PROJECT_ROOT/", "${ProjDirPath}/", "${project_loc}/"]:
                    if candidate.startswith(prefix):
                        candidate = candidate[len(prefix):]
                        break
                else:
                    # Cube builds run in Debug/Release, one level below the project.
                    if candidate.startswith("../"):
                        candidate = candidate[3:]
                if (re.match(r"(?:[A-Za-z]:/|/)", candidate) or "$" in candidate
                        or ".." in Path(candidate).parts or not (source / candidate).is_file()):
                    raise SystemExit("External/unresolved linker path is not supported: " + value)
    files = project_files(source)
    startups = [p for p in files if p.name.lower().startswith("startup_") and p.suffix.lower() in {".s", ".asm"}]
    if len(startups) != 1 or not re.fullmatch(r"startup_stm32f429(?:xx|zi[a-z0-9]*)\.s", startups[0].name, re.I):
        raise SystemExit("Expected exactly one F429 startup assembly file; remove stale F7/other MCU startups first.")
    linkers = [p for p in files if p.suffix.lower() == ".ld"]
    if not linkers:
        raise SystemExit("No local F429 linker script found. Linked/external linker scripts need manual review.")
    for path in linkers:
        validate_linker(path)


def prepare_main_text(text):
    begin, end = "/* USER CODE BEGIN 2 */", "/* USER CODE END 2 */"
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        raise SystemExit("main.c needs one ordered USER CODE BEGIN/END 2 section.")
    before = strip_c_comments(text[:text.index(begin)])
    for init in ["MX_USART3_UART_Init", "MX_RNG_Init"]:
        if not re.search(r"\b" + init + r"\s*\(\s*\)\s*;", before):
            raise SystemExit(init + "() must be called before USER CODE BEGIN 2.")
    whole = strip_c_comments(text)
    block = text[text.index(begin) + len(begin):text.index(end)]
    call = r"\bsk_app_run\s*\(\s*\)\s*;"
    total_calls = len(re.findall(call, whole))
    block_calls = len(re.findall(call, strip_c_comments(block)))
    if total_calls > 1 or total_calls != block_calls:
        raise SystemExit("sk_app_run must occur once inside USER CODE 2, or be absent. Review custom main hooks manually.")
    if total_calls == 0:
        # Existing custom initialization in USER CODE 2 runs before the nonreturning loop.
        text = text.replace(end, "  extern void sk_app_run(void);\n  sk_app_run();\n  " + end, 1)
    return text


def prepare_hal_conf(text):
    for module in ["TIM", "I2C", "IWDG"]:
        define = "#define HAL_" + module + "_MODULE_ENABLED"
        if not re.search(r"^\s*#define\s+HAL_" + module + r"_MODULE_ENABLED\b", text, re.M):
            commented = r"/\*\s*#define\s+HAL_" + module + r"_MODULE_ENABLED\s*\*/"
            if re.search(commented, text):
                text = re.sub(commented, define, text)
            else:
                raise SystemExit("Cannot safely enable HAL " + module + " in generated config")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--cube-f4-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    source, dest, cube = args.project.resolve(), args.output.resolve(), args.cube_f4_root.resolve()
    package = Path(__file__).resolve().parents[1]
    if dest.exists(): raise SystemExit("Output exists. Choose a new directory; this tool never overwrites a project.")
    if source == dest or source in dest.parents or dest in source.parents:
        raise SystemExit("Input/output projects must be separate directories, neither nested inside the other.")
    required = [source/".project", source/".cproject", source/"Core/Src/main.c", source/"Core/Inc/stm32f4xx_hal_conf.h"]
    if not all(p.is_file() for p in required):
        raise SystemExit("Expected a generated F4 CubeIDE project with Core/Src and Core/Inc.")
    iocs = list(source.glob("*.ioc"))
    if len(iocs) != 1: raise SystemExit("Expected exactly one .ioc file in the source project.")
    ioc = iocs[0].read_text(encoding="utf-8-sig")
    if not re.search(r"^Mcu\.(?:Name|CPN|UserName)=STM32F429ZI", ioc, re.M):
        raise SystemExit("The .ioc MCU is not STM32F429ZI. Do not use an F767 project.")
    try:
        project_tree = ET.parse(source/".project")
        cproject_tree = ET.parse(source/".cproject")
    except ET.ParseError as exc:
        raise SystemExit("Malformed CubeIDE project XML: " + str(exc)) from exc
    validate_target(source, project_tree, cproject_tree)
    main_text = prepare_main_text(required[2].read_text(encoding="utf-8-sig"))
    conf_text = prepare_hal_conf(required[3].read_text(encoding="utf-8-sig"))
    hal = cube/"Drivers/STM32F4xx_HAL_Driver"
    driver_names = ["tim", "tim_ex", "i2c", "i2c_ex", "iwdg"]
    if not all((hal/"Src"/("stm32f4xx_hal_"+n+".c")).is_file() for n in driver_names):
        raise SystemExit("STM32CubeF4 root lacks required HAL sources.")
    if not (hal/"Inc/stm32f4xx_hal_tim.h").is_file():
        raise SystemExit("STM32CubeF4 TIM headers missing.")
    def ignore(folder, names):
        return {n for n in names if n in IGNORED_DIRECTORIES or n.endswith(".launch")}
    created_destination = False
    try:
        # Atomic ownership: never clean up a directory created by someone else
        # between the earlier exists() check and the copy operation.
        dest.mkdir(parents=True, exist_ok=False)
        created_destination = True
        shutil.copytree(source, dest, ignore=ignore, dirs_exist_ok=True)
        # Metadata keeps the original build configuration, with a distinct import name.
        tree = ET.parse(dest/".project")
        project_name = tree.getroot().find("name")
        if project_name is None: raise RuntimeError("Malformed .project: missing name")
        project_name.text = dest.name
        tree.write(dest/".project", encoding="utf-8", xml_declaration=True)
        for sub in ["Inc", "Src"]:
            for item in (package/"Core"/sub).iterdir():
                if item.is_file(): shutil.copy2(item, dest/"Core"/sub/item.name)
        # Never include PC test mains in target Core/Src.
        for name in ["main_pc.c", "test_vectors.c"]:
            p = dest/"Core/Src"/name
            if p.exists(): p.unlink()
        main_path = dest/"Core/Src/main.c"
        main_path.write_text(main_text, encoding="utf-8")
        conf = dest/"Core/Inc/stm32f4xx_hal_conf.h"
        conf.write_text(conf_text, encoding="utf-8")
        target_hal = dest/"Drivers/STM32F4xx_HAL_Driver"
        for name in driver_names:
            source_driver = hal/"Src"/("stm32f4xx_hal_"+name+".c")
            (target_hal/"Src").mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_driver, target_hal/"Src"/source_driver.name)
        # Existing projects may copy only selected HAL headers. Complete the header set.
        shutil.copytree(hal/"Inc", target_hal/"Inc", dirs_exist_ok=True)
        (dest/"V2_IMPORT_NOTES.txt").write_text(
            "F429 v2 source copied. Original project was not modified.\n"
            "Import this directory as an existing CubeIDE project; Clean and Build.\n"
            "Keep F429 startup/linker, USART3 IRQ and RNG/clock generation.\n"
            "Only Core/Src/port_stm32.c owns UART callbacks.\n"
            "Review duplicate callbacks or custom existing code before flashing.\n"
            "Default: A/C mode C, servo on, motors/RTC/OLED/endpoints off.\n"
            "CubeMX regeneration can change HAL driver selection: recheck after generation.\n",
            encoding="utf-8")
    except Exception:
        # This destination was created by this invocation; preserve input and remove incomplete copy.
        if created_destination and dest.exists(): shutil.rmtree(dest)
        raise
    print("Prepared:", dest)
    print("Next: CubeIDE File > Import > Existing Projects into Workspace; select this directory.")
    print("Clean/Build and inspect the Run configuration's F429 ELF before downloading.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
