"""Dim local protocol v3. Authentication stays entirely in Dim's account plugin."""
import json
import os
from pathlib import Path
import socket
import stat
import time

PROVIDER = 'dimcode-api-oauth'
FRAME_LIMIT = 16 * 1024 * 1024


class RpcError(RuntimeError):
    pass


class Client:
    def __init__(self, endpoint=None):
        self.endpoint = Path(endpoint or Path.home() / '.dimcode/rust/daemon.sock')
        self.sock = None
        self.stream = None
        self.sequence = 0

    def __enter__(self):
        parent = self.endpoint.parent.lstat()
        endpoint = self.endpoint.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
                or parent.st_mode & 0o077 or not stat.S_ISSOCK(endpoint.st_mode)
                or endpoint.st_uid != os.getuid() or endpoint.st_mode & 0o077):
            raise RpcError('Dim endpoint must be a private socket owned by this user')
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(40)
        try:
            self.sock.connect(str(self.endpoint))
            self.stream = self.sock.makefile('rb')
            hello = self.call('hello', {'protocolVersion': 3, 'clientKind': 'other', 'clientName': 'SumOS'})
            if hello['protocolVersion'] != 3:
                raise RpcError('Unsupported Dim protocol version')
            self.features = hello.get('features', [])
            return self
        except Exception:
            self.close()
            raise

    def call(self, method, params):
        self.sequence += 1
        request = {'jsonrpc': '2.0', 'id': self.sequence, 'method': method, 'params': params}
        self.sock.sendall((json.dumps(request) + '\n').encode())
        deadline = time.monotonic() + 40
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Dim RPC timed out')
            self.sock.settimeout(remaining)
            line = self.stream.readline(FRAME_LIMIT + 1)
            if not line or len(line) > FRAME_LIMIT or not line.endswith(b'\n'):
                raise RpcError('Closed or oversized Dim RPC frame')
            reply = json.loads(line)
            if reply.get('jsonrpc') != '2.0':
                raise RpcError('Unsupported RPC envelope')
            if 'id' not in reply and 'method' in reply:
                continue
            if reply.get('id') != self.sequence:
                raise RpcError('Unexpected RPC response identity')
            if 'error' in reply:
                raise RpcError(reply['error']['message'])
            return reply['result']

    def close(self):
        if self.stream:
            self.stream.close()
        if self.sock:
            self.sock.close()

    def __exit__(self, *_):
        self.close()
