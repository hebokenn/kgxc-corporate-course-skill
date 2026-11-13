"""A current encoded candidate is inspected before a new render is requested."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from production import handoff
from workflow import export_job_projection


class CandidateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)/'project';self.p.mkdir()
        doc=dict(schema='course-workbench/1',revision=2,status='ready',fps=30,width=1920,height=1080,
                 adapter='scene-graph-v1',sourceDurationFrames=30,introFrames=0,bodyEndFrame=30,
                 media={},scenes=[],sceneGraph=dict(nodes=[]),fields=[],assets=[],holds=[],cuts=[],captions=[])
        (self.p/'workbench.json').write_text(json.dumps(doc))
        self.job=dict(id='encoded-current',status='complete',revision=2,registration_status='held',stage_registered=False,
                      video='/download/delivery/candidate.mp4',srt='/download/delivery/candidate.srt',
                      contract_pending=dict(required=True,ready=False,purpose='final',errors=[dict(requirement='logo',message='待核对当前Logo')]))

    def status(self,jobs,stage='final'):
        return handoff(self.p,dict(branch='video',stage=stage,jobs=jobs))

    def test_current_candidate_routes_to_its_existing_media_without_render_or_registration(self):
        before=(self.p/'workbench.json').read_bytes()
        value=self.status([self.job])
        self.assertEqual(value['action'],'verify-current-candidate')
        self.assertEqual(value['pending_candidates'][0]['video'],self.job['video'])
        self.assertEqual(value['pending_candidates'][0]['registration_status'],'held')
        self.assertEqual((self.p/'workbench.json').read_bytes(),before)

    def test_stale_revision_or_other_stage_does_not_reuse_a_candidate(self):
        stale=dict(self.job,revision=1)
        self.assertEqual(self.status([stale])['pending_candidates'],[])
        self.assertEqual(self.status([self.job],stage='pilot')['pending_candidates'],[])

    def test_registered_or_failed_jobs_are_not_contract_pending_candidates(self):
        self.assertEqual(self.status([dict(self.job,registration_status='registered',stage_registered=True)])['pending_candidates'],[])
        self.assertEqual(self.status([dict(self.job,status='failed')])['pending_candidates'],[])

    def test_actual_registered_path_and_exact_bytes_project_registered_without_rewriting_held_history(self):
        video=self.p.parent/'delivery/candidate.mp4';video.parent.mkdir();video.write_bytes(b'current encoded candidate')
        job=dict(self.job,contract_pending=dict(self.job['contract_pending'],video_sha256=hashlib.sha256(video.read_bytes()).hexdigest()))
        history=self.p/'result.json';history.write_text(json.dumps(job));before=history.read_bytes()
        state=dict(branch='video',stage='final',artifacts=dict(final=['../delivery/candidate.mp4']),jobs=[job])
        projected=export_job_projection(self.p,state,job)
        self.assertEqual(projected['registration_status'],'registered');self.assertTrue(projected['stage_registered'])
        self.assertEqual(handoff(self.p,state)['pending_candidates'],[])
        self.assertEqual(history.read_bytes(),before);self.assertEqual(job['registration_status'],'held')

    def test_unregistered_other_path_or_changed_bytes_remains_held(self):
        video=self.p.parent/'delivery/candidate.mp4';video.parent.mkdir();video.write_bytes(b'candidate bytes')
        job=dict(self.job,contract_pending=dict(self.job['contract_pending'],video_sha256=hashlib.sha256(video.read_bytes()).hexdigest()))
        for artifacts in [{},{'final':['../delivery/other.mp4']},{'pilot':['../delivery/candidate.mp4']}]:
            with self.subTest(artifacts=artifacts):
                self.assertEqual(export_job_projection(self.p,dict(artifacts=artifacts),job)['registration_status'],'held')
        video.write_bytes(b'changed candidate bytes')
        self.assertEqual(export_job_projection(self.p,dict(artifacts=dict(final=['../delivery/candidate.mp4'])),job)['registration_status'],'held')


if __name__=='__main__':unittest.main()
