#!/usr/bin/env python3
"""Surface a bounded build-log tail in the workflow's failure annotations."""
from collections import deque
from pathlib import Path
import sys
import re

for name in sys.argv[1:]:
    path = Path(name)
    if path.is_file():
        with path.open(errors='replace') as stream:
            tail_lines = deque(maxlen=60)
            errors = deque(maxlen=40)
            for number, line in enumerate(stream, 1):
                tail_lines.append(line)
                if re.search(r'(^E:|error:|Traceback|failed|not found|No such|Unable to)', line, re.IGNORECASE):
                    errors.append(f'{number}: {line}')
            tail = ('Matching diagnostics:\n' + ''.join(errors) + '\nFinal output:\n' + ''.join(tail_lines))[-24000:]
        if tail:
            message = f'{path.name}:\n{tail}'
            escaped = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=ISO build diagnostic::{escaped}')
