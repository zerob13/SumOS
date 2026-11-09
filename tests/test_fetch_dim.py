import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch_dim', ROOT / 'scripts/fetch-dim.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class DistributionIntegrity(unittest.TestCase):
    def test_nested_plugin_package_metadata_is_verified_and_preserved(self):
        for tampered in (False, True):
            with self.subTest(tampered=tampered), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cache = root / 'cache'
                cache.mkdir()
                files = {'bin/dimcode': b'fixture executable',
                         'plugins/example/package.json': b'{"name":"example"}'}
                manifest = {'version': 'fixture', 'sourceCommit': 'fixture-commit',
                            'platform': 'linux-x64', 'account': True,
                            'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
                if tampered:
                    files['plugins/example/package.json'] = b'{"name":"changed"}'
                entries = {**files, 'package.json': b'{"name":"platform-wrapper"}',
                           'release-manifest.json': json.dumps(manifest).encode()}
                archive = cache / 'dim-fixture.tgz'
                with tarfile.open(archive, 'w:gz') as bundle:
                    for name, data in entries.items():
                        member = tarfile.TarInfo('package/' + name)
                        member.size = len(data)
                        bundle.addfile(member, io.BytesIO(data))
                source = cache / 'dim-source-fixture-commit.tar.gz'
                source.write_bytes(b'fixture source archive')
                lock = {'version': 'fixture', 'source_commit': 'fixture-commit',
                        'url': 'https://example.org/binary', 'source_url': 'https://example.org/source',
                        'integrity': 'sha512-' + base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode(),
                        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'binary_sha256': manifest['files']['bin/dimcode']}
                (root / 'versions.json').write_text(json.dumps({'dim': lock}))
                with patch.object(fetch, 'ROOT', root), patch.object(fetch.urllib.request, 'urlopen') as network:
                    if tampered:
                        with self.assertRaisesRegex(ValueError, 'file manifest mismatch'):
                            fetch.stage(cache, root / 'staging')
                    else:
                        fetch.stage(cache, root / 'staging')
                        nested = root / 'staging/opt/dim/plugins/example/package.json'
                        self.assertEqual(nested.read_bytes(), files['plugins/example/package.json'])
                    network.assert_not_called()
