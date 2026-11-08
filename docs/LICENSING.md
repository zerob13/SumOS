# Licensing and corresponding source

SumOS build configuration and original integration code are MIT licensed under
this repository's LICENSE. An ISO is a collection of separately licensed works:
the MIT license does not relicense the Linux kernel, GNU tools, Debian packages,
Dim dependencies, fonts, firmware, or proprietary programs.

## Debian and GPL components

The default ISO uses Debian 13 main, with the original Debian package metadata
and `/usr/share/doc/*/copyright` files retained. The base `/etc/os-release` is
retained to keep package/OS detection working; SumOS identifies the derivative
through its boot menu, welcome page, `/etc/issue` and `/etc/lsb-release`.
This is not an official Debian image. No Debian logo is used as SumOS's logo.
Debian's name and trademarks remain their owners' property.

`live-build --source true --source-images tar` downloads companion source
packages. A source-stage hook completes that inventory using every installed
binary and retained bootloader/helper `.deb`, installer pool `.deb`/`.udeb`, and authenticated installer-initrd package inventories, including exact `Built-Using` and
`Static-Built-Using` dependencies (notably the actual Linux source behind signed
kernels). It compares these versions against the archived `.dsc` descriptors and
verifies every referenced source file's size and SHA-256.

Debian live-build currently attempts to download `grub-efi` as a source package,
even though that bootloader flag is not a source identity. The hook downloads the
actual GRUB source from binary metadata (`grub2`), verifies the entire expanded
inventory, and only then retains any upstream download report as
`source/live/live-build-download-report.txt`. A genuine missing version, corrupt
source or failed download still blocks the build. The full required inventory is
saved in `source/live/sumos-required-sources.json`. Source archives are generated
only after this check. Release uploads must include
all of these files, not just the ISO. Debian source packages include upstream
source, Debian patches and packaging/build instructions. Preserve them alongside
that exact binary image, including mirrors and older releases; do not replace
older source with current upstream source. Source download failure is a release
failure, not permission to publish without it.

Sources are divided into numbered parts to stay below GitHub's per-file limit.
After verifying `SHA256SUMS`, concatenate matching parts in numeric order:

```sh
cat live-image-amd64-source.debian.tar*.part* > debian-sources.tar
cat live-image-amd64-source.live.tar*.part* > live-sources.tar
file debian-sources.tar live-sources.tar
# If live-build used gzip/xz compression, tar can detect it:
tar -tf debian-sources.tar
```

The original archive names are recorded in `build-manifest.json`; use those
names if live-build's image naming changes. Each source archive is split even
when there is only one `.part000`. Keep every part. `sumos-source.tar.gz` contains
this project's build configuration, scripts, tests, branding and documentation.
The package manifest records binary versions for each build.

Background: https://www.debian.org/legal/licenses/ and
https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary .
The automation assists source delivery; before public distribution review the
actual package inventory and any new components for their own obligations.

## Dim

Use the unmodified official `dimcode-linux-x64` package pinned in `versions.json`.
It includes its own LICENSE, NOTICE, Rust third-party notices, vendored Aimux and
grok-build attributions, and plugin licenses. Preserve the entire distribution
under `/opt/dim`, not just its executable. Its original source archive at the
manifest's exact commit is included as `dim-source.tar.gz`. OAuth client IDs are
provided by that upstream account-enabled release; SumOS does not extract them,
ship account credentials, or require users to provide build-time IDs.

Branding asset provenance and its MIT notice: `assets/NOTICE.md`, also installed
as `/usr/share/doc/sumos/BRANDING.md`. MIT copyright permission does not transfer
trademark ownership or imply endorsement.

## Chrome and firmware

Google Chrome is proprietary and is deliberately absent from the redistributable
ISO. The welcome UI asks the user to review and accept Google's terms before
invoking an administrator-authorized installer. The installer downloads Google's
public APT key over verified HTTPS, scopes it with `signed-by` to Google's APT
source, and uses APT's normal package signature verification. Do not redistribute
an ISO rebuilt from a session with Chrome or private account data installed.
Chrome terms: https://www.google.com/chrome/terms/ .

Non-free firmware is excluded by default. Adding firmware or other archives is
a separate change requiring a package-by-package redistribution review; the
repository MIT license does not make those files MIT.

## Installer images

The Debian installer kernel and initrd pins are recorded in `versions.json`.
Preparation verifies Debian's InRelease using the Debian archive keyring, checks
SHA256SUMS against that authenticated Release, and checks each pinned image
against both the signed metadata and its SHA-256. The signed installer package
index resolves embedded udeb versions to their exact source identities. Installer
source, embedded components, downloadable installer modules and installed target
packages are all included in source auditing, including Built-Using dependencies.
SumOS's finish-install hook and preseed defaults are in its accompanying source.
Updating the pinned installer release requires reviewing its new signed hashes;
verification failures never fall back to an unverified download.
