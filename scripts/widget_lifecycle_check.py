"""Real Qt launcher/owned-server shutdown tests, with simulation only."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def check(signum):
    with tempfile.TemporaryDirectory(prefix='april-lifecycle-') as directory:
        root = Path(directory)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        config = root / 'settings.toml'
        config.write_text(f'port = {port}\n')
        environment = dict(os.environ)
        environment['APRIL_CONFIG'] = str(config)
        environment.setdefault('QT_QPA_PLATFORM', 'offscreen')
        log = root / 'simulation.log'
        with log.open('w') as output:
            process = subprocess.Popen(
                [sys.executable, '-m', 'april.launch', '--widget', '--simulation'],
                cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                url = f'http://127.0.0.1:{port}/health'
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError(log.read_text()[-1500:])
                    try:
                        if httpx.get(url, timeout=.2, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise AssertionError('Owned simulation server did not start')
                time.sleep(1)
                process.send_signal(signum)
                process.wait(timeout=10)
                if process.returncode != 0:
                    raise AssertionError(log.read_text()[-1500:])
                try:
                    httpx.get(url, timeout=.3, trust_env=False)
                except httpx.ConnectError:
                    pass
                else:
                    raise AssertionError('Owned server still listening after quit')
                print(f'Actual Qt simulation launcher: {signal.Signals(signum).name} exits cleanly and releases its server.')
            finally:
                if process.poll() is None:
                    # Only this fixture's newly created process group.
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


if __name__ == '__main__':
    check(signal.SIGTERM)
    check(signal.SIGINT)
