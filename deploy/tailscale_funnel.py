#!/usr/bin/env python3
"""Manage the free, user-owned WSL Funnel; public activation requires consent.

    python3 deploy/tailscale_funnel.py login
    python3 deploy/tailscale_funnel.py prepare
    python3 deploy/tailscale_funnel.py start --owner-approved
    python3 deploy/tailscale_funnel.py status
    python3 deploy/tailscale_funnel.py stop

Login/prepare never configure Serve or Funnel. The app binds only WSL loopback.
Keep all state in ignored app_data/funnel, including device keys and credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy import local_app

VERSION = '1.104.1'
ARCHIVE_SHA256 = '108d1d96ecf410d305571e173516f27038f870919a9b89c914a167c6d33a4528'
DEFAULT_STATE = ROOT / 'app_data/funnel'


class FunnelError(RuntimeError):
    pass


class Funnel:
    def __init__(self, directory: Path = DEFAULT_STATE, port: int = 8080):
        self.directory = directory.expanduser().absolute()
        self.tsdir = self.directory / 'tailscale'
        self.binary = self.directory / 'bin/tailscale'
        self.daemon_binary = self.directory / 'bin/tailscaled'
        self.socket = self.tsdir / 'tailscaled.sock'
        self.port = port
        self.target = f'http://127.0.0.1:{port}'
        self.public_start_intent = False
        if len(str(self.socket).encode()) > 103:
            raise FunnelError('Runtime directory is too long for a Unix socket.')

    def command(self, *args, timeout=30, check=True):
        try:
            result = subprocess.run(
                [str(self.binary), '--socket=' + str(self.socket), *args],
                text=True, capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            # Feature enablement can wait for an account-owner web approval.
            # Preserve that URL so the caller can complete the provider step.
            output = exc.stdout or exc.stderr or ''
            if isinstance(output, bytes):
                output = output.decode(errors='replace')
            raise FunnelError(f'Tailscale command timed out. {output.strip()}') from None
        if check and result.returncode:
            raise FunnelError((result.stderr or result.stdout).strip())
        return result

    def read_json(self, name):
        try:
            return json.loads(local_app.secure_read(self.directory / name))
        except FileNotFoundError:
            return None

    def write_json(self, name, value):
        local_app.private_write(self.directory / name, json.dumps(value, indent=2) + '\n')

    def daemon_owned(self, state):
        if not state:
            return False
        expected = state.get('process', {})
        current = local_app.process_identity(expected.get('pid'))
        return bool(current and current == expected and current['uid'] == os.getuid()
                    and current['session'] == current['pid'] == current['process_group']
                    and current['command'][0] == str(self.daemon_binary)
                    and '--socket=' + str(self.socket) in current['command'])

    def ensure_daemon(self):
        local_app.private_directory(self.directory)
        local_app.private_directory(self.tsdir)
        if not self.binary.is_file() or not self.daemon_binary.is_file():
            raise FunnelError('Install the verified static Tailscale binaries first; see docs/tailscale-deployment.md.')
        state = self.read_json('tailscaled.json')
        if self.daemon_owned(state):
            return
        if not self.public_start_intent and any(self.read_json(name) for name in
                ('unclean-stop.json', 'public.json', 'owner-approval.json')):
            raise FunnelError('Saved public history requires an authenticated start before daemon restart. '
                              'Use start; private prepare/login will not resume a saved Funnel.')
        if state and local_app.process_identity(state['process'].get('pid')):
            raise FunnelError('Daemon PID was reused; refusing to replace an unidentified process.')
        # A previous public configuration might resume on daemon restart. Never
        # restart a daemon with such history without its existing owner consent.
        if self.read_json('public.json') and not self.read_json('owner-approval.json'):
            raise FunnelError('Public state exists without owner consent; refusing automatic daemon restart.')
        descriptor = os.open(self.directory / 'tailscaled.log',
                             os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'a') as log:
            os.fchmod(log.fileno(), 0o600)
            process = subprocess.Popen([
                str(self.daemon_binary), '--tun=userspace-networking',
                '--statedir=' + str(self.tsdir), '--state=' + str(self.tsdir / 'tailscaled.state'),
                '--socket=' + str(self.socket), '--port=0',
            ], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        # /proc can briefly expose the parent's command line before exec has
        # settled. Capture only the stable, verified child identity.
        state = None
        for _ in range(100):
            if process.poll() is not None:
                break
            candidate = {'process': local_app.process_identity(process.pid)}
            if candidate['process'] and self.daemon_owned(candidate):
                state = candidate
                break
            time.sleep(.05)
        if state is None:
            # This Popen handle still identifies our child, even without a
            # durable /proc identity. Never leave an unmanaged daemon behind.
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            raise FunnelError('Could not identify the private Tailscale daemon.')
        self.write_json('tailscaled.json', state)
        for _ in range(100):
            if not self.daemon_owned(state):
                break
            if self.socket.exists():
                return
            time.sleep(.1)
        raise FunnelError('Tailscale daemon did not start; inspect app_data/funnel/tailscaled.log.')

    def node(self):
        for attempt in range(51):
            result = self.command('status', '--json', check=False)
            try:
                node = json.loads(result.stdout)
            except ValueError:
                raise FunnelError('Tailscale status is unavailable; run the login command.') from None
            if node.get('BackendState') not in {'Starting', 'NoState'} or attempt == 50:
                break
            # A restarted, authenticated daemon needs time to reconnect. This
            # transient state does not require the user to log in again.
            time.sleep(.2)
        if node.get('BackendState') != 'Running':
            raise FunnelError('Tailscale is not logged in; run the login command.')
        own = node.get('Self') or {}
        host = own.get('DNSName', '').rstrip('.').lower()
        if not re.fullmatch(r'[a-z0-9-]+\.[a-z0-9-]+\.ts\.net', host):
            raise FunnelError('A valid MagicDNS *.ts.net hostname is required.')
        if own.get('KeyExpiry') and own.get('Expired'):
            raise FunnelError('The Tailscale node key expired; log in again.')
        return {'node_id': own.get('ID'), 'host': host, 'url': 'https://' + host,
                'port': self.port, 'target': self.target}

    def login(self):
        self.ensure_daemon()
        # No routing, SSH, Serve, or Funnel is enabled by this login command.
        result = self.command('up', '--hostname=autovue-review', '--accept-dns=false',
                              '--accept-routes=false', '--ssh=false', '--timeout=60s',
                              check=False, timeout=75)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        if result.returncode:
            print('Complete the printed login URL using the free Personal plan, then run login again.')
            return 1
        node = self.node()
        print(f"Logged in as {node['host']}. Funnel remains unconfigured.")
        return 0

    def prepare(self):
        self.ensure_daemon()
        node = self.node()
        self.prepare_app(node)
        self.write_json('prepared.json', node)
        print(f"Prepared {self.target} with authentication and public safeguards; Funnel configuration unchanged.")
        return node

    def prepare_app(self, node):
        os.environ.update(AUTOVUE_PUBLIC_MODE='1', AUTOVUE_PUBLIC_HOST=node['host'],
                          AUTOVUE_PUBLIC_ORIGIN=node['url'],
                          AUTOVUE_REFERENCE_ANALYZED_VIDEO=str(ROOT / 'app_data/jobs/m25_reference/video/autovue_result.mp4'),
                          AUTOVUE_REFERENCE_PRESENTATION_VIDEO=str(ROOT / 'app_data/jobs/m25_reference/video/presentation.mp4'))
        with local_app.control_lock(self.directory):
            state = local_app.start(self.directory, port=self.port,
                                    jobs_root=self.directory / 'jobs')
        self.verify_auth(state, node)

    def verify_auth(self, state, expected_node):
        auth = local_app.read_auth(self.directory / 'auth.env')
        for path in ('/', '/api/jobs', '/api/reference/results', '/docs'):
            from urllib.request import ProxyHandler, build_opener
            try:
                with build_opener(ProxyHandler({})).open(state['url'] + path, timeout=5):
                    raise FunnelError('Authentication check failed: anonymous access was accepted.')
            except HTTPError as exc:
                if exc.code not in (401, 429):
                    raise FunnelError(f'Authentication check failed: HTTP {exc.code}.') from None
        local_app.request_json(state['url'] + '/api/jobs', auth)
        if state['public_configuration'] != {
            'AUTOVUE_PUBLIC_MODE': '1', 'AUTOVUE_PUBLIC_HOST': expected_node['host'],
            'AUTOVUE_PUBLIC_ORIGIN': expected_node['url'],
        }:
            raise FunnelError('The local process is not using the expected public safeguards.')

    def start(self, owner_approved=False):
        # Check the consent flag/receipt BEFORE starting any daemon or app.
        approval = self.read_json('owner-approval.json')
        if not owner_approved and not approval:
            raise FunnelError('Laptop-owner permission is required. No public endpoint was configured. '
                              'After obtaining it, run start --owner-approved.')
        saved_node = self.read_json('public.json') or self.read_json('prepared.json')
        if saved_node:
            if saved_node['port'] != self.port or saved_node['target'] != self.target:
                raise FunnelError('Saved Funnel target differs; preserve the existing port until its handler is safely removed.')
            if approval and not owner_approved and any(approval.get(key) != saved_node[key]
                                                       for key in ('node_id', 'host', 'port')):
                raise FunnelError('The device/URL/port changed; fresh laptop-owner approval is required.')
            # A detached Funnel may resume as soon as tailscaled starts. Verify
            # its exact loopback target BEFORE restarting a daemon with history.
            self.prepare_app(saved_node)
        elif approval:
            raise FunnelError('Saved node details are missing; refusing to resume an unidentified public target.')
        self.public_start_intent = True
        node = self.prepare()
        expected = {key: node[key] for key in ('node_id', 'host', 'port')}
        if owner_approved:
            self.write_json('owner-approval.json', {**expected, 'approved_at': time.time()})
        elif any(approval.get(key) != value for key, value in expected.items()):
            raise FunnelError('The device/URL/port changed; fresh laptop-owner approval is required.')
        result = self.command('funnel', '--bg', '--https=443', '--set-path=/', self.target,
                              check=False, timeout=45)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        if result.returncode:
            raise FunnelError('Funnel activation requires the account owner to complete the printed HTTPS/Funnel approval URL.')
        self.write_json('public.json', node)
        (self.directory / 'unclean-stop.json').unlink(missing_ok=True)
        print('Public AutoVue: ' + node['url'])
        print('Private reviewer login: ' + str(self.directory / 'auth.env'))

    def status(self):
        state = self.read_json('tailscaled.json')
        result = {'daemon_running': self.daemon_owned(state), 'public_configuration': self.read_json('public.json')}
        if result['daemon_running']:
            response = self.command('funnel', 'status', '--json', check=False)
            try:
                result['funnel'] = json.loads(response.stdout)
            except ValueError:
                result['funnel'] = response.stderr.strip()
        print(json.dumps(result, indent=2))
        local_app.status(self.directory)

    def stop(self, *, force=False):
        state = self.read_json('tailscaled.json')
        disable_failure = None
        if self.daemon_owned(state):
            # Remove only our HTTPS root handler; never reset unrelated config.
            try:
                current = json.loads(self.command('funnel', 'status', '--json').stdout)
                # Calling `off` on a never-enabled tailnet can itself wait for
                # provider feature approval. An empty config is already off.
                if current:
                    result = self.command('funnel', '--bg', '--https=443', '--set-path=/',
                                          self.target, 'off', check=False)
                    if result.returncode:
                        raise FunnelError(result.stderr.strip())
                print('Public Funnel is off.')
            except (FunnelError, ValueError, subprocess.TimeoutExpired) as exc:
                disable_failure = str(exc)
                self.write_json('unclean-stop.json', {'reason': disable_failure, 'at': time.time()})
            # Disconnect first, even if an active GPU job prevents app shutdown.
            # This also closes public connections if the local CLI was unhealthy.
            if self.daemon_owned(state):
                os.killpg(state['process']['pid'], signal.SIGTERM)
                print('Private Tailscale daemon stopped; public access is disconnected.')
        with local_app.control_lock(self.directory):
            local_app.stop(self.directory, force=force)
        if disable_failure:
            raise FunnelError('Public access was disconnected, but the saved Funnel configuration '
                              'could not be cleared; private restarts are blocked. ' + disable_failure)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--port', type=int, default=8080)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('login')
    sub.add_parser('prepare')
    begin = sub.add_parser('start')
    begin.add_argument('--owner-approved', action='store_true',
                       help='Record laptop-owner consent for this node, HTTPS hostname and app port')
    sub.add_parser('status')
    end = sub.add_parser('stop')
    end.add_argument('--force', action='store_true', help='Explicitly interrupt an active/unresponsive owned app')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    try:
        controller = Funnel(args.state_dir, args.port)
        if args.command == 'login':
            return controller.login()
        if args.command == 'start':
            controller.start(args.owner_approved)
        elif args.command == 'stop':
            controller.stop(force=args.force)
        elif args.command == 'prepare':
            controller.prepare()
        else:
            controller.status()
        return 0
    except (FunnelError, local_app.ControlError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'AutoVue Funnel: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
