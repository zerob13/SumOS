#!/usr/bin/env python3
"""Surface a bounded build-log tail in the workflow's failure annotations."""
from collections import deque
from pathlib import Path
import sys

for name in sys.argv[1:]:
    path = Path(name)
    if path.is_file():
        with path.open(errors='replace') as stream:
            tail = ''.join(deque(stream, maxlen=60))[-20000:]
        if tail:
            message = f'{path.name}:\n{tail}'
            escaped = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=ISO build diagnostic::{escaped}')
