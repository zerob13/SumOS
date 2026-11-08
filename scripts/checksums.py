#!/usr/bin/env python3
import hashlib
from pathlib import Path
import tarfile


def finalize(out):
    # Successful QEMU runs can produce empty stderr logs, which GitHub's asset
    # API rejects. Preserve all test evidence together, including empty files.
    evidence = sorted(set(out.glob('*.log')) | set(out.glob('boot-*.png')))
    if evidence:
        archive = out / 'boot-tests.tar.gz'
        if archive.exists():
            raise SystemExit('Test evidence is already archived; refusing to mix test runs')
        temporary = out / '.boot-tests.tar.gz.tmp'
        try:
            with tarfile.open(temporary, 'w:gz') as bundle:
                for path in evidence:
                    bundle.add(path, arcname=path.name)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
        for path in evidence:
            path.unlink()
    files = sorted(path for path in out.iterdir() if path.name != 'SHA256SUMS')
    for path in files:
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f'Invalid or empty release asset: {path.name}')
    with (out / 'SHA256SUMS').open('w') as sums:
        for path in files:
            with path.open('rb') as stream:
                sums.write(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}\n')


if __name__ == '__main__':
    finalize(Path(__file__).resolve().parents[1] / 'dist')
