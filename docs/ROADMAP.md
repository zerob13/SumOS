# Development and acceptance roadmap

## Implemented in the repository

A Debian Live build recipe; native Dim package staging with archive and file
integrity checks; Openbox desktop/session integration; user service; device OAuth
QR welcome; pause/resume; original brand asset provenance; optional Chrome
installer; source-aware release bundle; CI with BIOS and UEFI boot acceptance.

This list describes code, not evidence that an ISO has booted. The restricted
cloud workspace cannot mount filesystems, so full Live image construction and
QEMU validation must be completed by the configured CI or a capable build host.
See CI results for actual measured memory and screenshots. Real account login
and model inference require a user's interactive authorization and have not
been simulated as a successful real login.

## Next release gates

1. Build the ISO in CI. Inspect both boot screenshots and logs; keep all companion
   sources. Test USB boot on an amd64 computer with 4GB RAM.
2. Complete QR login with a real account in both service regions; verify expiry,
   restart, logout and offline behavior. Run a representative agent task with
   ordinary user permissions and inspect approval prompts.
3. Measure idle desktop, one agent session and Chrome with representative pages.
   The current 900 MiB idle CI budget is a gate, not a measured product claim.
4. Test sound, networking, suspend/resume and graphics on the supported hardware.
   Decide whether to publish a separately reviewed firmware-enabled image.
5. Add and test encrypted persistence before recommending storing credentials
   on a portable USB. Never publish a captured authenticated Live filesystem.
6. Add a Calamares-based disk installer only after full VM tests of UEFI/BIOS,
   partitioning, encryption, user creation, bootloader installation, upgrades
   and data preservation. Do not ship an untested disk-writing wrapper.

## Agent desktop integration

The first version supplies X11 tools (`xdotool`, `wmctrl`, `scrot`) for Dim's
existing shell/file tools. It does not pretend a new Dim desktop plugin exists.
Next implement a versioned MCP tool surface for window enumeration, screenshots
and scoped keyboard/mouse actions, with explicit approval and an observable
stop mechanism. Retain operator handover; do not grant a root account or blanket
passwordless administrative permissions to an agent as a product feature.
X11 and same-user processes are not a strong isolation boundary. A future
Wayland design needs a supported capture/input authorization mechanism.

Do not add a heavyweight browser UI or a local model until measurements show
headroom on the 4GB target. LazyVim/LSPs can be an optional developer profile;
Debian's packaged Neovim is sufficient for the base operator tools.
