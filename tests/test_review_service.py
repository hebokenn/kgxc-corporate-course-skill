"""The actual lifecycle entry must identify and reuse the current service build."""
from contextlib import redirect_stdout
from pathlib import Path
import io
import os
import signal
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from authoring import init_project
from workflow import Course,open_course,local_json,read,service_build

class ReviewServiceTests(unittest.TestCase):
    def test_lifecycle_service_reports_its_build_and_is_reused_without_duplicate_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();init_project(root/'project',ROOT/'skills/corporate-training-motion');Course(root).init('服务复用技术夹具');pid=None
            try:
                with redirect_stdout(io.StringIO()):first=open_course(root,open_browser=False)
                identity=local_json(first+'/api/identity');pid=identity['pid']
                self.assertEqual(identity['runtime_build'],service_build())
                with redirect_stdout(io.StringIO()):second=open_course(root,open_browser=False)
                self.assertEqual(first,second);self.assertEqual(local_json(second+'/api/identity')['pid'],pid)
                self.assertEqual(read(root/'project/work/workbench-service.json')['runtime_build'],service_build())
            finally:
                if pid:
                    try:os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError:pass

if __name__=='__main__':unittest.main()
