SumOS amd64 preview: a Debian 13 Live desktop with Dim 0.1.0-alpha.21 and QR
device login. Independent community derivative; not an official Debian or Dim
release. ISO is a bootable hybrid USB/DVD image. Includes Debian graphical/text disk installation and an unprivileged App Server
that starts on boot after installation. Secure Boot is not supported. Some hardware requires firmware absent from main.

Chrome is installed from Google only after accepting its terms; it is not
redistributed in this ISO. Accounts and files in Live mode are ephemeral without
separately configured persistence. No local model is included.

This release job requires BIOS and UEFI desktop/RPC readiness in a 4 GiB QEMU VM
and enforces a 900 MiB idle-memory ceiling. See logs and screenshots in `boot-tests.tar.gz`.
This does not cover arbitrary browser workloads, real OAuth/model service access
or physical hardware compatibility. CI also installs to fresh BIOS and UEFI
virtual disks and verifies independent disk boot and persistent user state.

Dim 0.1.0-alpha.21 upgrades Timeline storage to v36. Back up `~/.dimcode` before
upgrading an existing installation. Older Dim binaries cannot read the upgraded
store; restore the pre-upgrade backup if a rollback is needed. The bundled host
and default plugins come from the same upstream release.

Verify `SHA256SUMS` before booting. All Debian source parts, Dim source and SumOS
source accompany this exact ISO. Keep and redistribute them together. Read
LICENSING.md for reconstruction and third-party obligations; the repository's
MIT license applies only to SumOS's own code and configuration.
