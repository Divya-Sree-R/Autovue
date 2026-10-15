"""Check that public activation cannot precede owner consent and app checks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deploy import local_app
from deploy.tailscale_funnel import Funnel, FunnelError


class FunnelControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.funnel = Funnel(self.directory)
        self.node = {'node_id': 'node-test', 'host': 'autovue-review.test.ts.net',
                     'url': 'https://autovue-review.test.ts.net', 'port': 8080,
                     'target': 'http://127.0.0.1:8080'}

    def test_no_owner_permission_does_not_start_daemon_or_app(self):
        with patch.object(self.funnel, 'prepare') as prepare, patch.object(self.funnel, 'command') as command:
            with self.assertRaisesRegex(FunnelError, 'Laptop-owner permission'):
                self.funnel.start()
        prepare.assert_not_called()
        command.assert_not_called()

    def test_public_start_records_explicit_consent_after_local_checks(self):
        result = Mock(returncode=0, stdout='', stderr='')
        with patch.object(self.funnel, 'prepare', return_value=self.node) as prepare, \
             patch.object(self.funnel, 'command', return_value=result) as command:
            self.funnel.start(owner_approved=True)
        prepare.assert_called_once()
        self.assertEqual(self.funnel.read_json('owner-approval.json')['node_id'], 'node-test')
        self.assertEqual(self.funnel.read_json('public.json'), self.node)
        command.assert_called_once_with('funnel', '--bg', '--https=443', '--set-path=/',
                                        'http://127.0.0.1:8080', check=False, timeout=45)

    def test_local_check_failure_never_records_consent_or_starts_funnel(self):
        with patch.object(self.funnel, 'prepare', side_effect=FunnelError('unsafe app')), \
             patch.object(self.funnel, 'command') as command:
            with self.assertRaisesRegex(FunnelError, 'unsafe app'):
                self.funnel.start(owner_approved=True)
        command.assert_not_called()
        self.assertIsNone(self.funnel.read_json('owner-approval.json'))

    def test_changed_node_requires_fresh_owner_consent(self):
        self.funnel.write_json('owner-approval.json', {'node_id': 'different',
                               'host': self.node['host'], 'port': 8080})
        self.funnel.write_json('prepared.json', self.node)
        with patch.object(self.funnel, 'prepare', return_value=self.node), \
             patch.object(self.funnel, 'command') as command:
            with self.assertRaisesRegex(FunnelError, 'fresh laptop-owner approval'):
                self.funnel.start()
        command.assert_not_called()

    def test_saved_tunnel_checks_local_auth_before_restarting_daemon(self):
        self.funnel.write_json('prepared.json', self.node)
        self.funnel.write_json('owner-approval.json', self.node)
        events = []
        with patch.object(self.funnel, 'prepare_app', side_effect=lambda node: events.append('auth')), \
             patch.object(self.funnel, 'prepare', side_effect=lambda: events.append('daemon') or self.node), \
             patch.object(self.funnel, 'command', return_value=Mock(returncode=0, stdout='', stderr='')):
            self.funnel.start()
        self.assertEqual(events, ['auth', 'daemon'])

    def test_private_restart_cannot_resume_saved_public_configuration(self):
        self.funnel.binary.parent.mkdir()
        self.funnel.binary.touch()
        self.funnel.daemon_binary.touch()
        self.funnel.write_json('owner-approval.json', self.node)
        with patch('subprocess.Popen') as spawn:
            with self.assertRaisesRegex(FunnelError, 'Saved public history'):
                self.funnel.ensure_daemon()
        spawn.assert_not_called()

    def test_nonrunning_or_invalid_hostname_cannot_be_published(self):
        for value in ({'BackendState': 'NeedsLogin'},
                      {'BackendState': 'Running', 'Self': {'DNSName': 'evil.example'}}):
            with patch.object(self.funnel, 'command', return_value=Mock(stdout=json.dumps(value))):
                with self.assertRaises(FunnelError):
                    self.funnel.node()

    def test_restarted_logged_in_daemon_waits_for_control_connection(self):
        starting = Mock(stdout=json.dumps({'BackendState': 'Starting'}))
        running = Mock(stdout=json.dumps({'BackendState': 'Running',
                         'Self': {'ID': self.node['node_id'], 'DNSName': self.node['host'] + '.'}}))
        with patch.object(self.funnel, 'command', side_effect=[starting, running]), patch('time.sleep'):
            self.assertEqual(self.funnel.node(), self.node)

    def test_stop_removes_only_owned_root_handler_and_preserves_files(self):
        daemon = {'process': {'pid': 12345}}
        self.funnel.write_json('tailscaled.json', daemon)
        with patch.object(self.funnel, 'daemon_owned', return_value=True), \
             patch.object(self.funnel, 'command', return_value=Mock(returncode=0, stdout='{"AllowFunnel": {"test:443": true}}')) as command, \
             patch.object(local_app, 'stop') as stop, patch('os.killpg') as kill:
            self.funnel.stop()
        self.assertEqual(command.call_count, 2)
        command.assert_called_with('funnel', '--bg', '--https=443', '--set-path=/',
                                   'http://127.0.0.1:8080', 'off', check=False)
        stop.assert_called_once_with(self.directory, force=False)
        kill.assert_called_once()
        self.assertTrue((self.directory / 'tailscaled.json').exists())

    def test_failure_to_disable_funnel_disconnects_and_blocks_private_restart(self):
        self.funnel.write_json('tailscaled.json', {'process': {'pid': 12345}})
        with patch.object(self.funnel, 'daemon_owned', return_value=True), \
             patch.object(self.funnel, 'command', side_effect=FunnelError('offline')), \
             patch.object(local_app, 'stop') as stop, patch('os.killpg') as kill:
            with self.assertRaisesRegex(FunnelError, 'Public access was disconnected'):
                self.funnel.stop()
        stop.assert_called_once()
        kill.assert_called_once()
        self.assertTrue(self.funnel.read_json('unclean-stop.json'))

    def test_never_enabled_funnel_stop_does_not_request_feature_approval(self):
        self.funnel.write_json('tailscaled.json', {'process': {'pid': 12345}})
        with patch.object(self.funnel, 'daemon_owned', return_value=True), \
             patch.object(self.funnel, 'command', return_value=Mock(stdout='{}')) as command, \
             patch.object(local_app, 'stop'), patch('os.killpg'):
            self.funnel.stop()
        command.assert_called_once_with('funnel', 'status', '--json')

    def test_daemon_start_waits_for_exec_identity_before_recording(self):
        self.funnel.binary.parent.mkdir()
        self.funnel.binary.touch()
        self.funnel.daemon_binary.touch()
        self.funnel.tsdir.mkdir()
        self.funnel.socket.touch()
        child = Mock(pid=12345)
        child.poll.return_value = None
        identity = {'pid': 12345}
        with patch('subprocess.Popen', return_value=child), \
             patch.object(local_app, 'process_identity', side_effect=[None, identity]), \
             patch.object(self.funnel, 'daemon_owned', side_effect=[False, True, True]), \
             patch('time.sleep'):
            self.funnel.ensure_daemon()
        self.assertEqual(self.funnel.read_json('tailscaled.json'), {'process': identity})
        child.terminate.assert_not_called()

    def test_unidentifiable_spawned_child_is_terminated(self):
        self.funnel.binary.parent.mkdir()
        self.funnel.binary.touch()
        self.funnel.daemon_binary.touch()
        child = Mock(pid=12345)
        child.poll.return_value = None
        with patch('subprocess.Popen', return_value=child), \
             patch.object(local_app, 'process_identity', return_value=None), \
             patch.object(self.funnel, 'daemon_owned', return_value=False), patch('time.sleep'):
            with self.assertRaisesRegex(FunnelError, 'Could not identify'):
                self.funnel.ensure_daemon()
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=10)
        self.assertIsNone(self.funnel.read_json('tailscaled.json'))


if __name__ == '__main__':
    unittest.main()
