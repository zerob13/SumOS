import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'live/config/includes.chroot/usr/lib/sumos'))
from rpc import Client, PROVIDER, RpcError


class FakeDim:
    """Contract fixture: real private NDJSON socket, no real tokens or network."""
    def __init__(self, directory):
        self.endpoint = Path(directory) / 'daemon.sock'
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(self.endpoint))
        self.endpoint.chmod(0o600)
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.done = threading.Event()
        self.calls = []
        self.state = 'pending'
        self.account = False
        self.login_error = False
        self.complete_uri = True
        self.thread = threading.Thread(target=self.serve)
        self.thread.start()

    def reply(self, method, params):
        self.calls.append((method, params))
        if method == 'hello':
            return {'protocolVersion': 3, 'features': ['account.login.begin']}
        if method == 'account.status':
            return {'account': {'name': 'test'} } if self.account else {}
        if method == 'account.login.begin':
            data = {'attemptId': 'test-attempt', 'verificationUri': 'https://example.org/device',
                    'userCode': 'ABCD-EFGH', 'expiresAt': int(time.time()) + 600}
            if self.complete_uri:
                data['verificationUriComplete'] = 'https://example.org/device?code=ABCD-EFGH'
            return data
        if method == 'account.login.status':
            return {'status': self.state}
        return {}

    def serve(self):
        while not self.done.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            with connection, connection.makefile('rwb') as stream:
                for line in stream:
                    request = json.loads(line)
                    method, params = request['method'], request['params']
                    result = self.reply(method, params)
                    response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
                    if self.login_error and method == 'account.login.begin':
                        response.pop('result')
                        response['error'] = {'code': -32000, 'message': 'Network unavailable'}
                    # A real server can interleave progress notices with replies.
                    stream.write(b'{"jsonrpc":"2.0","method":"management.progress","params":{}}\n')
                    stream.write((json.dumps(response) + '\n').encode())
                    stream.flush()

    def close(self):
        self.done.set()
        self.thread.join(timeout=3)
        self.listener.close()
        assert not self.thread.is_alive(), 'Fixture did not stop'


class ProtocolFlow(unittest.TestCase):
    def test_device_rpc_with_notifications_and_private_socket(self):
        with tempfile.TemporaryDirectory() as home:
            server = FakeDim(home)
            try:
                with Client(server.endpoint) as client:
                    login = client.call('account.login.begin', {'providerId': PROVIDER, 'directory': 'https://dimagent.cn'})
                    self.assertEqual(login['userCode'], 'ABCD-EFGH')
                    state = client.call('account.login.status', {'providerId': PROVIDER, 'attemptId': login['attemptId']})
                    self.assertEqual(state['status'], 'pending')
            finally:
                server.close()

    def test_refuses_public_socket_before_connection(self):
        with tempfile.TemporaryDirectory() as home:
            server = FakeDim(home)
            try:
                server.endpoint.chmod(0o666)
                with self.assertRaisesRegex(RpcError, 'private socket'):
                    with Client(server.endpoint):
                        pass
                self.assertEqual(server.calls, [])
            finally:
                server.close()


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Run under xvfb-run for native welcome acceptance')
class WelcomeFlow(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        import welcome
        self.temp = tempfile.TemporaryDirectory()
        self.server = FakeDim(self.temp.name)
        self.rpc_patch = patch.object(welcome, 'Client', lambda: Client(self.server.endpoint))
        self.systemctl_patch = patch.object(welcome.subprocess, 'run')
        self.rpc_patch.start()
        self.systemctl_patch.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = welcome.Welcome(self.root)

    def pump_until(self, condition, timeout=4):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.root.update()
            if condition():
                return
            time.sleep(0.02)
        self.fail('Welcome did not reach the expected state')

    def tearDown(self):
        if not self.app.closed:
            self.app.close()
        self.app.worker.shutdown(wait=True)
        self.systemctl_patch.stop()
        self.rpc_patch.stop()
        self.server.close()
        self.temp.cleanup()

    def test_scan_success_and_completion_clears_code(self):
        self.pump_until(lambda: self.app.attempt is not None)
        self.assertEqual(self.app.code.cget('text'), 'ABCD-EFGH')
        self.assertTrue(self.app.qr.cget('image'))
        self.server.state = 'completed'
        self.app.poll(self.app.generation)
        self.pump_until(lambda: 'Signed in' in self.app.status.cget('text'))
        self.assertEqual(self.app.code.cget('text'), '')
        self.assertFalse(self.app.qr.cget('image'))

    def test_expiry_and_retry_without_complete_uri(self):
        self.server.complete_uri = False
        self.pump_until(lambda: self.app.attempt is not None)
        self.server.state = 'expired'
        self.app.poll(self.app.generation)
        self.pump_until(lambda: 'expired' in self.app.status.cget('text'))
        self.app.begin()
        self.pump_until(lambda: self.app.attempt is not None)
        self.assertTrue(self.app.qr.cget('image'))

    def test_network_failure_can_retry(self):
        self.server.login_error = True
        self.pump_until(lambda: 'unavailable' in self.app.status.cget('text'))
        self.server.login_error = False
        self.app.begin()
        self.pump_until(lambda: self.app.attempt is not None)

    def test_existing_account_does_not_start_new_login(self):
        self.server.account = True
        self.pump_until(lambda: 'Signed in' in self.app.status.cget('text'))
        self.assertFalse(any(method == 'account.login.begin' for method, _ in self.server.calls))

    def test_skip_cancels_pending_login(self):
        self.pump_until(lambda: self.app.attempt is not None)
        self.app.close()
        self.app.worker.shutdown(wait=True)
        self.assertIn(('account.login.cancel', {'providerId': PROVIDER, 'attemptId': 'test-attempt'}), self.server.calls)

    def test_pause_stops_service_and_discards_pending_result(self):
        self.pump_until(lambda: self.app.attempt is not None)
        self.app.pause()
        self.pump_until(lambda: 'stopped' in self.app.status.cget('text'))
        self.assertIsNone(self.app.attempt)
        self.assertFalse(self.app.qr.cget('image'))
        from welcome import subprocess as process
        process.run.assert_called_with(['systemctl', '--user', 'stop', 'sumos-dim.service'], check=True, timeout=20)


@unittest.skipUnless(os.environ.get('DIM_BINARY'), 'Set DIM_BINARY to the locked account-enabled binary')
class NativeDimFlow(unittest.TestCase):
    def test_real_account_enabled_daemon_cli_and_rpc(self):
        binary = Path(os.environ['DIM_BINARY']).resolve()
        with tempfile.TemporaryDirectory() as directory:
            product = Path(directory) / 'product'
            native = product / 'rust'
            native.mkdir(parents=True, mode=0o700)
            product.chmod(0o700)
            endpoint = native / 'daemon.sock'
            with (Path(directory) / 'daemon.log').open('w+') as log:
                process = subprocess.Popen([str(binary), 'app-server', '--product-home', str(product),
                    '--home', str(native), '--unix', str(endpoint), '--no-ws', '--threads', '2',
                    '--defaults', str(binary.parent.parent / 'default-plugins.json')], stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 20
                    while not endpoint.exists() and time.monotonic() < deadline and process.poll() is None:
                        time.sleep(0.1)
                    if not endpoint.exists():
                        log.seek(0)
                        self.fail(log.read())
                    with Client(endpoint) as client:
                        self.assertIn('account.login.begin', client.features)
                        self.assertIn('account.login.status', client.features)
                        providers = client.call('account.providers', {})
                        provider, = (p for p in providers if p['providerId'] == PROVIDER)
                        self.assertIn('device', provider['loginMethods'])
                        self.assertFalse(client.call('account.status', {'providerId': PROVIDER}).get('account'))
                        self.assertEqual(client.call('daemon.ping', {})['serverVersion'], '0.1.0-alpha.20')
                    result = subprocess.run([str(binary), '--home', str(product), 'account', PROVIDER],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                finally:
                    process.terminate()
                    process.wait(timeout=20)
