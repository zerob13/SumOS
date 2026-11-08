# Install SumOS on a computer

SumOS uses Debian Installer's Live installation mode. It copies the SumOS system,
including Dim and the desktop, from the ISO to disk and installs GRUB. Partition
selection, formatting confirmation, username and password remain interactive.
No unattended disk-wipe configuration or default installed password is included.

## Installation

1. Write `sumos-amd64.iso` to a USB stick or attach it to a VM's virtual optical
   drive. Verify SHA256SUMS before booting. This image is for amd64 computers;
   UEFI Secure Boot is not supported by this preview.
2. Boot the USB/ISO in the same BIOS or UEFI mode intended for the installed
   system. Choose **Install SumOS (graphical)**. A text installer is also available.
   From a Live desktop use **Install OS** in Welcome or **Install SumOS to disk**
   from the menu.
3. Select language, keyboard and network settings. Choose the target disk and
   review the partitioning/formatting summary. Formatting erases data on the
   selected partitions; back up existing data before proceeding.
4. Create your own normal user and password. The installed system does not use
   the Live account or its passwordless administrative policy. Debian Installer
   configures password-protected sudo for the installation user.
5. Finish installation, shut down, remove the USB/ISO and boot the system disk.
   Log in for the desktop and QR Welcome screen, or connect over SSH.

The system payload and bootloader packages are supplied on the ISO. Network
access is needed for Dim authentication/model use, future updates and optional
Chrome installation, rather than to replace SumOS with a stock Debian desktop.
Main-only firmware limitations from the README still apply.

## Use the computer as a Dim App Server

The installation user owns the Dim runtime and its private `~/.dimcode` state.
Their systemd user service is enabled with lingering, so it starts on system boot
before desktop login and continues after logout. It is not a root service.
Only the installation owner's user manager is enabled by the installed default.

SSH starts on the installed system with a freshly generated host identity. It is
disabled in Live mode. Use the account and password created in the installer:

```sh
ssh your-user@computer-address
systemctl --user status sumos-dim
python3 /usr/lib/sumos/health.py
dim login dimcode-api-oauth --directory https://dimagent.cn --device
sumos-agent
```

Phone/device login is also available in the desktop Welcome screen. Sign in
**after installing** to keep credentials on the system disk. Files, sessions and
account state persist across reboot. No account or OAuth token is baked into the
installation image.

The App Server continues to expose its private local Unix socket; no anonymous
public RPC port is opened. Operate it through SSH or Dim's supported authenticated
clients. Desktop input/screenshot tools require the installation user to be
logged into the X11 desktop. The default single-seat display is `:0` with the
user's `~/.Xauthority`.

```sh
sumos-pause                       # stop until explicitly resumed or rebooted
systemctl --user mask --now sumos-dim
loginctl disable-linger "$USER"    # if background service operation is unwanted
```

The installed defaults are managed in `/etc/systemd/user/default.target.wants`;
to permanently disable the distribution's global default, an administrator can
run `sudo systemctl --global disable sumos-dim.service`. Ordinary file/model work
can run before desktop login. Device access and administrative commands retain
normal system permissions and Dim's approval behavior.

## Acceptance tests

CI boots the Live ISO under BIOS and UEFI in 4 GiB, then runs the actual Debian
installer against a newly created 24 GiB qcow2 disk in each firmware mode. The
partitioning preseed and random test credentials exist only in the temporary test
harness and are never embedded in the published ISO.

After installation, each VM boots from disk twice **without any ISO, direct
kernel or initrd arguments**. Tests require the App Server readiness marker before
SSH login, authenticate as the created user, check the pinned Dim executable,
reject the Live account/passwordless sudo policy, and verify account identity,
SSH host-key persistence and a file surviving the next cold boot. They do not
attach, format or otherwise modify a real host disk.

```sh
python3 scripts/test-install.py dist/sumos-amd64.iso --firmware bios
python3 scripts/test-install.py dist/sumos-amd64.iso --firmware uefi
```

Manual partitioning, encryption, dual-boot data preservation and hardware-specific
drivers need additional machine-level acceptance before being recommended for
those scenarios. The CI disk tests cover guided installation to an empty disk.
