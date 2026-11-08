#!/usr/bin/env python3
"""Generate an isolated live-build working directory. Never builds in live/."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch_dim', ROOT / 'scripts/fetch-dim.py')
fetch_dim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_dim)


def prepare(work):
    if work.exists():
        raise SystemExit(f'{work} already exists; use a new empty build directory')
    shutil.copytree(ROOT / 'live', work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    tools = work / 'config/source-tools'
    tools.mkdir(parents=True, exist_ok=True)
    for name in ['collect-extra-sources.py', 'verify-sources.py']:
        shutil.copy2(ROOT / 'scripts' / name, tools / name)
    installer_spec = importlib.util.spec_from_file_location('installer_images', ROOT / 'scripts/installer-images.py')
    installer = importlib.util.module_from_spec(installer_spec)
    installer_spec.loader.exec_module(installer)
    installer.stage(work)
    prefix = work / 'config/includes.chroot'
    source = fetch_dim.stage(ROOT / '.cache', prefix)
    banner = ROOT / 'assets/dim-banner.png'
    lock = json.loads((ROOT / 'versions.json').read_text())
    if hashlib.sha256(banner.read_bytes()).hexdigest() != lock['branding']['sha256']:
        raise SystemExit('Branding asset checksum mismatch')
    for location in ['usr/share/backgrounds/sumos', 'usr/share/plymouth/themes/sumos']:
        destination = prefix / location
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(banner, destination / 'dim-banner.png')
    shutil.copy2(banner, work / 'config/bootloaders/grub-pc/dim-banner.png')
    shutil.copy2(banner, work / 'config/bootloaders/syslinux_common/splash.png')
    doc = prefix / 'usr/share/doc/sumos'
    doc.mkdir(parents=True, exist_ok=True)
    for name in ['LICENSE', 'versions.json']:
        shutil.copy2(ROOT / name, doc / name)
    shutil.copy2(ROOT / 'docs/LICENSING.md', doc / 'LICENSING.md')
    shutil.copy2(ROOT / 'assets/NOTICE.md', doc / 'BRANDING.md')
    # live-build source.live archives its own configuration; keep the extra
    # upstream source alongside the final release as well.
    print(f'Prepared {work}; upstream source: {source}')
    work.chmod(0o755)
    for path in work.rglob('*'):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    subprocess.run(['lb', 'config'], cwd=work, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    prepare(args.directory.resolve())
