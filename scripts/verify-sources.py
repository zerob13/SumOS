#!/usr/bin/env python3
"""Require exact source versions and all files named by Debian source descriptors."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from email.parser import Parser


def built_using(value):
    result = set()
    for entry in value.split(','):
        if not entry.strip():
            continue
        match = re.fullmatch(r'\s*([a-z0-9][a-z0-9+.-]*)\s*\(=\s*([^\s)]+)\)\s*', entry)
        if not match:
            raise ValueError(f'Unsupported Built-Using declaration: {entry}')
        result.add(match.groups())
    return result


def required_sources(work):
    installed = subprocess.check_output(['chroot', str(work / 'chroot'), 'dpkg-query', '-W',
        '-f=${source:Package}\t${source:Version}\t${Built-Using}\t${Static-Built-Using}\n'], text=True)
    installed = re.sub(r'\n[ \t]+', ' ', installed)
    required = set()
    for line in installed.splitlines():
        name, version, built, static = line.split('\t')
        if name and version:
            required.add((name, version))
        required.update(built_using(built))
        required.update(built_using(static))
    # Bootloader helpers are temporarily installed and then removed by live-build.
    # Its retained debs record the precise source for the code copied into the ISO.
    for archive in (work / 'cache').rglob('*.deb'):
        control = Parser().parsestr(subprocess.check_output(['dpkg-deb', '--field', str(archive)], text=True))
        source = control.get('Source', control['Package'])
        match = re.fullmatch(r'([^\s]+)(?: \(([^)]+)\))?', source)
        if not match:
            raise ValueError(f'Invalid source identity in {archive}')
        required.add((match[1], match[2] or control['Version']))
        required.update(built_using(control.get('Built-Using', '')))
        required.update(built_using(control.get('Static-Built-Using', '')))
    return required


def verify(work, resolve_upstream_report=False):
    source = work / 'source/debian'
    if (work / 'source/missing-source.txt').exists() and not resolve_upstream_report:
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
    required = required_sources(work)
    missing = required - found
    if missing:
        raise ValueError(f'Exact installed source versions absent: {sorted(missing)}')
    report = work / 'source/missing-source.txt'
    if report.exists():
        destination = work / 'source/live/live-build-download-report.txt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        report.replace(destination)
        print('Upstream source-download report retained; all shipped source versions verified')
    print(f'Corresponding sources verified: {len(required)} installed source versions; {len(found)} descriptors')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve(), resolve_upstream_report='--resolve-upstream-report' in sys.argv[2:])
