"""Resume must expose executable production work; sound selection must affect real mixes."""
from array import array
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import wave
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
import test_new_course_workbench as fixture_module
from backend import read,atomic
from workflow import Course,bundle_course
from production import handoff
from sound import PALETTE,ROLES,catalog,make_plan,mix,sha


class ContinuationSoundTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.NewCourseTests();self.fixture.setUp();self.p=self.fixture.p
        self.doc=self.fixture.ready();self.course=Course(self.fixture.course)
    def tearDown(self):self.fixture.tearDown()
    def events(self):
        data=dict(events=[dict(id=f'contact-{i}',frame=i*4,role='enter') for i in range(6)]+[dict(id='quiet',frame=28,role='none')])
        path=self.p/'source/sfx-events.json';atomic(path,data);return path

    def test_resume_reports_new_route_requirements_without_changing_confirmations(self):
        before=(self.p/'course-state.json').read_bytes()
        director=read(self.p/'director-plan.json');director['rendering']=dict(requiredEffects=['chars-in','draw-on'])
        atomic(self.p/'director-plan.json',director)
        status=self.course.status();info=status['production_handoff']
        self.assertTrue(info['automatic']);self.assertEqual(info['route_audit']['route'],'motion-canvas')
        self.assertEqual(info['action'],'upgrade-renderer');self.assertEqual(info['sound_defaults']['palette'],PALETTE)
        self.assertIn('制作接续',self.course.brief())
        self.assertEqual((self.p/'course-state.json').read_bytes(),before)

    def test_courseware_and_completed_courses_do_not_start_video_or_audio(self):
        for status in [dict(branch='courseware',stage='courseware',workflow_schema=2),dict(branch='video',stage='complete',workflow_schema=2)]:
            self.assertFalse(handoff(self.p,status)['active'])

    def test_palette_has_actual_distinct_waveforms_and_valid_hashes(self):
        data=catalog(self.p);self.assertEqual(len(data['assets']),45)
        self.assertEqual({a['role'] for a in data['assets']},set(ROLES))
        self.assertEqual(len({a['sha256'] for a in data['assets']}),45)
        for a in data['assets']:
            path=self.p/'audio/sfx'/PALETTE/a['path'];self.assertEqual(sha(path),a['sha256'])
            with wave.open(str(path),'rb') as w:
                self.assertEqual((w.getframerate(),w.getnchannels(),w.getsampwidth()),(48000,1,2))
                samples=array('h');samples.frombytes(w.readframes(w.getnframes()))
            self.assertGreater(max(abs(v) for v in samples),300);self.assertLess(max(abs(v) for v in samples),8000)
            self.assertLess(abs(samples[0]),10);self.assertLess(abs(samples[-1]),10)

    def test_same_role_varies_but_replanning_is_reproducible_and_respects_silence(self):
        path=self.events();first=make_plan(self.p,path)['plan'];second=make_plan(self.p,path)['plan']
        self.assertEqual(first,second);self.assertEqual(len(first['events']),6);self.assertEqual(len(first['skipped']),1)
        choices=[e['assetId'] for e in first['events']]
        self.assertTrue(all(a!=b for a,b in zip(choices,choices[1:])))
        self.assertEqual(read(self.p/'workbench.json'),self.doc)

    def test_real_mix_preserves_original_audio_and_can_bind_without_timeline_changes(self):
        # No-speech source is a technical fixture, not an approved narration.
        events=self.events();make_plan(self.p,events);before=sha(self.p/'audio/test.wav')
        receipt=mix(self.p,self.p/'audio/sfx-plan.json','audio/test.wav','audio/new-mix.wav',bind=True)
        self.assertEqual(sha(self.p/'audio/test.wav'),before);self.assertTrue(receipt['narration_source_unchanged'])
        self.assertGreater(receipt['peak'],.01);self.assertLess(receipt['peak'],.98)
        changed=read(self.p/'workbench.json');self.assertEqual(changed['media']['audio'],'audio/new-mix.wav')
        for k in ['scenes','captions','holds','cuts','sourceDurationFrames']:self.assertEqual(changed[k],self.doc[k])
        with wave.open(str(self.p/'audio/new-mix.wav'),'rb') as w:self.assertEqual(w.getnframes(),48000)
        self.assertTrue((self.p/'workbench-history/000000.json').is_file())
        with self.assertRaises(ValueError):mix(self.p,self.p/'audio/sfx-plan.json','audio/test.wav','audio/test.wav')

    def test_new_draft_uses_real_composition_timeline_before_configure(self):
        from scaffold import create
        import shutil
        target=self.fixture.course.parent/'new-draft';create(target);p=target/'project'
        shutil.copy2(self.p/'audio/test.wav',p/'audio/narration.wav')
        atomic(p/'source/course-composition.json',dict(sourceDurationFrames=30,fps=30))
        atomic(p/'source/sfx-events.json',dict(events=[dict(id='reveal',frame=15,role='reveal')]))
        result=make_plan(p,p/'source/sfx-events.json')
        self.assertEqual(result['plan']['sourceDurationFrames'],30)
        self.assertEqual(read(p/'workbench.json')['sourceDurationFrames'],1)
        receipt=mix(p,p/'audio/sfx-plan.json','audio/narration.wav','audio/course-mix.wav')
        self.assertEqual(receipt['duration'],1);self.assertIsNone(read(p/'workbench.json')['media']['audio'])

    def test_portable_package_restores_handoff_and_sound_tools(self):
        preview=self.p/'work/style-previews/approved.png';preview.parent.mkdir(parents=True,exist_ok=True);preview.write_bytes(b'approved style preview')
        (self.p/'work/unrelated-cache.bin').write_bytes(b'not distributable')
        archive=self.fixture.course/'packages/course.zip';bundle_course(self.fixture.course,archive)
        destination=self.fixture.course.parent/'portable'
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip());self.assertIn('project/work/style-previews/approved.png',z.namelist());self.assertNotIn('project/work/unrelated-cache.bin',z.namelist());z.extractall(destination)
        command=[sys.executable,str(destination/'project/editor/scripts/workflow.py'),'status',str(destination),'--json']
        status=json.loads(subprocess.check_output(command,text=True));self.assertTrue(status['production_handoff']['active'])
        tools=destination/'project/editor/scripts/course_tools.py'
        result=json.loads(subprocess.check_output([sys.executable,str(tools),'sfx-catalog'],text=True))
        self.assertEqual(result['id'],PALETTE);self.assertEqual(len(result['assets']),45)


if __name__=='__main__':unittest.main()
