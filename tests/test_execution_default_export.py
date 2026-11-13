"""Actual standard Workspace→worker→browser→H264/AAC at 24fps; never a quality approval."""
from pathlib import Path
import http.server
import json
import os
import shutil
import hashlib
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/scripts'),str(ROOT/'skills/corporate-training-motion/workbench')]
import test_new_course_workbench as legacy_fixture
from backend import Workspace,Handler
from workflow import read

class DefaultExportTests(unittest.TestCase):
    def test_packaging_is_only_for_final_after_worker_finishes(self):
        fixture=legacy_fixture.NewCourseTests();fixture.setUp()
        try:
            doc=fixture.ready()
            space=Workspace(fixture.course)
            from workflow import atomic
            def finished_worker(command,**kwargs):
                directory=Path(command[command.index('--directory')+1])
                (directory/'video.mp4').write_bytes(b'test packaging fixture; not video')
                atomic(directory/'verification.json',dict(fullDecode=True))
                return type('Completed',(),dict(pid=0,returncode=0,poll=lambda self:0))()
            with patch('backend.owned_export_process',side_effect=finished_worker), \
                 patch('backend.Workspace.require_production_active'), \
                 patch('workflow.Course.require_video'), \
                 patch('release_gate.evaluate',return_value=dict(allow_release=False)), \
                 patch('release_gate.build_context'), \
                 patch('workflow.bundle_course') as bundle:
                for purpose in ['pilot','final']:
                    job=space.start_export(doc['revision'],0,1,'http://127.0.0.1:1',purpose=purpose)
                    directory=space.work/'exports'/job['id']
                    deadline=time.monotonic()+8
                    while not (directory/'result.json').exists() and time.monotonic()<deadline:time.sleep(.02)
                    receipt=read(directory/'result.json')
                    self.assertEqual(receipt['status'],'complete',receipt)
                    self.assertTrue(receipt['video'].endswith('.mp4'))
                    self.assertTrue(receipt['srt'].endswith('.srt'))
                    if purpose=='pilot':
                        self.assertNotIn('package',receipt)
                        self.assertFalse(list((fixture.course/'packages').glob('*.zip')))
                        bundle.assert_not_called()
                    else:
                        self.assertTrue(receipt['package'].endswith('.zip'))
                        self.assertEqual(len(list((fixture.course/'packages').glob('*.zip'))),1)
                        bundle.assert_called_once()
        finally:fixture.tearDown()

    def test_actual_24fps_default_export_keeps_complete_aac_and_chapters_as_held_candidate(self):
        fixture=legacy_fixture.NewCourseTests('test_authoring_generates_bindings_and_does_not_overwrite_edits');fixture.setUp()
        server=None
        try:
            table=[dict(chapter_id='one',label='第一段',source_start=0,source_end=12,display_start=0,display_end=12),dict(chapter_id='two',label='第二段',source_start=12,source_end=24,display_start=12,display_end=24)]
            doc=fixture.ready(dict(fps=24,sourceDurationFrames=24,chapterTable=table,
                scenes=[dict(id='X',chapter='技术',title='对象',sourceStartFrame=0,sourceEndFrame=24)],
                captions=[dict(id='c',sceneId='X',text='核对',startFrame=0,endFrame=24)]))
            self.assertEqual(doc['fps'],24)
            space=Workspace(fixture.course);server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=space
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url='http://127.0.0.1:'+str(server.server_port)
            job=space.start_export(doc['revision'],0,1,url,purpose='pilot')
            deadline=time.monotonic()+60
            while job['status'] not in ['complete','failed','cancelled'] and time.monotonic()<deadline:time.sleep(.1)
            self.assertEqual(job['status'],'complete',job)
            self.assertNotIn('package',job)
            self.assertFalse(list((fixture.course/'packages').glob('*.zip')))
            self.assertEqual(job['registration_status'],'held');self.assertFalse(job['stage_registered'])
            proof=job['verification']['verification'];self.assertEqual(proof['frames'],24);self.assertEqual(proof['fps'],24)
            self.assertTrue(proof['audioCompletion']['all_packets_and_timestamps_equal']);self.assertGreater(proof['audioCompletion']['copied_aac_packets'],0)
            video=fixture.course/'delivery'/Path(job['video']).name
            meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_chapters','-show_streams','-of','json',str(video)]))
            self.assertEqual([r['tags']['title']for r in meta['chapters']],['第一段','第二段'])
            self.assertEqual(meta['streams'][0]['avg_frame_rate'],'24/1')
            self.assertFalse(read(fixture.p/'course-state.json').get('artifacts',{}).get('pilot'))
            if os.environ.get('KGXC_DEFAULT_EXPORT_EVIDENCE'):
                target=Path(os.environ['KGXC_DEFAULT_EXPORT_EVIDENCE']).resolve();target.mkdir(parents=True,exist_ok=False)
                shutil.copytree(fixture.course,target/'course',ignore=shutil.ignore_patterns('__pycache__','node_modules'))
                sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
                sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),*[ROOT/'skills/corporate-training-motion/workbench'/name for name in ['backend.py','authoring.py','render_worker.py','timeline.py','timeline.js','renderer.js','export_playback.py','render_input_guard.py']]]}
                receipt=dict(schema='retained-standard-export-evidence/1',status='actual-standard-candidate-generated',
                    current_quality_release_allowed=False,source_root=str(ROOT),source_sha256=sources,
                    original_temporary_course=str(fixture.course),retained_course=str(target/'course'),
                    video=dict(path=str(target/'course/delivery'/video.name),sha256=sha(video)),
                    actual_probe=meta,actual_job=job,actual_verification=proof,
                    files={str(p.relative_to(target/'course')):sha(p)for p in (target/'course').rglob('*')if p.is_file()},
                    limits='Synthetic historical QA input setup; actual default renderer/worker/FFmpeg, no gate mock; held candidate, not media quality acceptance')
                (target/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        finally:
            if server:server.shutdown();server.server_close()
            fixture.tearDown()

if __name__=='__main__':unittest.main()
