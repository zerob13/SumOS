#!/usr/bin/env python3
"""Assemble a release only with companion source, notices and SHA256SUMS."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / 'build/iso'
out = ROOT / 'dist'
if list(out.glob('*')):
    raise SystemExit('dist must be empty; refusing to mix releases')
out.mkdir(exist_ok=True)
if (work / 'source/missing-source.txt').exists():
    raise SystemExit('live-build could not obtain all corresponding sources')
iso, = work.glob('*.hybrid.iso')
if iso.stat().st_size > 1900 * 1024 * 1024:
    raise SystemExit('ISO exceeds the 1900 MiB release size budget')
shutil.copy2(iso, out / 'sumos-amd64.iso')
sources = list(work.glob('*-source.*.tar*'))
if not any('-source.debian.' in p.name for p in sources) or not any('-source.live.' in p.name for p in sources):
    raise SystemExit('Debian and live-build source archives are required')
# Each GitHub release asset must stay below 2 GiB. Split, never omit sources.
for source in sources:
    with source.open('rb') as stream:
        index = 0
        while first := stream.read(8 * 1024 * 1024):
            with (out / f'{source.name}.part{index:03d}').open('wb') as part:
                part.write(first)
                remaining = 1024 * 1024 * 1024 - len(first)
                while remaining:
                    chunk = stream.read(min(remaining, 8 * 1024 * 1024))
                    if not chunk:
                        break
                    part.write(chunk)
                    remaining -= len(chunk)
            index += 1
lock = json.loads((ROOT / 'versions.json').read_text())
upstream = ROOT / '.cache' / f'dim-source-{lock["dim"]["source_commit"]}.tar.gz'
shutil.copy2(upstream, out / 'dim-source.tar.gz')
for name in ['LICENSE', 'versions.json']:
    shutil.copy2(ROOT / name, out / name)
shutil.copy2(ROOT / 'docs/LICENSING.md', out / 'LICENSING.md')
shutil.copy2(work / 'config/includes.chroot/opt/dim/NOTICE', out / 'DIM-NOTICE')
# Include this distribution's build scripts and configuration, including local
# changes when building from an uncommitted checkout.
with tarfile.open(out / 'sumos-source.tar.gz', 'w:gz') as tar:
    for name in ['README.md', 'LICENSE', 'versions.json', 'live', 'assets', 'scripts', 'docs', 'tests', '.github']:
        tar.add(ROOT / name, arcname=f'SumOS/{name}',
                filter=lambda item: None if '__pycache__' in item.name or item.name.endswith('.pyc') else item)
manifest = {
    'sumosCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
    'versions': lock,
    'isoBytes': (out / 'sumos-amd64.iso').stat().st_size,
    'debianSources': [p.name for p in sources],
}
(out / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
for candidate in work.glob('*.packages'):
    shutil.copy2(candidate, out / candidate.name)
with (out / 'SHA256SUMS').open('w') as sums:
    for path in sorted(out.iterdir()):
        if path.name != 'SHA256SUMS':
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            sums.write(f'{digest}  {path.name}\n')
print(f'Release files: {out}')
