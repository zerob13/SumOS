import hashlib
import json
from pathlib import Path
import runpy
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBundle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ['scripts', 'docs', 'live', 'assets', 'tests', '.github', 'dist', '.cache',
                     'build/iso/config/includes.chroot/opt/dim']:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for name in ['README.md', 'LICENSE', 'Dockerfile', 'versions.json', 'docs/LICENSING.md',
                     'scripts/package-release.py', 'scripts/checksums.py']:
            shutil.copy2(ROOT / name, self.root / name)
        work = self.root / 'build/iso'
        self.iso = work / 'fixture.hybrid.iso'
        self.iso.write_bytes(b'fixture ISO bytes; not a bootable image')
        (work / 'fixture.packages').write_text('example 1.0\n')
        self.debian = b'fixture corresponding source bytes'
        (work / 'fixture-source.debian.tar').write_bytes(self.debian)
        (work / 'fixture-source.live.tar').write_bytes(b'fixture live configuration source')
        (work / 'config/includes.chroot/opt/dim/NOTICE').write_text('fixture notice')
        commit = json.loads((ROOT / 'versions.json').read_text())['dim']['source_commit']
        (self.root / f'.cache/dim-source-{commit}.tar.gz').write_bytes(b'fixture Dim source')

    def tearDown(self):
        self.temporary.cleanup()

    def package(self):
        def git(args, **kwargs):
            return 'a' * 40 + '\n' if 'rev-parse' in args else b''
        with patch('subprocess.check_output', side_effect=git):
            runpy.run_path(str(self.root / 'scripts/package-release.py'))

    def test_release_retains_iso_sources_notices_and_verifiable_checksums(self):
        self.package()
        out = self.root / 'dist'
        self.assertEqual((out / 'sumos-amd64.iso').read_bytes(), self.iso.read_bytes())
        restored = b''.join(p.read_bytes() for p in sorted(out.glob('*source.debian.tar.part*')))
        self.assertEqual(restored, self.debian)
        self.assertTrue((out / 'DIM-NOTICE').is_file())
        self.assertTrue((out / 'dim-source.tar.gz').is_file())
        with tarfile.open(out / 'sumos-source.tar.gz') as archive:
            self.assertIn('SumOS/LICENSE', archive.getnames())
            self.assertIn('SumOS/scripts/package-release.py', archive.getnames())
        for line in (out / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)

    def test_missing_companion_archive_blocks_packaging(self):
        (self.root / 'build/iso/fixture-source.debian.tar').unlink()
        with self.assertRaisesRegex(SystemExit, 'source archives are required'):
            self.package()

    def test_empty_qemu_logs_are_preserved_in_uploadable_evidence_archive(self):
        self.package()
        out = self.root / 'dist'
        (out / 'qemu-bios.log').write_bytes(b'')
        (out / 'boot-bios.log').write_bytes(b'SUMOS_DESKTOP_READY\n')
        (out / 'boot-bios.png').write_bytes(b'fixture screenshot bytes')
        script = str(self.root / 'scripts/checksums.py')
        runpy.run_path(script, run_name='__main__')
        with tarfile.open(out / 'boot-tests.tar.gz') as archive:
            self.assertEqual(archive.extractfile('qemu-bios.log').read(), b'')
            self.assertEqual(archive.extractfile('boot-bios.log').read(), b'SUMOS_DESKTOP_READY\n')
            self.assertEqual(archive.extractfile('boot-bios.png').read(), b'fixture screenshot bytes')
        self.assertFalse((out / 'qemu-bios.log').exists())
        self.assertEqual((out / 'sumos-amd64.iso').read_bytes(), self.iso.read_bytes())
        checksums = (out / 'SHA256SUMS').read_bytes()
        for line in checksums.decode().splitlines():
            digest, name = line.split('  ', 1)
            self.assertGreater((out / name).stat().st_size, 0)
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
        runpy.run_path(script, run_name='__main__')
        self.assertEqual((out / 'SHA256SUMS').read_bytes(), checksums)
