"""Real synthetic H264/AAC fixtures. No listening, human approval or native-view claim."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
import final_media_checks as media
spec=importlib.util.spec_from_file_location('execution_finish',ROOT/'skills/corporate-training-motion/scripts/finish_media.py')
finish=importlib.util.module_from_spec(spec);spec.loader.exec_module(finish)


def run(args):return subprocess.run(args,check=True,capture_output=True)
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def reference(path):return dict(path=str(path),sha256=media.sha(path))


class FinalSyntheticMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('ffmpeg'):raise unittest.SkipTest('ffmpeg required for actual media fixture')
        cls.tmp=tempfile.TemporaryDirectory()
        cls.p=Path(os.environ.get('EXECUTION_FINAL_MEDIA_EVIDENCE_DIR',cls.tmp.name))/'project';cls.p.mkdir(parents=True,exist_ok=True)
        p=cls.p
        (p/'chapters.ffmeta').write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Whole\n')
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=64x36:r=24:d=2','-f','ffmetadata','-i',str(p/'chapters.ffmeta'),'-map','0:v:0','-map_metadata','1','-map_chapters','1','-c:v','libx264','-pix_fmt','yuv420p',str(p/'source.mp4')])
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=64x36','-frames:v','1','-threads','1',str(p/'cover.png')])
        count=round(2.02*48000)
        for name,gain in [('speech.wav',.1),('bed.wav',.01)]:
            with wave.open(str(p/name),'wb')as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000)
                f.writeframes(b''.join(struct.pack('<h',round(gain*32767*math.sin(2*math.pi*440*i/48000)))for i in range(count)))
        (p/'source.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nFirst.\n\n2\n00:00:01,000 --> 00:00:01,875\nLast.\n\n')
        cls.plan=dict(project_dir='.',video='source.mp4',srt='source.srt',speech='speech.wav',bed='bed.wav',cover='cover.png',output_video='candidate.mp4',output_srt='candidate.srt')
        write(p/'finish-plan.json',cls.plan);cls.receipt=finish.finish(p/'finish-plan.json')
        cls.video=p/'candidate.mp4'
        cls.doc=dict(fps=24,width=64,height=36,sourceDurationFrames=48,introFrames=4,bodyEndFrame=44,
            captions=[dict(text='First.',startFrame=0,endFrame=24),dict(text='Last.',startFrame=24,endFrame=45)])
        write(p/'workbench.json',cls.doc)
        cls.context=dict(course_id='synthetic-media',purpose='final',current_document=str(p/'workbench.json'),current_video=str(cls.video),current_contract=str(p/'production-contract.json'),current_review_refs=[])
        cls.base=dict(expected=dict(frames=48,fps='24',width=64,height=36),source_video=reference(p/'source.mp4'),narration=reference(p/'speech.wav'),
            subtitles=reference(p/'candidate.srt'),cover=reference(p/'cover.png'),audio=dict(mode='copy',source=reference(Path(cls.receipt['audio_complete_path']))),
            visual_review=dict(status='unverified',scope='No subjective viewing claimed by fixture'),thumbnail_review=dict(status='unverified'),tail_listening=dict(status='unverified'),full_av=dict(status='unverified'))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def contract(self,plan=None):
        write(self.p/'production-contract.json',dict(final_media=plan or self.base,requirements=dict(chapters=dict(chapter_table=[dict(chapter_id='whole',label='Whole',display_start=0,display_end=48)]))))
    def check(self,plan=None,video=None):
        self.contract(plan);context=copy.deepcopy(self.context)
        if video:context['current_video']=str(video)
        return media.inspect(self.p,context)
    def test_technical_decode_reused_only_for_unchanged_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'candidate.mp4'
            shutil.copyfile(self.video,target)
            media._decoded_clock.cache_clear()
            with patch.object(media,'run',wraps=media.run) as execute:
                initial=media.decoded_clock(target,media.sha(target))
                self.assertEqual(len(initial[1]),48)
                self.assertEqual(execute.call_count,3)
                self.assertEqual(media.decoded_clock(target,media.sha(target)),initial)
                self.assertEqual(execute.call_count,3)
                with target.open('ab') as stream:
                    stream.write(bytes.fromhex('0000000866726565'))
                self.assertEqual(media.decoded_clock(target,media.sha(target))[1],initial[1])
                self.assertEqual(execute.call_count,6)

    def test_01_first_frame_only_native24fps_and_all_audio_packets_survive(self):
        r=self.check();codes={e['code']for e in r['errors']}
        self.assertEqual(r['checks']['decode']['frames'],48);self.assertEqual(r['checks']['decode']['fps'],'24')
        self.assertTrue(r['checks']['audio']['packet_payloads_equal']);self.assertNotIn('COVER_FRAME_MISMATCH',codes)
        self.assertNotIn('FINAL_MEDIA_NOT_READY',codes);self.assertNotIn('SRT_TIME_MISMATCH',codes);self.assertNotIn('CHAPTER_TABLE_STALE',codes)
        self.assertFalse(r['ready']);self.assertIn('AUDIO_REVIEW_UNVERIFIED',codes)
        meta=media.probe(self.video);self.assertGreater(len([s for s in meta['streams']if s['codec_type']=='video']),1)
        write(self.p/'actual-technical-positive-with-unverified-listening.json',r)
    def test_02_two_frame_cover_fails_actual_second_frame(self):
        plan=copy.deepcopy(self.plan);plan.update(output_video='bad-cover.mp4',output_srt='bad-cover.srt',cover_hold_seconds=.1,cover_timing_authorization='synthetic explicit timing experiment')
        path=self.p/'bad-cover-plan.json';write(path,plan);finish.finish(path)
        self.assertIn('COVER_FRAME_MISMATCH',{e['code']for e in self.check(video=self.p/'bad-cover.mp4')['errors']})
    def test_03_lost_audio_packets_fail_even_when_video_frames_complete(self):
        short=self.p/'short.m4a';out=self.p/'truncated-audio.mp4'
        run(['ffmpeg','-v','error','-y','-i',self.receipt['audio_complete_path'],'-t','0.8','-c','copy',str(short)])
        run(['ffmpeg','-v','error','-y','-i',str(self.video),'-i',str(short),'-map','0:v:0','-map','1:a:0','-map_metadata','0','-map_chapters','0','-c','copy',str(out)])
        r=self.check(video=out);self.assertEqual(r['checks']['decode']['frames'],48)
        self.assertIn('AAC_PAYLOAD_MISMATCH',{e['code']for e in r['errors']})
        write(self.p/'actual-truncated-audio-negative.json',r)
    def test_04_old_srt_hash_and_illegal_overlap_fail(self):
        bad=self.p/'bad.srt';bad.write_text('1\n00:00:00,000 --> 00:00:01,500\nFirst.\n\n2\n00:00:01,000 --> 00:00:01,875\nLast.\n\n')
        plan=copy.deepcopy(self.base);plan['subtitles']=reference(bad)
        self.assertIn('SRT_TIME_MISMATCH',{e['code']for e in self.check(plan)['errors']})
        plan['subtitles']['sha256']='0'*64
        self.assertIn('FINAL_MEDIA_NOT_READY',{e['code']for e in self.check(plan)['errors']})
    def test_05_early_script_is_not_blocked_on_future_aac_or_cover(self):
        r=media.inspect(self.p,dict(self.context,purpose='script',current_video=None))
        self.assertTrue(r['ready'],r['errors']);self.assertEqual(r['checks']['future_media'],'not_applicable_at_current_stage')
    def test_06_direct_formal_path_rejected_before_directory_write(self):
        plan=copy.deepcopy(self.plan);plan.update(output_video=str(self.p.parent/'Desktop/ai 制课/fixture/video.mp4'),output_srt='blocked.srt')
        path=self.p/'desktop-plan.json';write(path,plan)
        with self.assertRaisesRegex(ValueError,'Desktop'):finish.finish(path)
        self.assertFalse((self.p.parent/'Desktop').exists())
    def test_07_unrequested_slowdown_is_rejected(self):
        plan=copy.deepcopy(self.plan);plan.update(output_video='slowed.mp4',output_srt='slowed.srt',rate=.9)
        path=self.p/'slow-plan.json';write(path,plan)
        with self.assertRaisesRegex(ValueError,'authorization'):finish.finish(path)
    def test_08_reencode_uses_samples_not_equal_compressed_bytes(self):
        plan=copy.deepcopy(self.base);plan['audio'].update(mode='reencode',expected_samples=round(2.02*48000),calibrated_sample_tolerance=1024,tolerance_basis='synthetic AAC padding measurement, not subjective hearing')
        r=self.check(plan);self.assertNotIn('AUDIO_SAMPLE_CLOCK_MISMATCH',{e['code']for e in r['errors']})
        plan['audio']['expected_samples']=48000
        self.assertIn('AUDIO_SAMPLE_CLOCK_MISMATCH',{e['code']for e in self.check(plan)['errors']})
    def test_09_text_image_probe_cannot_be_relabelled_continuous_listening(self):
        path=self.p/'text-image-probe.json';write(path,dict(schema='review-runner-probe/1',tool='synthetic text-image-only runner',route=dict(provider='fixture',model='fixture'),capabilities=['text','images','automatic_audio_technical'],probes=[dict(kind='image',ok=True)]))
        plan=copy.deepcopy(self.base);plan['full_av']=dict(status='verified',actor='fixture',scope='Synthetic attempted relabelling, not actual listening',method='actual-continuous-av',video_sha256=media.sha(self.video),document_sha256=media.sha(self.p/'workbench.json'),listening_performed=True,continuous_playback=True,range_seconds=[0,2],observations=['Synthetic control'],capability_ref=reference(path))
        r=self.check(plan)
        self.assertTrue(any(e['code']=='AUDIO_REVIEW_UNVERIFIED'and 'capability'in e['message']for e in r['errors']))
    def test_10_copy_authorization_is_not_a_user_listening_declaration(self):
        path=self.p/'user-copy-only.json';write(path,dict(actor_type='user',original_quote='Replace the desktop files',video_sha256=media.sha(self.video)))
        plan=copy.deepcopy(self.base);plan['tail_listening']=dict(status='verified',actor='user',scope='Synthetic copy instruction only',method='user-actual-media-review',video_sha256=media.sha(self.video),document_sha256=media.sha(self.p/'workbench.json'),listening_performed=True,range_seconds=[0,2],observations=['Synthetic control'],source_event_ref=reference(path))
        r=self.check(plan)
        self.assertTrue(any(e['code']=='AUDIO_REVIEW_UNVERIFIED'and 'declaration'in e['message']for e in r['errors']))
    def test_11_pilot_does_not_require_future_external_cover_thumbnail(self):
        plan=copy.deepcopy(self.base);plan.pop('cover');plan.pop('thumbnail_review');plan['source_range']=[0,48]
        self.contract(plan);context=dict(self.context,purpose='pilot')
        r=media.inspect(self.p,context)
        self.assertNotIn('FINAL_MEDIA_NOT_READY',{e['code']for e in r['errors']})
        self.assertFalse(any(e.get('item')=='thumbnail_review'for e in r['errors']))
        self.assertIn('AUDIO_REVIEW_UNVERIFIED',{e['code']for e in r['errors']})
    def test_12_pilot_cut_through_phrase_is_rejected(self):
        plan=copy.deepcopy(self.base);plan.pop('cover');plan['source_range']=[12,60]
        self.contract(plan);r=media.inspect(self.p,dict(self.context,purpose='pilot'))
        self.assertIn('SAMPLE_SEMANTIC_BOUNDARY',{e['code']for e in r['errors']})

if __name__=='__main__':unittest.main()
