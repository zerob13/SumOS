SumOS amd64 preview: a Debian 13 Live desktop with the native Dim agent and QR
device login. Independent community derivative; not an official Debian or Dim
release. ISO is a bootable hybrid USB/DVD image. This preview has no disk installer
and no Secure Boot support. Some hardware requires firmware absent from main.

Chrome is installed from Google only after accepting its terms; it is not
redistributed in this ISO. Accounts and files in Live mode are ephemeral without
separately configured persistence. No local model is included.

This release job requires BIOS and UEFI desktop/RPC readiness in a 4 GiB QEMU VM
and enforces a 900 MiB idle-memory ceiling. See included logs and screenshots.
This does not cover arbitrary browser workloads, real OAuth/model service access
or physical hardware compatibility.

Verify `SHA256SUMS` before booting. All Debian source parts, Dim source and SumOS
source accompany this exact ISO. Keep and redistribute them together. Read
LICENSING.md for reconstruction and third-party obligations; the repository's
MIT license applies only to SumOS's own code and configuration.
