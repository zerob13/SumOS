import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verify_sources', ROOT / 'scripts/verify-sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceDelivery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.work = Path(self.temporary.name)
        directory = self.work / 'source/debian/e/example'
        directory.mkdir(parents=True)
        self.archive = directory / 'example_1.0.orig.tar.xz'
        self.archive.write_bytes(b'corresponding source fixture')
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (directory / 'example_1.0.dsc').write_text(
            f'Source: example\nVersion: 1.0\nChecksums-Sha256:\n {digest} {self.archive.stat().st_size} {self.archive.name}\n')
        self.inventory = patch.object(module.subprocess, 'check_output', return_value='example\t1.0\n')
        self.inventory.start()

    def tearDown(self):
        self.inventory.stop()
        self.temporary.cleanup()

    def test_exact_source_and_all_referenced_files_accepted(self):
        module.verify(self.work)

    def test_changed_source_file_blocks_release(self):
        self.archive.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed corresponding source'):
            module.verify(self.work)

    def test_different_source_version_blocks_release(self):
        with patch.object(module.subprocess, 'check_output', return_value='example\t1.1\n'):
            with self.assertRaisesRegex(ValueError, 'Exact installed source versions absent'):
                module.verify(self.work)

    def test_missing_source_report_blocks_release(self):
        (self.work / 'source/missing-source.txt').write_text('example')
        with self.assertRaisesRegex(ValueError, 'reported missing'):
            module.verify(self.work)
