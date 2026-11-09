#!/usr/bin/env python3
"""Fetch the locked upstream distribution and source without npm install scripts."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(url, destination, algorithm, expected):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    digest = hashlib.new(algorithm, destination.read_bytes()).digest()
    actual = base64.b64encode(digest).decode() if algorithm == 'sha512' else digest.hex()
    if actual != expected:
        raise ValueError(f'Checksum mismatch: {destination}; remove it and retry')


def stage(cache, prefix):
    lock = json.loads((ROOT / 'versions.json').read_text())['dim']
    archive = cache / f'dim-{lock["version"]}.tgz'
    algorithm, digest = lock['integrity'].split('-', 1)
    if algorithm != 'sha512':
        raise ValueError('Expected a SHA-512 integrity pin')
    download(lock['url'], archive, algorithm, digest)
    source = cache / f'dim-source-{lock["source_commit"]}.tar.gz'
    download(lock['source_url'], source, 'sha256', lock['source_sha256'])
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != 'package' or '..' in parts or not (member.isfile() or member.isdir()):
                    raise ValueError('Unexpected archive entry')
            tar.extractall(temporary, filter='data')
        package = Path(temporary) / 'package'
        manifest = json.loads((package / 'release-manifest.json').read_text())
        if (manifest['version'], manifest['sourceCommit'], manifest['platform'], manifest['account']) != (
                lock['version'], lock['source_commit'], 'linux-x64', True):
            raise ValueError('Upstream identity/account-enabled build mismatch')
        if manifest['files']['bin/dimcode'] != lock['binary_sha256']:
            raise ValueError('Pinned Dim executable checksum differs from release manifest')
        actual_files = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in package.rglob('*') if p.is_file()
                        and str(p.relative_to(package)) not in ('package.json', 'release-manifest.json')}
        if actual_files != manifest['files']:
            raise ValueError('Upstream file manifest mismatch')
        target = prefix / 'opt/dim'
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package, target)
        (target / 'bin/dimcode').chmod(0o755)
    return source


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache')
    parser.add_argument('--prefix', type=Path, required=True)
    args = parser.parse_args()
    print(stage(args.cache.resolve(), args.prefix.resolve()))
