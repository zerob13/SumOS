#!/usr/bin/env python3
import hashlib
from pathlib import Path

out = Path(__file__).resolve().parents[1] / 'dist'
with (out / 'SHA256SUMS').open('w') as sums:
    for path in sorted(out.iterdir()):
        if path.name != 'SHA256SUMS':
            with path.open('rb') as stream:
                sums.write(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}\n')
