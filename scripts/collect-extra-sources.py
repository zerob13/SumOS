#!/usr/bin/env python3
"""Complete source delivery using installed/cached binary metadata, not boot flags."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('verify_sources', here / 'verify-sources.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
work = Path(sys.argv[1]).resolve()
source_root = work / 'source/debian'
found = set()
for descriptor in source_root.rglob('*.dsc'):
    text = descriptor.read_text()
    found.add((re.search(r'^Source: (\S+)$', text, re.MULTILINE)[1],
               re.search(r'^Version: (\S+)$', text, re.MULTILINE)[1]))
required = audit.required_sources(work)
# Save provenance with the source archive even when a download later fails.
provenance = work / 'source/live/sumos-required-sources.json'
provenance.parent.mkdir(parents=True, exist_ok=True)
provenance.write_text(json.dumps(sorted(required), indent=2) + '\n')
chroot = work / 'chroot'
staging = chroot / 'sumos-extra-sources'
staging.mkdir(exist_ok=True)
subprocess.run(['chroot', str(chroot), 'chown', '_apt:root', '/sumos-extra-sources'], check=True)
for name, version in sorted(required - found):
    print(f'Collecting corresponding source: {name}={version}', flush=True)
    subprocess.run(['chroot', str(chroot), 'sh', '-c',
        'cd /sumos-extra-sources && exec apt-get --only-source --download-only source "$1"',
        'sh', f'{name}={version}'], check=True)
    prefix = name[:4] if name.startswith('lib') else name[0]
    destination = source_root / prefix / name
    destination.mkdir(parents=True, exist_ok=True)
    for file in staging.iterdir():
        target = destination / file.name
        if target.exists():
            with file.open('rb') as left, target.open('rb') as right:
                if hashlib.file_digest(left, 'sha256').digest() != hashlib.file_digest(right, 'sha256').digest():
                    raise ValueError(f'Source archive filename collision: {target}')
            file.unlink()
        else:
            shutil.move(file, target)
staging.rmdir()
# This gate checks every installed/cached binary's exact source and Built-Using,
# plus every referenced source file's size and SHA-256. Only then may the false
# upstream virtual-package report be retained under an informational filename.
audit.verify(work, resolve_upstream_report=True)
