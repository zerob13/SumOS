#!/usr/bin/env python3
"""Boot the release ISO, not a substituted test kernel, on a 4 GiB QEMU guest."""
import argparse
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
from PIL import Image


def smoke(iso, firmware, out, timeout):
    out.mkdir(parents=True, exist_ok=True)
    log = out / f'boot-{firmware}.log'
    with tempfile.TemporaryDirectory(prefix='sumos-boot-') as temporary:
        temporary = Path(temporary)
        qmp = temporary / 'qmp.sock'
        command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg,thread=multi',
                   '-m', '4096', '-smp', '2', '-vga', 'std', '-display', 'none',
                   '-cdrom', str(iso), '-boot', 'd', '-nic', 'user,model=virtio-net-pci',
                   '-serial', f'file:{log}', '-qmp', f'unix:{qmp},server=on,wait=off', '-no-reboot']
        if firmware == 'uefi':
            code = Path('/usr/share/OVMF/OVMF_CODE_4M.fd')
            variables = Path('/usr/share/OVMF/OVMF_VARS_4M.fd')
            if not code.is_file() or not variables.is_file():
                raise RuntimeError('Install ovmf: /usr/share/OVMF/OVMF_{CODE,VARS}_4M.fd required')
            copy = temporary / 'vars.fd'
            shutil.copy2(variables, copy)
            command += ['-drive', f'if=pflash,format=raw,readonly=on,file={code}',
                        '-drive', f'if=pflash,format=raw,file={copy}']
        with (out / f'qemu-{firmware}.log').open('w') as stderr:
            process = subprocess.Popen(command, stdout=stderr, stderr=stderr)
        try:
            deadline = time.monotonic() + timeout
            match = None
            while time.monotonic() < deadline and process.poll() is None:
                text = log.read_text(errors='replace') if log.exists() else ''
                match = re.search(r'SUMOS_DESKTOP_READY used_kib=(\d+)', text)
                if match:
                    break
                time.sleep(2)
            # Retain a screenshot even when readiness fails, for diagnosis.
            if qmp.exists() and process.poll() is None:
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(15)
                    connection.connect(str(qmp))
                    stream = connection.makefile('rwb')
                    json.loads(stream.readline())
                    def execute(name, args=None):
                        stream.write((json.dumps({'execute': name, 'arguments': args or {}}) + '\n').encode())
                        stream.flush()
                        while True:
                            response = json.loads(stream.readline())
                            if 'error' in response:
                                raise RuntimeError(str(response['error']))
                            if 'return' in response:
                                return response['return']
                    execute('qmp_capabilities')
                    image = temporary / 'desktop.ppm'
                    execute('screendump', {'filename': str(image)})
                    Image.open(image).save(out / f'boot-{firmware}.png')
                    execute('quit')
            if not match:
                raise RuntimeError(f'{firmware}: desktop and Dim did not become ready in {timeout}s; see {log}')
            used = int(match[1])
            if used > 900 * 1024:
                raise RuntimeError(f'{firmware}: idle memory {used / 1024:.0f} MiB exceeds 900 MiB budget')
            print(f'{firmware}: desktop + Dim RPC ready with 4 GiB RAM; used {used / 1024:.0f} MiB')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('iso', type=Path)
    parser.add_argument('--firmware', choices=['bios', 'uefi'], required=True)
    parser.add_argument('--out', type=Path, default=Path('dist'))
    parser.add_argument('--timeout', type=int, default=420)
    args = parser.parse_args()
    smoke(args.iso.resolve(), args.firmware, args.out.resolve(), args.timeout)
