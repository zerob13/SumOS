#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
report_failure() {
    result=$?
    trap - ERR
    python3 scripts/ci-diagnostics.py build/builder-image.log build/iso-build.log build/iso/source/missing-source.txt || true
    exit "$result"
}
trap report_failure ERR
docker build -t sumos-builder . 2>&1 | tee build/builder-image.log
docker run --rm --privileged -v "$PWD:/repo" sumos-builder 2>&1 | tee build/iso-build.log
