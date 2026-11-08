#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(id -u) == 0 ]] || { echo 'Build inside the privileged Debian builder (see README).' >&2; exit 1; }
command -v lb >/dev/null
# An early mount probe gives a useful failure instead of half a debootstrap.
probe=$(mktemp -d)
if ! mount -t tmpfs tmpfs "$probe"; then
    rmdir "$probe"
    echo 'ISO building requires mount/chroot capabilities; use a full VM or privileged Docker on a rootful host.' >&2
    exit 1
fi
umount "$probe"
rmdir "$probe"
[[ ! -e build/iso ]] || { echo 'build/iso already exists. Use lb clean --purge there before removing it.' >&2; exit 1; }
python3 scripts/prepare.py build/iso
chown -R root:root build/iso/config/includes.chroot
mkdir -p dist
cd build/iso
lb build 2>&1 | tee ../live-build.log
[[ ! -e source/missing-source.txt ]] || { cat source/missing-source.txt >&2; exit 1; }
[[ -n $(find source/debian -name '*.dsc' -print -quit) ]] || { echo 'Corresponding Debian sources missing' >&2; exit 1; }
cd ../..
python3 scripts/verify-sources.py build/iso
python3 scripts/package-release.py
