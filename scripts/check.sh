#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mapfile -d '' scripts < <(find scripts live/auto live/config/hooks live/config/includes.installer live/config/includes.chroot/usr/bin live/config/includes.chroot/usr/lib/sumos -type f \( -name '*.sh' -o -name '*.hook.chroot' -o -name '*.hook.source' -o -name config -o -name dim -o -name sumos-agent -o -name sumos-pause -o -name sumos-welcome -o -name install-chrome -o -name boot-check -o -name installed-check -o -name 90sumos \) -print0)
shellcheck "${scripts[@]}"
python3 - <<'PY'
import ast
from pathlib import Path
import xml.etree.ElementTree as ET
for base in ['scripts', 'tests', 'live/config/includes.chroot/usr/lib/sumos']:
    for path in Path(base).glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
for path in Path('live').rglob('*.xml'):
    ET.parse(path)
print('Shell, Python and desktop XML checks passed')
PY
