"""Observable anti-dead-air behavior, with real decoded audio and edit mappings."""
import copy
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from continuity_pacing import audit, inspect, policy, require


def fixture():
    return dict(schema='course-workbench/1',revision=1,fps=30,sourceDurationFrames=300,
                scenes=[dict(id='S',kind='concept',sourceStartFrame=0,sourceEndFrame=300)],
                media=dict(audio='mix.wav',narration='dry.wav'),audio=dict(gain=1,speed=1),
                holds=[],cuts=[],captions=[],continuityPolicy=policy(),
                continuityPlan=dict(schema='course-continuity-plan/1',pauses=[]))


def pause(doc, a=90, z=210, maximum=4.1, kind='practice'):
    doc['continuityPlan']['pauses']=[dict(id='task',sceneId='S',kind=kind,
        window=dict(startFrame=a,endFrame=z),maxSeconds=maximum,
        reason='完成明确练习任务',learnerCue='请自行暂停完成练习后继续')]


def audio(path, seconds=10, quiet=()):
    rate=16000
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes(b''.join(struct.pack('<h',0 if any(a<=i/rate<z for a,z in quiet)
            else round(8000*math.sin(i*2*math.pi*220/rate))) for i in range(round(rate*seconds))))


class PlanTests(unittest.TestCase):
    def test_reading_can_overlap_continuous_narration_without_hold(self):
        from test_reading_pacing import fixture as reading_fixture
        from reading_pacing import inspect as reading_inspect
        d=reading_fixture();d.update(continuityPolicy=policy(),continuityPlan=fixture()['continuityPlan'])
        before=copy.deepcopy(d)
        self.assertEqual(reading_inspect(d)['status'],'pass')
        self.assertEqual(inspect(d)['status'],'pass');self.assertEqual(d,before)

    def test_reading_shortfall_is_not_automatically_repaired_with_silence(self):
        from test_reading_pacing import fixture as reading_fixture
        from reading_pacing import inspect as reading_inspect
        d=reading_fixture(90);before=copy.deepcopy(d)
        self.assertEqual(reading_inspect(d)['status'],'fail');self.assertEqual(d,before)
        d.update(continuityPolicy=policy(),continuityPlan=fixture()['continuityPlan'])
        d['holds']=[dict(sourceFrame=75,frames=120)]
        self.assertEqual(reading_inspect(d)['status'],'pass')
        self.assertEqual(inspect(d)['status'],'fail')

    def test_task_pause_is_bounded_and_cannot_cut_a_sentence(self):
        d=fixture();d['holds']=[dict(sourceFrame=180,frames=60)]
        pause(d,165,195,3.1)
        self.assertEqual(inspect(d)['status'],'pass',inspect(d))
        d['captions']=[dict(startFrame=150,endFrame=270)]
        self.assertTrue(any('口播字幕'in e for e in inspect(d)['errors']))

    def test_reading_and_scene_wide_exemptions_are_rejected(self):
        for kind in ['reading','transition','brand']:
            d=fixture();pause(d,0,300,4,kind)
            self.assertEqual(inspect(d)['status'],'fail')

    def test_observation_requires_an_explicit_learner_task(self):
        d=fixture();pause(d,kind='observation');self.assertEqual(inspect(d)['status'],'pass')
        d['continuityPlan']['pauses'][0]['learnerCue']=''
        self.assertEqual(inspect(d)['status'],'fail')

    def test_brief_brand_handoff_can_cross_scene_boundary_with_one_budget(self):
        d=fixture();d['scenes']=[dict(id='S',kind='brand',sourceStartFrame=0,sourceEndFrame=180),
                                dict(id='next',kind='navigation',sourceStartFrame=180,sourceEndFrame=300)]
        pause(d,150,210,2.1,'brand')
        self.assertEqual(inspect(d)['status'],'pass')
        d['continuityPlan']['pauses'][0]['window']['endFrame']=300
        self.assertEqual(inspect(d)['status'],'fail')

    def test_duplicate_or_overlapping_pause_windows_cannot_hide_more_gaps(self):
        d=fixture();pause(d);p=copy.deepcopy(d['continuityPlan']['pauses'][0]);p['id']='second'
        d['continuityPlan']['pauses'].append(p);self.assertEqual(inspect(d)['status'],'fail')

    def test_invalid_diagnostic_thresholds_are_not_a_bypass(self):
        for value in [float('nan'),float('inf'),True,100,0]:
            d=fixture();d['continuityPolicy']['gapSeconds']=value
            with self.subTest(value=value):self.assertEqual(inspect(d)['status'],'fail')

    def test_new_contract_cannot_be_deleted_and_legacy_does_not_migrate(self):
        d=fixture();d.pop('continuityPolicy');before=copy.deepcopy(d)
        self.assertEqual(inspect(d)['status'],'legacy-not-opted-in');self.assertEqual(d,before)
        with tempfile.TemporaryDirectory()as tmp:
            Path(tmp,'motion-contract.json').write_text('{"continuityRequired":true}')
            with self.assertRaisesRegex(ValueError,'不能删除 continuityPolicy'):require(d,tmp)


class ActualAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.d=fixture()
        audio(self.p/'dry.wav');audio(self.p/'mix.wav')
        (self.p/'workbench.json').write_text(json.dumps(self.d))
    def tearDown(self):self.tmp.cleanup()

    def test_continuous_narration_passes(self):
        self.assertEqual(audit(self.d,self.p)['status'],'pass')

    def test_background_music_cannot_mask_narration_interruption(self):
        audio(self.p/'dry.wav',quiet=[(3,7)])
        r=audit(self.d,self.p,video=self.p/'mix.wav')
        self.assertEqual(r['status'],'fail');self.assertTrue(r['narrationIntervals']);self.assertFalse(r['encodedIntervals'])

    def test_encoded_audio_gap_is_checked_even_when_source_is_continuous(self):
        audio(self.p/'mix.wav',quiet=[(3,7)])
        r=audit(self.d,self.p,video=self.p/'mix.wav')
        self.assertEqual(r['status'],'fail');self.assertFalse(r['narrationIntervals']);self.assertTrue(r['encodedIntervals'])

    def test_purposeful_gap_passes_only_within_its_actual_window(self):
        audio(self.p/'dry.wav',quiet=[(3,7)]);pause(self.d)
        self.assertEqual(audit(self.d,self.p)['status'],'pass')
        self.d['continuityPlan']['pauses'][0]['window']=dict(startFrame=0,endFrame=120)
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_silent_navigation_is_not_exempt(self):
        self.d['scenes'][0]['kind']='navigation';audio(self.p/'dry.wav',quiet=[(0,5.5)])
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_dry_track_is_required_even_if_mix_is_continuous(self):
        self.d['media'].pop('narration')
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_cut_can_remove_bad_gap_without_changing_source(self):
        audio(self.p/'dry.wav',quiet=[(3,7)]);self.d['cuts']=[dict(startFrame=90,endFrame=210)]
        self.assertEqual(audit(self.d,self.p)['status'],'pass')

    def test_cut_can_join_two_short_gaps_into_a_bad_gap(self):
        audio(self.p/'dry.wav',quiet=[(3,5),(6,8)]);self.d['cuts']=[dict(startFrame=150,endFrame=180)]
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_hold_and_natural_tail_share_one_total_budget(self):
        audio(self.p/'dry.wav',quiet=[(5,6)]);self.d['holds']=[dict(sourceFrame=165,frames=60)]
        pause(self.d,150,180,3.1)
        self.assertEqual(audit(self.d,self.p)['status'],'pass')
        self.d['holds'][0]['frames']=120
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_sample_offset_uses_same_display_clock_as_final(self):
        audio(self.p/'dry.wav',quiet=[(5,9)]);pause(self.d,150,270,4.1)
        r=audit(self.d,self.p,first=120,last=300)
        self.assertEqual(r['status'],'pass',r);self.assertAlmostEqual(r['narrationIntervals'][0]['start'],5,places=2)

    def test_source_duration_mismatch_fails(self):
        audio(self.p/'dry.wav',seconds=8)
        self.assertEqual(audit(self.d,self.p)['status'],'fail')

    def test_registration_rejects_stale_voice_video_document_and_range(self):
        from continuity_pacing import export_errors
        r=audit(self.d,self.p,video=self.p/'mix.wav')
        meta=dict(verification=dict(narrationContinuity=r),range=dict(firstFrame=0,lastFrame=300,fps=30))
        self.assertEqual(export_errors(self.d,self.p,self.p/'mix.wav',meta),[])
        for key,value in [('videoSha256','stale'),('narrationSha256','stale'),('documentSha256','stale'),('lastFrame',150)]:
            stale=copy.deepcopy(meta);stale['verification']['narrationContinuity'][key]=value
            with self.subTest(key=key):self.assertTrue(export_errors(self.d,self.p,self.p/'mix.wav',stale))

    def test_explicit_enable_preserves_original_and_is_idempotent(self):
        from continuity_pacing import enable
        original=copy.deepcopy(self.d);original.pop('continuityPolicy')
        (self.p/'workbench.json').write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError,'实际修改依据'):enable(self.p,'')
        r=enable(self.p,'QA opt-in only; not a user approval')
        self.assertEqual(r['revision'],2)
        self.assertEqual(json.loads((self.p/'workbench-history/000001.json').read_text()),original)
        self.assertEqual(enable(self.p,'QA')['status'],'already-enabled')

    def test_real_encoded_container_is_decoded_and_bound(self):
        video=self.p/'actual.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=s=160x90:r=30:d=10',
            '-i',str(self.p/'mix.wav'),'-c:v','libx264','-c:a','aac','-shortest',str(video)],check=True)
        r=audit(self.d,self.p,video=video)
        self.assertEqual(r['status'],'pass');self.assertEqual(len(r['videoSha256']),64)


if __name__=='__main__':unittest.main()
