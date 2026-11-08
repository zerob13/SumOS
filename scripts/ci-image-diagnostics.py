#!/usr/bin/env python3
"""Expose small, fresh-VM boot screenshots through manual diagnostic notices."""
import base64
from pathlib import Path
import sys

for path in sorted(Path(sys.argv[1]).rglob('boot-*.png')):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise SystemExit(f'Screenshot too large for diagnostic notices: {path.name}')
    data = base64.b64encode(path.read_bytes()).decode()
    size = 3000
    count = (len(data) + size - 1) // size
    for index in range(count):
        print(f'::notice title=Boot image {path.name} part {index + 1}/{count}::{data[index * size:(index + 1) * size]}')
