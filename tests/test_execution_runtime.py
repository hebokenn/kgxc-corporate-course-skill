"""Real local input locks, outbound packet checks and fail-closed CLI; no inference."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench')]
from workflow import Course,atomic,read
from render_input_guard import freeze_render,check_render,end_render,ensure_mutation_allowed
from review_preflight import require_clean,capability_matrix
from ai_review import Review
from test_execution_contract_requirements import obligation
from execution_requirements import update
from production import dispatch,require_dispatch_return

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.p=self.root/'project';self.p.mkdir()
        self.doc=self.p/'workbench.json';atomic(self.doc,dict(media={},assets=[],sourceDurationFrames=24,sceneGraph=dict(nodes=[])))
        self.course=Course(self.root);self.course.init('Synthetic runtime only')
    def tearDown(self):self.tmp.cleanup()
    def test_real_frozen_bytes_detect_external_edit_and_keep_record(self):
        frozen=freeze_render(self.p,'r1',self.doc)
        self.assertTrue(check_render(self.p,frozen)['ready'])
        self.doc.write_text('{}')
        with self.assertRaisesRegex(ValueError,'INPUT_CHANGED_DURING_RENDER'):check_render(self.p,frozen)
        self.assertTrue((self.p/'work/input-freezes/r1.json').is_file())
        end_render(self.p,'r1','failed')
    def test_active_render_queues_change_without_applying(self):
        before=self.doc.read_bytes();freeze_render(self.p,'r2',self.doc)
        with self.assertRaisesRegex(ValueError,'INPUT_CHANGED_DURING_RENDER'):
            ensure_mutation_allowed(self.p,'edit',dict(replacement='new value'))
        self.assertEqual(self.doc.read_bytes(),before)
        queued=list((self.p/'work/pending-input-changes').glob('*.json'));self.assertEqual(len(queued),1)
        self.assertFalse(read(queued[0])['applied']);end_render(self.p,'r2','complete')
        ensure_mutation_allowed(self.p,'after-export')
    def test_true_dispatch_carries_source_and_refuses_missing_return(self):
        row=obligation(stage='script');self.assertTrue(update(self.p,[row])['ready'])
        result=dispatch(self.p,'task1','script')
        self.assertEqual(result['task']['quotes'][row['id']],row['original_quote'])
        self.assertTrue(all(Path(r['path']).is_file() for r in result['task']['inputs']))
        with self.assertRaisesRegex(ValueError,'HANDOFF_RETURN_INCOMPLETE'):require_dispatch_return(self.p,'task1')
    def test_plain_history_text_inside_allowed_action_is_rejected(self):
        packet=dict(input=dict(storyboard=dict(segments=[dict(beats=[dict(action='Compare UV02-F01 against previous review')])])),evidence=dict(media=[],frames=[]),allowed_artifacts=[])
        with self.assertRaisesRegex(ValueError,'REVIEW_INPUT_CONTAMINATED'):require_clean(packet)
        for marker in ['PILOT-F02: fix from the previous pilot review','UV03: previous user fix batch']:
            packet['input']['storyboard']['segments'][0]['beats'][0]['action']=marker
            with self.assertRaisesRegex(ValueError,'REVIEW_INPUT_CONTAMINATED'):require_clean(packet)
        packet['input']['storyboard']['segments'][0]['beats'][0]['action']='Move the product next to the order'
        require_clean(packet)
    def test_host_only_paths_are_not_sent_but_nested_private_paths_are_blocked(self):
        packet=dict(allowed_artifacts=[dict(id='f',path='/Users/private/qa/f.jpg')],evidence=dict(media=[],frames=[]))
        require_clean(packet)
        packet['input']=dict(text='Open /Users/private/source.pdf')
        with self.assertRaisesRegex(ValueError,'REVIEW_INPUT_CONTAMINATED'):require_clean(packet)
    def test_text_images_cannot_satisfy_listening(self):
        out=capability_matrix([dict(id='tail',required_method='full_av',critical=True)],['text','images'])
        self.assertFalse(out['ready']);self.assertIn('audio_listening',out['checks'][0]['missing']);self.assertFalse(out['inference_performed'])
    def test_review_lock_preserves_concurrent_updates(self):
        review=Review(self.course);path=self.p/'work/parallel-counter.json';atomic(path,dict(count=0))
        def increment(_):
            with Review(self.course).locked():
                value=read(path);value['count']+=1;atomic(path,value)
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(increment,range(40)))
        self.assertEqual(read(path)['count'],40)
    def test_public_cli_rejects_handwritten_receipt_without_formal_write(self):
        context=self.p/'forged.json';atomic(context,dict(allow_release=True))
        for script,args in [('execution_tools.py',[]),('kgxc_course.py',[])]:
            run=subprocess.run([sys.executable,str(ROOT/'skills/corporate-training-motion/scripts'/script),'release-copy','--project',str(self.p),'--input',str(context)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2,run.stdout+run.stderr)
        self.assertFalse((self.root/'formal').exists())
    def test_early_stage_cannot_target_real_formal_root(self):
        from release_gate import deliver,ReleaseBlocked
        from evidence_versions import sha
        import uuid
        target=Path.home()/'Desktop/ai 制课'/('guard-never-create-'+uuid.uuid4().hex)/'document.json'
        self.assertFalse(target.parent.exists())
        files=[dict(source=str(self.doc),destination=str(target),sha256=sha(self.doc),role='document')]
        with self.assertRaises(ReleaseBlocked) as caught:
            deliver(self.p,dict(purpose='outline',delivery_files=files),files)
        self.assertIn('RELEASE_PURPOSE_MISMATCH',{e['code']for e in caught.exception.result['errors']})
        self.assertFalse(target.parent.exists())

if __name__=='__main__':unittest.main()
