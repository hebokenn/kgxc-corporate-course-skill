"""A persisted supervision hold stops the owned render, preserving its evidence."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from backend import Workspace,ProductionHeld,stop_export_process,owned_export_process


class ProductionHoldTests(unittest.TestCase):
    def test_hold_stops_only_its_real_process_group_and_retains_files(self):
        with tempfile.TemporaryDirectory(prefix='kgxc-hold-') as folder:
            project=Path(folder);space=Workspace.__new__(Workspace);space.project=project
            source=project/'original.wav';source.write_bytes(b'original bytes retained')
            partial=project/'partial.mp4';partial.write_bytes(b'partial render retained')
            child='import signal,sys,time;from pathlib import Path;signal.signal(signal.SIGTERM,lambda *_:(Path(sys.argv[1]).write_text("stopped"),sys.exit(0)));Path(sys.argv[2]).touch();time.sleep(30)'
            parent='import signal,sys,time,subprocess;from pathlib import Path;signal.signal(signal.SIGTERM,lambda *_:(Path(sys.argv[1]).write_text("stopped"),sys.exit(0)));subprocess.Popen([sys.executable,"-c",sys.argv[2],sys.argv[3],sys.argv[4]]);time.sleep(30)'
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
            process=subprocess.Popen([sys.executable,'-c',parent,str(project/'parent-stopped'),child,str(project/'child-stopped'),str(project/'child-ready')],start_new_session=True)
            try:
                deadline=time.monotonic()+4
                while time.monotonic()<deadline and not (project/'child-ready').exists():time.sleep(.02)
                self.assertTrue((project/'child-ready').exists())
                space.require_production_active(process);self.assertIsNone(process.poll())
                (project/'ai-review.json').write_text(json.dumps(dict(hold=dict(held=True,reason='独立监督发现权限越界',source='supervisor'))))
                with self.assertRaisesRegex(ProductionHeld,'权限越界'):space.require_production_active(process)
                self.assertIsNotNone(process.poll());self.assertIsNone(unrelated.poll())
                deadline=time.monotonic()+2
                while time.monotonic()<deadline and not (project/'child-stopped').exists():time.sleep(.02)
                self.assertTrue((project/'child-stopped').exists())
                self.assertTrue((project/'parent-stopped').exists())
                self.assertEqual(source.read_bytes(),b'original bytes retained')
                self.assertEqual(partial.read_bytes(),b'partial render retained')
                with self.assertRaises(ProductionHeld):space.start_export(1,0,1,'http://127.0.0.1')
                self.assertFalse((project/'work/exports').exists())
            finally:
                if process.poll() is None:stop_export_process(process)
                unrelated.terminate();unrelated.wait(timeout=3)

    def test_stop_refuses_a_process_without_an_owned_group(self):
        process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        try:
            self.assertNotEqual(os.getpgid(process.pid),process.pid)
            with self.assertRaisesRegex(ValueError,'独立进程组'):stop_export_process(process)
            self.assertIsNone(process.poll())
        finally:process.terminate();process.wait(timeout=3)

    def test_stop_drains_a_stubborn_child_after_its_leader_has_exited(self):
        with tempfile.TemporaryDirectory(prefix='kgxc-stubborn-child-') as folder:
            ready=Path(folder)/'child-pid'
            child='import signal,sys,time,os;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)'
            parent='import subprocess,sys,time;from pathlib import Path;subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]);exec("while not Path(sys.argv[2]).exists():time.sleep(.01)")'
            process=owned_export_process([sys.executable,'-c',parent,child,str(ready)])
            try:
                process.wait(timeout=4);self.assertEqual(process.returncode,0)
                pid=int(ready.read_text());stop_export_process(process)
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
                    if not state or state.startswith('Z'):break
                    time.sleep(.02)
                self.assertTrue(not state or state.startswith('Z'),state)
            finally:stop_export_process(process)

    def test_actual_export_loop_observes_hold_and_never_registers_partial_media(self):
        sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/scripts'))
        from test_new_course_workbench import NewCourseTests
        fixture=NewCourseTests();fixture.setUp()
        try:
            doc=fixture.ready();space=Workspace(fixture.course)
            shim=fixture.course/'test-render-runtime';shim.mkdir()
            (shim/'render_worker.py').write_text('import sys,time\nfrom pathlib import Path\nd=Path(sys.argv[sys.argv.index("--directory")+1]);(d/"video.mp4").write_bytes(b"partial-owned-render");(d/"ready").touch();time.sleep(30)\n')
            with patch('backend.APP',shim):
                job=space.start_export(doc['revision'],0,1,'http://127.0.0.1:1',purpose='pilot')
                directory=space.work/'exports'/job['id'];deadline=time.monotonic()+5
                while time.monotonic()<deadline and not (directory/'ready').exists() and job['status'] not in ['failed','complete']:time.sleep(.02)
                self.assertTrue((directory/'ready').exists(),job)
                (fixture.p/'ai-review.json').write_text(json.dumps(dict(hold=dict(held=True,reason='合成执行监督暂停'))))
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and job['status'] not in ['cancelled','failed','complete']:time.sleep(.02)
                self.assertEqual(job['status'],'cancelled',job)
                self.assertEqual(json.loads((directory/'result.json').read_text())['status'],'cancelled')
                self.assertEqual((directory/'video.mp4').read_bytes(),b'partial-owned-render')
                self.assertTrue((directory/'execution.json').exists())
                self.assertEqual(list((fixture.course/'delivery').glob('*.mp4')),[])
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
