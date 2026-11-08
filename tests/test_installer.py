import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer_images', ROOT / 'scripts/installer-images.py')
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)
spec = importlib.util.spec_from_file_location('source_audit', ROOT / 'scripts/verify-sources.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class InstallerIntegrity(unittest.TestCase):
    def test_only_sha256_section_authenticates_downloads(self):
        digest = 'a' * 64
        text = f'Suite: stable\nSHA256:\n {digest} 123 image\nSHA512:\n wrong 123 image\n'
        self.assertEqual(images.release_hashes(text)['image'], (digest, 123))

    def test_cached_installer_corruption_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'image'
            file.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                images.cached_download('https://example.org/image', file, hashlib.sha256(b'original').hexdigest())

    def test_embedded_udebs_require_exact_authenticated_binary_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            inventory = work / 'config/installer-inventory'
            inventory.mkdir(parents=True)
            (inventory / 'version').write_text('test-version')
            (inventory / 'Packages').write_text('Package: kernel-di\nVersion: 2\nSource: linux (1)\nBuilt-Using: gcc (= 3)\n\n')
            (inventory / 'initrd.status').write_text('Package: kernel-di\nVersion: 2\n\n')
            self.assertEqual(audit.installer_sources(work), {('linux', '1'), ('gcc', '3'), ('debian-installer', 'test-version')})
            (inventory / 'initrd.status').write_text('Package: kernel-di\nVersion: 4\n\n')
            with self.assertRaisesRegex(ValueError, 'absent from signed package index'):
                audit.installer_sources(work)

    def test_published_preseed_requires_partition_and_account_interaction(self):
        preseed = (ROOT / 'live/config/preseed/sumos.cfg.installer').read_text()
        for forbidden in ['partman/confirm', 'partman-auto/disk', 'passwd/user-password', 'passwd/username']:
            self.assertNotIn(forbidden, preseed)

    def test_test_guest_only_attaches_a_new_virtual_disk_and_ejects_iso(self):
        spec = importlib.util.spec_from_file_location('install_test', ROOT / 'scripts/test-install.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory, patch.object(module.subprocess, 'Popen') as launch:
            directory = Path(directory)
            module.Guest(directory, 'bios', directory / 'fresh.qcow2', directory, 'boot', 22222)
            command = launch.call_args.args[0]
            self.assertNotIn('-cdrom', command)
            self.assertNotIn('-kernel', command)
            self.assertIn(f'file={directory}/fresh.qcow2,format=qcow2,if=virtio', command)
