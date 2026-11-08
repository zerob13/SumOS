#!/usr/bin/python3
import argparse
import time
from rpc import Client

parser = argparse.ArgumentParser()
parser.add_argument('--wait', type=float, default=0)
args = parser.parse_args()
deadline = time.monotonic() + args.wait
while True:
    try:
        with Client() as client:
            response = client.call('daemon.ping', {})
            assert response['serverVersion']
        print('Dim RPC ready')
        break
    except (OSError, RuntimeError) as error:
        if time.monotonic() >= deadline:
            raise SystemExit(str(error))
        time.sleep(0.2)
