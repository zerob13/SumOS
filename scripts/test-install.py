#!/usr/bin/env python3
"""Install the ISO to a disposable QEMU disk and boot it twice without the ISO."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import paramiko
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class PreseedHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class Guest:
    def __init__(self, directory, firmware, disk, out, label, ssh_port, install=None):
        self.qmp = directory / f'{label}.sock'
        self.serial = out / f'install-{firmware}-{label}.log'
        self.screenshot = out / f'boot-installed-{firmware}-{label}.png'
        command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg,thread=multi',
            '-m', '4096', '-smp', '2', '-vga', 'std', '-display', 'none', '-no-reboot',
            '-drive', f'file={disk},format=qcow2,if=virtio',
            '-nic', f'user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:{ssh_port}-:22',
            '-serial', f'file:{self.serial}', '-qmp', f'unix:{self.qmp},server=on,wait=off']
        if firmware == 'uefi':
            variables = directory / 'vars.fd'
            if not variables.exists():
                shutil.copy2('/usr/share/OVMF/OVMF_VARS_4M.fd', variables)
            command += ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
                        '-drive', f'if=pflash,format=raw,file={variables}']
        if install:
            iso, installer, url = install
            command += ['-cdrom', str(iso), '-boot', 'd',
                        '-kernel', str(installer / 'vmlinuz'), '-initrd', str(installer / 'initrd.gz'),
                        '-append', 'auto=true priority=critical debian-installer/locale=en_US.UTF-8 '
                        'keyboard-configuration/xkb-keymap=us netcfg/choose_interface=auto '
                        'netcfg/get_hostname=sumos-ci netcfg/get_domain=local '
                        f'preseed/url={url} console=ttyS0,115200n8 DEBIAN_FRONTEND=text ---']
        else:
            command += ['-boot', 'c']
        with (out / f'qemu-installed-{firmware}-{label}.log').open('w') as log:
            self.process = subprocess.Popen(command, stdout=log, stderr=log)

    def wait_for(self, marker, timeout, poweroff=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = self.serial.read_text(errors='replace') if self.serial.exists() else ''
            if marker in text and (not poweroff or self.process.poll() is not None):
                return
            if self.process.poll() is not None:
                raise RuntimeError(f'Guest exited before {marker}; see {self.serial}')
            time.sleep(2)
        raise RuntimeError(f'Timed out waiting for {marker}; see {self.serial}')

    def close(self):
        if self.process.poll() is None and self.qmp.exists():
            try:
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(10)
                    connection.connect(str(self.qmp))
                    stream = connection.makefile('rwb')
                    json.loads(stream.readline())
                    for execute in [{'execute': 'qmp_capabilities'}, {'execute': 'screendump',
                        'arguments': {'filename': str(self.screenshot.with_suffix('.ppm'))}}, {'execute': 'quit'}]:
                        stream.write((json.dumps(execute) + '\n').encode())
                        stream.flush()
                        while True:
                            response = json.loads(stream.readline())
                            if 'error' in response:
                                raise RuntimeError(str(response['error']))
                            if 'return' in response:
                                break
                image = self.screenshot.with_suffix('.ppm')
                Image.open(image).save(self.screenshot)
                image.unlink()
            except (OSError, RuntimeError, ValueError) as error:
                print(f'Could not retain guest screenshot: {error}')
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def unused_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def ssh_command(client, command):
    _, stdout, stderr = client.exec_command(command, timeout=30)
    result, errors = stdout.read().decode(), stderr.read().decode()
    status = stdout.channel.recv_exit_status()
    if status:
        raise RuntimeError(f'Installed-system check failed ({status}): {command}: {errors}')
    return result.strip()


def test_install(iso, firmware, out):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sumos-install-') as temporary:
        directory = Path(temporary)
        disk = directory / 'system.qcow2'
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(disk), '24G'], check=True)
        installer = directory / 'installer'
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract', '/install', str(installer)], check=True)
        password = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(28))
        hashed = subprocess.check_output(['openssl', 'passwd', '-6', '-stdin'], input=password.encode()).decode().strip()
        preseed = (ROOT / 'live/config/preseed/sumos.cfg.installer').read_text() + f'''
# This disposable-VM fixture is never embedded in the distributable ISO.
d-i auto-install/enable boolean true
d-i debian-installer/locale string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap select us
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string sumos-ci
d-i netcfg/get_domain string local
d-i clock-setup/utc boolean true
d-i clock-setup/ntp boolean false
d-i time/zone string Etc/UTC
d-i hw-detect/load_firmware boolean false
d-i anna/choose_modules string live-installer
d-i partman-auto/disk string /dev/vda
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i passwd/user-fullname string SumOS installation test
d-i passwd/username string operator
d-i passwd/user-password-crypted password {hashed}
d-i grub-installer/only_debian boolean true
d-i grub-installer/bootdev string /dev/vda
d-i finish-install/reboot_in_progress note
d-i debian-installer/exit/poweroff boolean true
'''
        webroot = directory / 'preseed'
        webroot.mkdir()
        (webroot / 'preseed.cfg').write_text(preseed)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(PreseedHandler, directory=str(webroot)))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        ssh_port = unused_port()
        guest = Guest(directory, firmware, disk, out, 'installer', ssh_port,
            install=(iso, installer, f'http://10.0.2.2:{server.server_port}/preseed.cfg'))
        try:
            guest.wait_for('SUMOS_INSTALL_COMPLETE', 1800, poweroff=True)
        finally:
            guest.close()
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        marker = secrets.token_hex(16)
        host_key = None
        for label in ['first-boot', 'second-boot']:
            # The installation medium is deliberately absent from these commands.
            guest = Guest(directory, firmware, disk, out, label, ssh_port)
            try:
                # This marker must arrive before SSH login can start a user manager.
                guest.wait_for('SUMOS_INSTALLED_READY', 420)
                with paramiko.SSHClient() as client:
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect('127.0.0.1', port=ssh_port, username='operator', password=password,
                                   look_for_keys=False, allow_agent=False, timeout=20)
                    key = client.get_transport().get_remote_server_key().asbytes()
                    if host_key is not None and key != host_key:
                        raise RuntimeError('SSH host identity changed across reboot')
                    host_key = key
                    assert ssh_command(client, 'id -un') == 'operator'
                    assert ssh_command(client, 'cat /etc/sumos/installed-user') == 'operator'
                    ssh_command(client, 'test ! -e /run/live/medium && test ! -e /etc/sudoers.d/live')
                    ssh_command(client, '! getent passwd sumos && ! sudo -n true 2>/dev/null')
                    ssh_command(client, 'python3 /usr/lib/sumos/health.py')
                    assert ssh_command(client, 'systemctl --user is-active sumos-dim.service') == 'active'
                    assert ssh_command(client, 'loginctl show-user operator -p Linger --value') == 'yes'
                    dim = json.loads((ROOT / 'versions.json').read_text())['dim']
                    assert ssh_command(client, 'sha256sum /opt/dim/bin/dimcode').split()[0] == dim['binary_sha256']
                    expected = dim['version']
                    assert expected in ssh_command(client, 'dim --version')
                    if label == 'first-boot':
                        ssh_command(client, f'printf %s {marker} > "$HOME/install-persistence-check"')
                    else:
                        assert ssh_command(client, 'cat "$HOME/install-persistence-check"') == marker
                    ssh_command(client, 'sync')
                    print(f'{firmware} {label}: installed App Server ready before login; account and state verified')
            finally:
                guest.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('iso', type=Path)
    parser.add_argument('--firmware', choices=['bios', 'uefi'], required=True)
    parser.add_argument('--out', type=Path, default=Path('dist'))
    args = parser.parse_args()
    test_install(args.iso.resolve(), args.firmware, args.out.resolve())
