"""oled-rtc-servo-bench-20261127-v3: build the imported bench firmware.

This helper is newly added tooling, not firmware used in the reported bench test.
No flash programming or original-project writes are performed.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='arm-none-eabi-gcc')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    compiler = shutil.which(args.cc)
    if not compiler:
        parser.error('Compiler not found; supply --cc with the compiler path.')
    output = root / 'build-motor'
    output.mkdir(exist_ok=True)
    flags = ['-mcpu=cortex-m4', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard', '-mthumb']
    includes = ['Inc', 'Drivers/STM32F4xx_HAL_Driver/Inc',
                'Drivers/STM32F4xx_HAL_Driver/Inc/Legacy',
                'Drivers/CMSIS/Device/ST/STM32F4xx/Include', 'Drivers/CMSIS/Include']
    common = flags + ['-std=gnu11', '-g3', '-DDEBUG', '-DUSE_HAL_DRIVER',
                      '-DSTM32F429xx', '-O0', '-ffunction-sections', '-fdata-sections',
                      '-Wall', '--specs=nano.specs'] + ['-I' + s for s in includes]
    sources = sorted(root.glob('Src/*.c')) + sorted(root.glob('Drivers/STM32F4xx_HAL_Driver/Src/*.c'))
    sources += sorted(root.glob('Startup/*.s'))
    objects = []
    commands = []
    for source in sources:
        rel = source.relative_to(root).as_posix()
        obj = output / (rel.replace('/', '_') + '.o')
        command = [compiler, *common, '-c', rel, '-o', str(obj)]
        commands.append(command)
        subprocess.run(command, cwd=root, check=True)
        objects.append(str(obj))
    elf = output / 'MDD3A_Motor_Test.elf'
    command = [compiler, *flags, '-TSTM32F429ZITX_FLASH.ld', '--specs=nosys.specs',
               '--specs=nano.specs', '-static', '-z', 'noexecstack', '-Wl,--gc-sections',
               '-Wl,-Map=' + str(output / 'MDD3A_Motor_Test.map'),
               *objects, '-Wl,--start-group', '-lc', '-lm', '-Wl,--end-group', '-o', str(elf)]
    commands.append(command)
    subprocess.run(command, cwd=root, check=True)
    version = subprocess.check_output([compiler, '--version'], text=True).splitlines()[0]
    report = {'snapshot_id': 'oled-rtc-servo-bench-20261127-v3', 'built_at': datetime.now().astimezone().isoformat(timespec='seconds'),
              'compiler': version, 'translation_units': len(sources),
              'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
              'result': 'PASS', 'uploaded': False, 'commands': commands}
    (output / 'build_result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: {len(sources)} units compiled and linked; no upload performed.')
    print(version)
    print('ELF SHA256: ' + report['elf_sha256'])


if __name__ == '__main__':
    main()
