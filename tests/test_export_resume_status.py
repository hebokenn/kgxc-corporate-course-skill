from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'))
from backend import Workspace
from workflow import atomic

class ExportResumeStatus(unittest.TestCase):
    def test_persisted_interruption_is_resumable_but_live_and_completed_jobs_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); job_id='abcdef012345'; out=root/'exports'/job_id; out.mkdir(parents=True)
            space=SimpleNamespace(work=root,project=root,jobs={})
            receipt=dict(id=job_id,purpose='pilot',status='queued',revision=4)
            atomic(out/'started.json',receipt)
            with patch('render_input_guard.active',return_value=[]):
                interrupted=Workspace.job(space,job_id)
            self.assertEqual(interrupted['status'],'cancelled')
            self.assertEqual(interrupted['purpose'],'pilot')
            self.assertTrue(interrupted['files_retained'])
            with patch('render_input_guard.active',return_value=[{'render_id':job_id}]):
                self.assertEqual(Workspace.job(space,job_id)['status'],'rendering')
            atomic(out/'result.json',dict(receipt,status='complete'))
            self.assertEqual(Workspace.job(space,job_id)['status'],'complete')

if __name__=='__main__':unittest.main()
