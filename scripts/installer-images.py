#!/usr/bin/env python3
"""Authenticate Debian installer images through the signed Debian Release."""
import gzip
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def release_hashes(text):
    fields = {}
    active = False
    for line in text.splitlines():
        if not line.startswith(' '):
            active = line == 'SHA256:'
        elif active:
            digest, size, name = line.split()
            fields[name] = (digest, int(size))
    if not fields:
        raise ValueError('No authenticated SHA-256 entries in Debian Release')
    return fields


def cached_download(url, destination, digest, size=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    with destination.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest or (size is not None and destination.stat().st_size != size):
        raise ValueError(f'Installer checksum mismatch: {destination}')


def initrd_status(path):
    with gzip.open(path, 'rb') as stream:
        while True:
            header = stream.read(110)
            if header[:6] not in (b'070701', b'070702'):
                raise ValueError('Expected a newc installer initrd')
            size, namesize = int(header[54:62], 16), int(header[94:102], 16)
            name = stream.read(namesize).rstrip(b'\0').decode()
            stream.read((-110 - namesize) % 4)
            if name == 'TRAILER!!!':
                break
            if name.lstrip('./') == 'var/lib/dpkg/status':
                return stream.read(size).decode()
            remaining = size + (-size) % 4
            while remaining:
                chunk = stream.read(min(remaining, 1024 * 1024))
                if not chunk:
                    raise ValueError('Truncated installer initrd')
                remaining -= len(chunk)
    raise ValueError('Installer package status is missing')


def stage(work):
    lock = json.loads((ROOT / 'versions.json').read_text())['installer']
    mirror = 'https://deb.debian.org/debian'
    suite = f'{mirror}/dists/trixie'
    relative = f'main/installer-amd64/{lock["version"]}/images'
    cache = ROOT / '.cache/installer'
    cache.mkdir(parents=True, exist_ok=True)
    inventory = work / 'config/installer-inventory'
    inventory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        signed, verified = temporary / 'InRelease', temporary / 'Release'
        with urllib.request.urlopen(f'{suite}/InRelease', timeout=60) as response, signed.open('wb') as output:
            shutil.copyfileobj(response, output)
        subprocess.run(['gpgv', '--keyring', '/usr/share/keyrings/debian-archive-keyring.gpg',
                        '--output', str(verified), str(signed)], check=True)
        hashes = release_hashes(verified.read_text())
        digest, size = hashes[f'{relative}/SHA256SUMS']
        sums = cache / f'{lock["version"]}-SHA256SUMS'
        cached_download(f'{suite}/{relative}/SHA256SUMS', sums, digest, size)
        image_hashes = {name.removeprefix('./'): value for value, name in
                        (line.split() for line in sums.read_text().splitlines())}
        for name, expected in lock['files'].items():
            if image_hashes.get(name) != expected:
                raise ValueError(f'Installer pin differs from signed Debian metadata: {name}')
            path = cache / f'{lock["version"]}-{name.replace("/", "-")}'
            cached_download(f'{suite}/{relative}/{name}', path, expected)
            if name.endswith('initrd.gz'):
                (inventory / (name.replace('/', '-') + '.status')).write_text(initrd_status(path))
            # live-build's documented download cache is keyed by its current URL.
            url = f'{suite}/main/installer-amd64/current/images/{name}'
            target = work / 'cache/installer_debian-installer' / url.replace('/', '_')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        index_name = 'main/debian-installer/binary-amd64/Packages.xz'
        digest, size = hashes[index_name]
        index = cache / f'{digest}-Packages.xz'
        cached_download(f'{suite}/{index_name}', index, digest, size)
        (inventory / 'Packages').write_bytes(lzma.decompress(index.read_bytes()))
        shutil.copy2(signed, inventory / 'InRelease')
        shutil.copy2(verified, inventory / 'Release')
        shutil.copy2(sums, inventory / 'SHA256SUMS')
        (inventory / 'version').write_text(lock['version'] + '\n')
        (inventory / 'kernels.json').write_text(json.dumps({name.removeprefix('cdrom/'): digest
            for name, digest in lock['files'].items() if name.endswith('vmlinuz')}) + '\n')
        spec = importlib.util.spec_from_file_location('source_audit', ROOT / 'scripts/verify-sources.py')
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        audit.installer_sources(work)
    print(f'Authenticated Debian installer {lock["version"]}')


if __name__ == '__main__':
    import sys
    stage(Path(sys.argv[1]).resolve())
