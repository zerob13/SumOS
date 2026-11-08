FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    live-build debootstrap ca-certificates debian-archive-keyring gpgv curl python3 git \
    xorriso squashfs-tools syslinux-common isolinux grub-pc-bin grub-efi-amd64-bin \
    mtools dosfstools cpio file rsync gzip xz-utils bzip2 apt-utils && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /repo
CMD ["bash", "scripts/build-iso.sh"]
