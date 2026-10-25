"""Stop a completed course service after genuine inactivity, never during export.

Kept separate from the frozen renderer/backend fingerprint so upgrading service
management does not invalidate an already reviewed course.
"""
import http.server
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.parse

import backend

POLICY = 'completed-idle/1'
IDLE_SECONDS = 120
CHECK_SECONDS = 5


class Lifecycle:
    def __init__(self, workspace, idle_seconds=IDLE_SECONDS, clock=time.monotonic):
        self.space = workspace
        self.idle_seconds = idle_seconds
        self.clock = clock
        self.guard = threading.RLock()
        self.last_activity = clock()
        self.complete = False
        self.checked_token = None
        self.requests = 0
        self.clients = {}
        self.stopping = False
        self.was_busy = False
        self.last_error = None

    def token(self):
        p = self.space.project
        files = [p/name for name in ['course-state.json', 'workbench.json', 'design-plan.json', 'director-plan.json', 'motion-contract.json', 'craft-contract.json']]
        # Metadata only. Never read video/audio bytes or launch FFmpeg on a poll.
        for folder in [self.space.root/'inputs', *(p/name for name in ['native', 'assets', 'audio', 'media', 'source', 'qa']), backend.APP]:
            files.extend(f for f in folder.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
        state = backend.read(p/'course-state.json') if (p/'course-state.json').is_file() else {}
        for paths in state.get('artifacts', {}).values():
            for name in paths:
                f = (p/name).resolve()
                if f.is_relative_to(self.space.root):
                    files.append(f)
        result = []
        for f in sorted(set(files)):
            try:
                st = f.stat()
                result.append((str(f), st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns))
            except FileNotFoundError:
                result.append((str(f), None))
        return tuple(result)

    def load_status(self):
        from workflow import Course
        return Course(self.space.root).status()

    def exporting(self):
        for job in list(self.space.jobs.values()):
            if job.get('status') not in ['complete', 'failed', 'missing']:
                return True
            # A worker sets its in-memory terminal status just before persisting
            # result.json. Keep it alive until that final write has completed.
            result = self.space.work/'exports'/job['id']/'result.json'
            try:
                if backend.read(result).get('status') != job['status']:
                    return True
            except (OSError, ValueError):
                return True
        return False

    def begin_request(self, meaningful=False):
        with self.guard:
            if self.stopping:
                return False
            self.requests += 1
            if meaningful:
                self.last_activity = self.clock()
            return True

    def end_request(self, meaningful=False):
        with self.guard:
            self.requests -= 1
            if meaningful:
                self.last_activity = self.clock()

    def activity(self, data):
        client = data.get('client_id', '')
        if not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', client):
            raise ValueError('页面会话标识无效')
        if any(type(data.get(k, False)) is not bool for k in ['dirty', 'playing', 'active']):
            raise ValueError('页面活动状态无效')
        with self.guard:
            now = self.clock()
            if data.get('active') or client in self.clients:
                self.last_activity = now
            if data.get('dirty') or data.get('playing'):
                self.clients[client] = now + 90
            else:
                self.clients.pop(client, None)

    def tick(self):
        """Return True only after atomically refusing new work at shutdown."""
        try:
            token = self.token()
            if token != self.checked_token:
                with self.guard:
                    self.complete = False
                status = self.load_status()
                if token != self.token():
                    return False
                with self.guard:
                    self.complete = status.get('stage') == 'complete'
                    self.checked_token = token
                    self.last_activity = self.clock()
                    self.last_error = None
        except (OSError, ValueError, KeyError) as exc:
            with self.guard:
                self.complete = False
                self.checked_token = None
                self.last_error = str(exc)
            return False
        # Export enqueueing uses the same backend lock. A request that has
        # already entered also holds a lifecycle reference until it finishes.
        with backend.LOCK, self.guard:
            now = self.clock()
            self.clients = {key: expiry for key, expiry in self.clients.items() if expiry > now}
            busy = self.exporting() or bool(self.clients)
            if busy or self.was_busy:
                self.last_activity = now
            self.was_busy = busy
            if not busy and self.requests == 0 and self.complete and now-self.last_activity >= self.idle_seconds:
                self.stopping = True
                return True
            return False

    def snapshot(self):
        with self.guard:
            return dict(policy=POLICY, completed=self.complete, idle_seconds=self.idle_seconds,
                        stopping=self.stopping, reason='completed_idle' if self.stopping else None)


class Handler(backend.Handler):
    def json(self, value, status=200):
        if isinstance(value, dict) and 'course_root' in value and 'pid' in value:
            value = dict(value, lifecycle_policy=POLICY)
        return super().json(value, status)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        life = self.server.lifecycle
        meaningful = path in ['/', '/index.html', '/edit.html', '/course-file'] or path.startswith('/download/')
        if not life.begin_request(meaningful):
            return self.json(dict(error='课程已完成，工作台正在自动关闭；需要时从课程目录重新打开'), 503)
        try:
            if path == '/api/service':
                return self.json(life.snapshot())
            return super().do_GET()
        finally:
            life.end_request(meaningful)

    def do_POST(self):
        life = self.server.lifecycle
        path = urllib.parse.urlparse(self.path).path
        meaningful = path != '/api/activity'
        if not life.begin_request(meaningful):
            return self.json(dict(error='工作台正在自动关闭，请重新打开后操作'), 503)
        try:
            if path != '/api/activity':
                return super().do_POST()
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host', ''):
                raise ValueError('仅允许当前本地工作台修改')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2048:
                raise ValueError('页面活动请求大小无效')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('页面活动请求无效')
            life.activity(data)
            return self.json(life.snapshot())
        except (ValueError, TypeError) as exc:
            return self.json(dict(error=str(exc)), 400)
        finally:
            life.end_request(meaningful)


def serve(root, port=0, idle_seconds=IDLE_SECONDS, check_seconds=CHECK_SECONDS):
    http.server.ThreadingHTTPServer.request_queue_size = 128
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.workspace = backend.Workspace(root)
    server.lifecycle = Lifecycle(server.workspace, idle_seconds)
    url = 'http://127.0.0.1:'+str(server.server_port)
    if (server.workspace.project/'course-state.json').is_file():
        from workflow import VERSION
        backend.atomic(server.workspace.project/'work/workbench-service.json',
                       dict(pid=os.getpid(), version=VERSION, url=url, lifecycle_policy=POLICY))
    stopped = threading.Event()

    def monitor():
        while not stopped.wait(check_seconds):
            if server.lifecycle.tick():
                server.shutdown()
                return

    watcher = threading.Thread(target=monitor, name='course-idle-shutdown', daemon=True)
    watcher.start()
    print('WORKBENCH_URL='+url, flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        server.server_close()
        if server.lifecycle.stopping:
            backend.atomic(server.workspace.project/'work/workbench-last-shutdown.json',
                           dict(pid=os.getpid(), url=url, reason='completed_idle', idle_seconds=idle_seconds))
            print('WORKBENCH_STOPPED=completed_idle', flush=True)
