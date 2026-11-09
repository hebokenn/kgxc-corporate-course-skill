"""No user audio approval; real synthetic bytes support technical facts only."""
import copy
import json
import subprocess
import unittest
from unittest import mock

import test_ai_review as fixtures
import test_review_audio_arrangement as audio_fixtures
import ai_review
from ai_review import approved, gate_errors
import blind_review as blind
from workflow import atomic, read, sha


class ProducerAudioTests(unittest.TestCase):
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    movie=audio_fixtures.AudioArrangementTests.movie
    ready_media=audio_fixtures.AudioArrangementTests.ready_media
    reviewer_result=audio_fixtures.AudioArrangementTests.reviewer_result
    blind_submit=audio_fixtures.AudioArrangementTests.blind_submit
    complete=audio_fixtures.AudioArrangementTests.complete
    declaration=audio_fixtures.AudioArrangementTests.declaration

    def setUp(self):
        fixtures.AIReviewTests.setUp(self);ai_review._AUDIO_TECHNICAL_CACHE.clear()

    def select(self):
        return self.review.set_review_arrangement(blind.PRODUCER_AUDIO_ARRANGEMENT,'PRIVATE_REAL_AUDIO_WAIVER 配音不用一句一句试听，配音不用我审核',
            actor='user-chat-confirmation',source=dict(kind='chat',id='actual-no-audio-approval-message'))

    def measure(self,path):
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],stderr=subprocess.PIPE))
        return ai_review._audio_technical(path,sha(path),probe)

    def synthetic(self,name='technical',audio='sine=frequency=660:duration=0.4',video_seconds=.4):
        path=self.project/'media'/f'{name}.mp4';path.parent.mkdir(exist_ok=True)
        args=['ffmpeg','-v','error','-f','lavfi','-i',f'color=c=red:s=96x64:r=10:d={video_seconds}']
        if audio:args.extend(['-f','lavfi','-i',audio,'-c:a','aac'])
        subprocess.run(args+['-c:v','libx264','-y',str(path)],check=True)
        return path

    def test_explicit_course_mode_is_private_reversible_and_never_creates_listening(self):
        self.assertEqual(self.review.arrangement(),blind.DEFAULT_ARRANGEMENT)
        for actor,source in [('producer',dict(kind='chat',id='forged')),('dsh-user-click',dict(kind='chat',id='wrong-origin'))]:
            with self.assertRaises(ValueError):self.review.set_review_arrangement(blind.PRODUCER_AUDIO_ARRANGEMENT,'不得代报',actor,source)
        self.select();run=self.ready_media();packet=self.review.packet('pilot',run)['packet'];encoded=json.dumps(packet,ensure_ascii=False)
        self.assertNotIn('PRIVATE_REAL_AUDIO_WAIVER',encoded);self.assertNotIn('actual-no-audio-approval-message',encoded)
        responsibilities=packet['review_contract']['responsibilities'];self.assertFalse(responsibilities['user_audio_approval_required'])
        self.assertFalse(responsibilities['continuous_listening_performed']);self.assertEqual(responsibilities['subjective_audio_status'],'not_evaluated')
        node=self.review.node_view('pilot');self.assertFalse(node['user_audio_review']['required'])
        self.assertEqual(node['user_audio_review']['status'],'user_approval_not_required');self.assertFalse(node['user_confirmed'])
        self.assertFalse(self.review.require_user_audio('pilot')['required'])
        self.assertIn('PRIVATE_REAL_AUDIO_WAIVER',self.review.producer_packet('pilot',run)['packet']['review_arrangement']['evidence'])
        self.review.finish('pilot',run,error='合成暂停');before=self.review.node_view('pilot')
        self.review.set_review_arrangement(blind.DEFAULT_ARRANGEMENT,'恢复原默认',actor='user-chat-confirmation',source=dict(kind='chat',id='restore-message'))
        self.assertEqual(self.review.arrangement(),blind.DEFAULT_ARRANGEMENT);self.assertEqual(self.review.node_view('pilot')['calls'],before['calls'])
        self.assertEqual(len(self.review.load()['review_arrangement_history']),2)

    def test_actual_byte_checks_pass_but_subjective_unknown_blocks_formal_approval_without_user_request(self):
        self.select();run=self.complete();node=self.review.node_view('pilot');report=node['run']['report']
        self.assertFalse(node['passed']);self.assertFalse(node['user_audio_review']['required']);self.assertFalse(report['user_audio_pending'])
        self.assertFalse(approved(self.course,'pilot'));self.assertTrue(gate_errors(self.course,'pilot'))
        self.assertIn('continuous-av',report['blocking_ids']);self.assertIn('ending',report['blocking_ids'])
        for item in report['items']:
            if item.get('responsibility')=='producer_audio_unverified':
                self.assertTrue(item['critical']);self.assertEqual(item['verdict'],'无法验证');self.assertFalse(item['allow_na'])
            if item.get('responsibility')=='producer_audio_technical':self.assertEqual(item['verdict'],'通过')
        technical=report['inspection']['media'][0]['audio_technical']
        self.assertEqual(technical['status'],'passed');self.assertTrue(technical['checks']['full_stream_decode'])
        self.assertGreater(technical['audio_sample_count'],0);self.assertFalse(technical['continuous_listening_performed'])
        self.assertEqual(technical['subjective_audio_status'],'not_evaluated');self.assertNotIn('full_av',report['methods'])
        with self.assertRaisesRegex(ValueError,'关键检查项'):self.review.approve('pilot',run)
        entry=node['run']['iterations'][-1]
        for raw in [entry['raw_result'],entry['raw_producer_result']]:self.assertEqual(next(i for i in raw['items'] if i['id']=='ending')['verdict'],'不适用')
        self.assertNotIn('user_audio_reviews',self.review.load()['nodes']['pilot'])

    def test_unknown_visual_evidence_still_blocks_and_model_cannot_forge_technical_pass(self):
        self.select();self.movie('pilot');path=self.course.relative(read(self.course.state_file)['artifacts']['pilot'][0])
        silent=self.synthetic('silent',audio='anullsrc=r=48000:cl=mono:d=0.4');path.write_bytes(silent.read_bytes())
        state=read(self.course.state_file);state['pilot_context']=self.course._video_context(state);atomic(self.course.state_file,state)
        run=self.begin('pilot',request='silent-current-media',mode='continue');result=self.reviewer_result('pilot',run,sequence=False)
        value=self.blind_submit('pilot',run,result);report=value['report']
        self.assertIn('motion-pacing',report['blocking_ids']);self.assertIn('audio-technical',report['blocking_ids'])
        self.assertEqual(next(i for i in report['items'] if i['id']=='audio-technical')['verdict'],'需修改')
        self.assertNotIn('user_audio',[i.get('responsibility') for i in report['items']])

    def test_audio_checks_are_sha_cached_copy_safe_and_current_bytes_required(self):
        path=self.synthetic()
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],stderr=subprocess.PIPE))
        with mock.patch.object(subprocess,'run',wraps=subprocess.run) as execute:
            first=ai_review._audio_technical(path,sha(path),probe);second=ai_review._audio_technical(path,sha(path),probe)
        self.assertEqual(execute.call_count,1);self.assertEqual(first,second);self.assertEqual(first['status'],'passed')
        second['checks']['full_stream_decode']=False;self.assertTrue(self.measure(path)['checks']['full_stream_decode'])
        digest=sha(path);path.write_bytes(path.read_bytes()+b'synthetic change')
        with self.assertRaisesRegex(ValueError,'字节已改变'):ai_review._audio_technical(path,digest,{})

    def test_missing_track_silence_and_stream_boundary_anomalies_fail_from_real_bytes(self):
        for path,issue in [(self.synthetic('missing',audio=None),'missing_audio_or_video_stream'),
                           (self.synthetic('silence',audio='anullsrc=r=48000:cl=mono:d=0.4'),'all_silent_or_inaudible_audio'),
                           (self.synthetic('mismatched',audio='sine=frequency=660:duration=0.8'),'audio_video_stream_boundary_mismatch')]:
            result=self.measure(path);self.assertEqual(result['status'],'failed');self.assertIn(issue,result['issues'])

    def test_sealed_current_byte_evidence_is_reused_across_role_requests_without_repeat_decode(self):
        self.select();run=self.ready_media()
        before=self.review.packet('pilot',run)['packet']['evidence']['media'][0]['audio_technical']
        self.blind_submit('pilot',run)
        ai_review._AUDIO_TECHNICAL_CACHE.clear()  # A new service process has no memory cache.
        with mock.patch.object(ai_review,'_audio_technical',side_effect=AssertionError('must reuse the sealed current-byte evidence')):
            packet=self.review.producer_packet('pilot',run)['packet']
        self.assertEqual(packet['evidence']['media'][0]['audio_technical'],before)

    def test_actual_corrupted_stream_decode_and_unavailable_check_never_pass(self):
        path=self.synthetic('corrupted');data=bytearray(path.read_bytes());offset=data.index(b'mdat')+4
        data[offset:offset+128]=b'\x00'*128;path.write_bytes(data)
        result=self.measure(path);self.assertEqual(result['status'],'failed');self.assertIn('stream_decode_failed',result['issues'])
        other=self.synthetic('timeout',audio='sine=frequency=880:duration=0.4')
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(other)],stderr=subprocess.PIPE))
        with mock.patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired('ffmpeg',30)):
            unknown=ai_review._audio_technical(other,sha(other),probe)
        self.assertEqual(unknown['status'],'unverified');self.assertIn('technical_check_unavailable:TimeoutExpired',unknown['issues'])

    def test_previous_real_user_audio_receipt_is_retained_and_not_relabelled(self):
        self.review.set_review_arrangement(blind.USER_AUDIO_ARRANGEMENT,'此前真实用户听审选择',actor='user-chat-confirmation',source=dict(kind='chat',id='old-choice'))
        self.movie('pilot');self.review.record_user_audio_review('pilot',**self.declaration())
        old=copy.deepcopy(self.review.load()['nodes']['pilot']['user_audio_reviews'])
        self.select();self.assertEqual(self.review.load()['nodes']['pilot']['user_audio_reviews'],old)
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'user_approval_not_required')
        self.assertFalse(self.review.node_view('pilot')['user_audio_review']['required'])


if __name__=='__main__':unittest.main()
