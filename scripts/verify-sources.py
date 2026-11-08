#!/usr/bin/env python3
"""Require exact source versions and all files named by Debian source descriptors."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys


def verify(work):
    source = work / 'source/debian'
    if (work / 'source/missing-source.txt').exists():
        raise ValueError('live-build reported missing source packages')
    descriptors = list(source.rglob('*.dsc'))
    if not descriptors:
        raise ValueError('No Debian source descriptors')
    found = set()
    for descriptor in descriptors:
        text = descriptor.read_text()
        name = re.search(r'^Source: (\S+)$', text, re.MULTILINE)[1]
        version = re.search(r'^Version: (\S+)$', text, re.MULTILINE)[1]
        found.add((name, version))
        hashes = re.search(r'^Checksums-Sha256:\n((?: [^\n]+\n)+)', text, re.MULTILINE)
        if not hashes:
            raise ValueError(f'Missing SHA-256 file list: {descriptor}')
        for record in hashes[1].splitlines():
            expected, size, filename = record.split()
            if Path(filename).name != filename:
                raise ValueError(f'Unsafe source filename in {descriptor}')
            path = descriptor.parent / filename
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != expected or path.stat().st_size != int(size):
                raise ValueError(f'Incomplete or changed corresponding source: {path}')
    installed = subprocess.check_output(['chroot', str(work / 'chroot'), 'dpkg-query', '-W',
        '-f=${source:Package}\t${source:Version}\n'], text=True)
    required = {tuple(line.split('\t')) for line in installed.splitlines()}
    missing = required - found
    if missing:
        raise ValueError(f'Exact installed source versions absent: {sorted(missing)}')
    print(f'Corresponding sources verified: {len(required)} installed source versions; {len(found)} descriptors')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
