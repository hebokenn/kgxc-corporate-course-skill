"""Deterministic completion, export, unsaved edit and HTTP shutdown regressions."""
import http.server
import json
import os
from pathlib import Path
import sys
import socket
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workbench'))
from backend import atomic
from lifecycle import Handler, Lifecycle


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.p = self.root/'project'
        self.p.mkdir()
        self.space = SimpleNamespace(root=self.root, project=self.p, work=self.p/'work/workbench', jobs={})
        self.now = 0
        self.generation = 0
        self.state = 'complete'
        self.calls = 0
        self.life = Lifecycle(self.space, idle_seconds=120, clock=lambda: self.now)
        self.life.token = lambda: self.generation
        self.life.load_status = self.load_status

    def tearDown(self):
        self.temp.cleanup()

    def load_status(self):
        self.calls += 1
        return dict(stage=self.state)

    def tick(self, at):
        self.now = at
        return self.life.tick()

    def test_completed_closes_and_unchanged_metadata_never_revalidates(self):
        self.assertFalse(self.tick(0))
        for second in range(1, 120):
            self.assertFalse(self.tick(second))
        self.assertTrue(self.tick(120))
        self.assertEqual(self.calls, 1)
        self.assertFalse(self.life.begin_request())

    def test_polling_does_not_extend_idle_and_inflight_request_finishes(self):
        self.tick(0)
        for second in range(1, 121):
            self.now = second
            self.assertTrue(self.life.begin_request())
            self.assertFalse(self.life.tick())
            self.life.end_request()
        self.assertTrue(self.life.tick())

    def test_incomplete_and_changed_course_stay_open(self):
        self.state = 'final'
        self.tick(0)
        self.assertFalse(self.tick(1000))
        self.state = 'complete'
        self.generation += 1
        self.assertFalse(self.tick(1001))
        self.state = 'script'
        self.generation += 1
        self.assertFalse(self.tick(1200))
        self.assertFalse(self.tick(2000))
        self.assertEqual(self.calls, 3)

    def test_export_stays_alive_through_encoding_packaging_and_result_write(self):
        self.tick(0)
        job = dict(id='abc123456789', status='queued')
        self.space.jobs[job['id']] = job
        for second, phase in [(120, 'queued'), (300, 'rendering'), (500, 'encoding'), (700, 'packaging'), (900, 'complete')]:
            job['status'] = phase
            self.assertFalse(self.tick(second), phase)
        atomic(self.space.work/'exports'/job['id']/'result.json', job)
        self.assertFalse(self.tick(1000))
        self.assertFalse(self.tick(1119))
        self.assertTrue(self.tick(1120))

    def test_dirty_pages_and_playback_hold_service_then_release(self):
        self.tick(0)
        for now in range(30, 301, 30):
            self.now = now
            self.life.activity(dict(client_id='edit-page', dirty=True))
            self.assertFalse(self.life.tick())
        self.now = 301
        self.life.activity(dict(client_id='edit-page', dirty=False))
        self.life.activity(dict(client_id='watch-page', playing=True))
        self.assertFalse(self.tick(350))
        self.now = 351
        self.life.activity(dict(client_id='watch-page', playing=False))
        self.assertFalse(self.tick(351))
        self.assertFalse(self.tick(470))
        self.assertTrue(self.tick(471))

    def test_closed_page_lease_expires_and_navigation_extends_idle(self):
        self.tick(0)
        self.life.activity(dict(client_id='lost-tab', dirty=True))
        self.assertFalse(self.tick(89))
        self.assertFalse(self.tick(90))
        self.now = 200
        self.life.begin_request(meaningful=True)
        self.life.end_request(meaningful=True)
        self.assertFalse(self.tick(319))
        self.assertTrue(self.tick(320))

    def test_failed_or_racing_completion_check_never_closes(self):
        self.life.load_status = mock.Mock(side_effect=ValueError('incomplete write'))
        self.assertFalse(self.tick(0))
        self.assertFalse(self.tick(500))
        self.life.load_status = lambda: (setattr(self, 'generation', self.generation+1) or dict(stage='complete'))
        self.assertFalse(self.tick(1000))
        self.assertFalse(self.life.complete)

    def test_http_activity_and_shutdown_race_reject_new_export(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.workspace = self.space
        server.lifecycle = self.life
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:'+str(server.server_port)
        try:
            payload=json.dumps(dict(client_id='page', dirty=True, active=True)).encode()
            with urllib.request.urlopen(urllib.request.Request(url+'/api/activity', data=payload), timeout=3) as response:
                self.assertEqual(response.status, 200)
            self.assertIn('page', self.life.clients)
            self.life.stopping = True
            with urllib.request.urlopen(url+'/api/service', timeout=3) as response:
                self.fail('new requests must not enter after shutdown begins')
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 503)
            error.close()
            with mock.patch('backend.Workspace.start_export', side_effect=AssertionError('export entered while stopping')):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(urllib.request.Request(url+'/api/export', data=b'{}'), timeout=3)
                self.assertEqual(denied.exception.code, 503)
                denied.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


class ProcessTests(unittest.TestCase):
    def test_completed_process_exits_despite_polling_and_launcher_reopens(self):
        from scaffold import create
        from test_branch_workflow import design, approve_script
        from workflow import Course
        app = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            course = root/'course'
            create(course)
            current = Course(course)
            current.init('Automatic shutdown test fixture')
            design(current)
            approve_script(current)
            current.select_branch('courseware', current.status()['revision'], 'automated fixture request')
            deck = course/'delivery/courseware/test.html'
            deck.parent.mkdir(parents=True, exist_ok=True)
            deck.write_text('<html><h1>Technical test fixture</h1></html>')
            self.assertEqual(current.register('courseware', ['../delivery/courseware/test.html'], current.status()['revision'])['stage'], 'complete')
            state_bytes = current.state_file.read_bytes()
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            code = 'import sys;sys.path.append(sys.argv[1]+"/scripts");sys.path.insert(0,sys.argv[1]+"/workbench");from lifecycle import serve;serve(sys.argv[2],idle_seconds=.5,check_seconds=.05)'
            with (root/'server.log').open('w') as log:
                process = subprocess.Popen([sys.executable, '-c', code, str(app), str(course)], stdout=log, stderr=log, env=env)
                try:
                    record = course/'project/work/workbench-service.json'
                    deadline = time.monotonic()+6
                    while not record.exists() and time.monotonic()<deadline and process.poll() is None:
                        time.sleep(.02)
                    self.assertTrue(record.is_file(), (root/'server.log').read_text())
                    service = json.loads(record.read_text())
                    self.assertEqual(service['lifecycle_policy'], 'completed-idle/1')
                    polls = 0
                    while process.poll() is None and time.monotonic()<deadline:
                        try:
                            with urllib.request.urlopen(service['url']+'/api/workflow', timeout=1) as response:
                                self.assertEqual(json.load(response)['stage'], 'complete')
                                polls += 1
                        except urllib.error.HTTPError as error:
                            error.close()
                        except (OSError, urllib.error.URLError):
                            pass
                        time.sleep(.03)
                    self.assertEqual(process.wait(timeout=2), 0)
                    self.assertGreater(polls, 1)
                    receipt = json.loads((course/'project/work/workbench-last-shutdown.json').read_text())
                    self.assertEqual(receipt['reason'], 'completed_idle')
                    self.assertEqual(current.state_file.read_bytes(), state_bytes)
                    with socket.socket() as sock:
                        self.assertNotEqual(sock.connect_ex(('127.0.0.1', int(service['url'].rsplit(':', 1)[1]))), 0)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=3)
            with (root/'reopen.log').open('w') as log:
                reopened = subprocess.Popen([sys.executable, str(app/'scripts/workbench.py'), 'serve', str(course)], stdout=log, stderr=log, env=env)
                try:
                    deadline = time.monotonic()+6
                    while time.monotonic()<deadline:
                        service = json.loads(record.read_text())
                        if service['pid'] == reopened.pid:
                            break
                        time.sleep(.02)
                    self.assertEqual(service['pid'], reopened.pid)
                    with urllib.request.urlopen(service['url']+'/api/identity', timeout=2) as response:
                        self.assertEqual(json.load(response)['lifecycle_policy'], 'completed-idle/1')
                    self.assertIsNone(reopened.poll())
                finally:
                    reopened.terminate()
                    reopened.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
