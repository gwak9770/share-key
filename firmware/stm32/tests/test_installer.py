#!/usr/bin/env python3
"""CLI fixture checks for the copy-only CubeIDE importer (no ARM toolchain needed)."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


PACKAGE = Path(__file__).resolve().parents[1]
INSTALLER = PACKAGE / "tools" / "prepare_cubeide_copy.py"
LINKER = "STM32F429ZITX_FLASH.ld"
MAIN = """void MX_USART3_UART_Init(void);
void MX_RNG_Init(void);
int main(void) {
  MX_USART3_UART_Init();
  MX_RNG_Init();
  /* USER CODE BEGIN 2 */
  existing_user_init();
  /* USER CODE END 2 */
  for (;;) {}
}
"""


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="f429-import-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "sharekey_f429"
        self.dest = self.root / "imported_f429"
        self.cube = self.root / "cube_f4"
        self.write(".project", "<projectDescription><name>sharekey_f429</name></projectDescription>")
        # CubeIDE may derive cortex-m4 from this MCU token: no explicit CPU is required.
        self.write(".cproject", '<cproject><option value="STM32F429ZITx"/>'
                   '<option value="${workspace_loc:/${ProjName}/' + LINKER + '}"/>'
                   '<builder buildPath="${workspace_loc:/${ProjName}}/Debug"/></cproject>')
        self.write("sharekey_f429.ioc", "Mcu.Name=STM32F429ZITx\nMcu.CPN=STM32F429ZIT6\n")
        self.write("Core/Startup/startup_stm32f429zitx.s", ".syntax unified\n")
        self.write(LINKER, """_estack = ORIGIN(RAM) + LENGTH(RAM);
MEMORY {
  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 192K
  CCMRAM (rw) : ORIGIN = 0x10000000, LENGTH = 64K
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 2048K
}
""")
        self.write("Core/Src/main.c", MAIN)
        self.write("Core/Inc/stm32f4xx_hal_conf.h", "\n".join(
            "/* #define HAL_" + module + "_MODULE_ENABLED */" for module in ("TIM", "I2C", "IWDG")) + "\n")
        hal = self.cube / "Drivers/STM32F4xx_HAL_Driver"
        (hal / "Src").mkdir(parents=True)
        (hal / "Inc").mkdir()
        for module in ("tim", "tim_ex", "i2c", "i2c_ex", "iwdg"):
            (hal / "Src" / ("stm32f4xx_hal_" + module + ".c")).write_text("/* Fixture source. */\n")
        (hal / "Inc/stm32f4xx_hal_tim.h").write_text("/* Fixture header. */\n")

    def write(self, relative, text):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def edit(self, relative, old, new):
        path = self.source / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def snapshot(self):
        return {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.source.rglob("*") if p.is_file()}

    def run_installer(self):
        return subprocess.run([sys.executable, str(INSTALLER), "--project", str(self.source),
                               "--cube-f4-root", str(self.cube), "--output", str(self.dest)],
                              text=True, capture_output=True, check=False)

    def assert_rejected(self, message):
        before = self.snapshot()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertFalse(self.dest.exists(), result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot(), "The original project changed")

    def test_valid_copy_preserves_source_and_custom_init(self):
        before = self.snapshot()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(ET.parse(self.dest / ".project").findtext("name"), self.dest.name)
        main = (self.dest / "Core/Src/main.c").read_text()
        self.assertEqual(main.count("sk_app_run();"), 1)
        self.assertLess(main.index("existing_user_init();"), main.index("sk_app_run();"))
        self.assertLess(main.index("sk_app_run();"), main.index("/* USER CODE END 2 */"))
        for module in ("TIM", "I2C", "IWDG"):
            self.assertIn("#define HAL_" + module + "_MODULE_ENABLED",
                          (self.dest / "Core/Inc/stm32f4xx_hal_conf.h").read_text())
        self.assertTrue((self.dest / "Core/Src/port_stm32.c").is_file())
        self.assertTrue((self.dest / "Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim.c").is_file())

    def test_existing_main_hook_not_duplicated(self):
        self.edit("Core/Src/main.c", "existing_user_init();",
                  "existing_user_init();\n  extern void sk_app_run(void);\n  sk_app_run();")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dest / "Core/Src/main.c").read_text().count("sk_app_run();"), 1)

    def test_literal_stack_top_accepted(self):
        self.edit(LINKER, "ORIGIN(RAM) + LENGTH(RAM)", "0x20030000")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mixed_f7_build_settings_rejected(self):
        for setting in ("STM32F767xx", "STM32F746ZGTx", "cortex-m7", "fpv5-sp-d16"):
            with self.subTest(setting=setting):
                self.write(".cproject", '<cproject><option value="STM32F429ZITx"/>'
                           '<option value="' + setting + '"/></cproject>')
                self.assert_rejected("F7/M7 build settings")

    def test_ioc_alone_cannot_identify_target(self):
        self.write(".cproject", "<cproject/>")
        self.assert_rejected(".cproject must identify STM32F429")

    def test_stale_startup_rejected(self):
        self.write("Core/Startup/startup_stm32f767xx.s", ".syntax unified\n")
        self.assert_rejected("exactly one F429 startup")

    def test_missing_startup_rejected(self):
        (self.source / "Core/Startup/startup_stm32f429zitx.s").unlink()
        self.assert_rejected("exactly one F429 startup")

    def test_f429_filename_cannot_hide_f7_ram(self):
        self.edit(LINKER, "192K", "512K")
        self.assert_rejected("Wrong F429 linker RAM")

    def test_wrong_stack_top_rejected(self):
        self.edit(LINKER, "ORIGIN(RAM) + LENGTH(RAM)", "0x20080000")
        self.assert_rejected("Wrong/unsupported F429 _estack")

    def test_custom_split_sram_requires_manual_review(self):
        self.edit(LINKER, "RAM (xrw)", "RAM1 (xrw)")
        self.assert_rejected("custom split SRAM needs manual review")

    def test_wrong_ram_origin_rejected(self):
        self.edit(LINKER, "0x20000000", "0x20010000")
        self.assert_rejected("Wrong F429 linker RAM")

    def test_existing_output_preserved(self):
        self.dest.mkdir()
        sentinel = self.dest / "keep.txt"
        sentinel.write_text("User output must survive")
        before = self.snapshot()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Output exists", result.stderr)
        self.assertEqual(sentinel.read_text(), "User output must survive")
        self.assertEqual(list(self.dest.iterdir()), [sentinel])
        self.assertEqual(before, self.snapshot())

    def test_linked_resources_rejected(self):
        self.write(".project", "<projectDescription><name>sharekey_f429</name>"
                   "<linkedResources><link><name>Core</name><location>/other/Core</location>"
                   "</link></linkedResources></projectDescription>")
        self.assert_rejected("Linked project resources")

    def test_embedded_symlink_rejected(self):
        link = self.source / "Core/external"
        try:
            link.symlink_to(self.cube, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks is unavailable")
        self.assert_rejected("Embedded symlink")

    def test_original_project_build_path_rejected(self):
        self.edit(".cproject", "${workspace_loc:/${ProjName}}/Debug",
                  "${workspace_loc:/sharekey_f429}/Debug")
        self.assert_rejected("Literal/external workspace path")

    def test_external_linker_rejected(self):
        self.edit(".cproject", "${workspace_loc:/${ProjName}/" + LINKER + "}",
                  "C:/outside/" + LINKER)
        self.assert_rejected("External/unresolved linker path")

    def test_main_hook_outside_user_section_rejected(self):
        self.edit("Core/Src/main.c", "for (;;) {}", "sk_app_run();\n  for (;;) {}")
        self.assert_rejected("sk_app_run must occur once inside USER CODE 2")

    def test_missing_uart_init_rejected_before_copy(self):
        self.edit("Core/Src/main.c", "  MX_USART3_UART_Init();", "  /* MX_USART3_UART_Init(); */")
        self.assert_rejected("MX_USART3_UART_Init() must be called")

    def test_hal_config_failure_leaves_no_output(self):
        self.write("Core/Inc/stm32f4xx_hal_conf.h", "/* No configurable module defines */\n")
        self.assert_rejected("Cannot safely enable HAL TIM")


if __name__ == "__main__":
    unittest.main()
