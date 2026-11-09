from pathlib import Path
from types import SimpleNamespace
import copy
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from workflow import Course,atomic,read
from studio import Studio,compose
from test_branch_workflow import design
from test_storyboard_workflow import fixture
from export_playback import playback,audio_settings


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();project=self.root/'project'
        atomic(project/'workbench.json',{'title':'工作台技术夹具','scenes':[],'media':{}})
        self.course=Course(self.root);self.course.init('工作台技术夹具',planning='storyboard-v1');design(self.course)
        plan=read(self.course.plan_file);base=plan['units'][0]
        plan['units']=[dict(copy.deepcopy(base),id='U'+str(i),title='章节'+str(i)) for i in range(1,4)]
        self.course.save_plan(plan,self.rev())
        self.studio=Studio(SimpleNamespace(root=self.root,project=project,file=project/'workbench.json'))
    def tearDown(self):self.tmp.cleanup()
    def rev(self):return self.course.status()['revision']
    def sections(self):return [{'unit_id':'U1','body':'先核对订单。\n\n再核对商品编码。'},{'unit_id':'U2','body':'发现不一致就记录。'},{'unit_id':'U3','body':'核对完成后交接。'}]
    def ready_script(self):
        self.course.confirm('outline',self.rev(),'技术夹具明确确认',actor='qa-operator')
        self.studio.save_sections(self.sections(),self.rev(),official=True)
        from source_coverage_fixture import confirm_fixture_coverage
        confirm_fixture_coverage(self.course)
        self.studio.confirm('script',self.rev())
    def ready_board(self):
        self.ready_script();board=fixture(self.course);mapping=read(self.course.plan_file)['script_mapping']['paragraphs']
        for shot,item in zip(board['segments'],mapping):shot.update(unit_id=item['unit_id'],source_paragraph_ids=[item['id']])
        self.course.save_storyboard(board,self.rev());self.course.choose_shot('all','recommended',self.rev(),'技术夹具方案选择',actor='qa-operator')
        self.course.confirm('storyboard',self.rev(),'技术夹具分镜确认',actor='qa-operator')
    def test_draft_save_keeps_approvals_and_formal_script_separate(self):
        self.studio.save_sections(self.sections(),self.rev(),0)
        self.assertFalse(self.course.script()['text']);self.assertEqual(read(self.course.state_file)['gates'],{})
        view=self.studio.view();self.assertTrue(view['mapped']);self.assertTrue(view['editor']['changed'])
        self.assertEqual([s['unit_id'] for s in view['sections']],['U1','U2','U3'])
    def test_reopened_progress_retains_export_purpose_and_completion_without_heavy_proofs(self):
        folder=self.studio.project/'work/workbench/exports/abc123abc123'
        atomic(folder/'document.json',{})
        atomic(folder/'result.json',dict(id=folder.name,purpose='pilot',status='complete',progress=1,verification=dict(large='not needed for progress')))
        jobs=self.studio.view()['jobs']
        self.assertEqual(jobs[0]['purpose'],'pilot');self.assertEqual(jobs[0]['progress'],1);self.assertNotIn('verification',jobs[0])
    def test_isolated_qa_confirmation_cannot_be_mistaken_for_business_acceptance(self):
        atomic(self.studio.project/'workbench-review-context.json',dict(scope='qa-simulation',course_id=read(self.course.state_file)['course_id']))
        self.studio.confirm('outline',self.rev())
        receipt=read(self.course.state_file)['gates']['outline']
        self.assertEqual(receipt['actor'],'qa-operator');self.assertIn('不代表正式课程',receipt['evidence'])
    def test_reorder_moves_the_same_words_and_paragraph_ids_and_invalidates_downstream(self):
        self.ready_board();before=self.studio.view();ids={s['unit_id']:[p['id'] for p in s['paragraphs']] for s in before['sections']}
        board_ids={s['id']:s['unit_id'] for s in self.course.storyboard()['segments']}
        after=self.studio.restructure('reorder',{'baseRevision':self.rev(),'order':['U3','U1','U2']})
        self.assertEqual([s['unit_id'] for s in after['sections']],['U3','U1','U2'])
        for section in after['sections']:self.assertEqual([p['id'] for p in section['paragraphs']],ids[section['unit_id']])
        text=self.course.script()['text'];self.assertLess(text.index('核对完成后交接'),text.index('先核对订单'))
        self.assertEqual(text.count('先核对订单'),1)
        self.assertEqual({s['id']:s['unit_id'] for s in self.course.storyboard()['segments']},board_ids)
        self.assertEqual(self.course.storyboard()['segments'][0]['unit_id'],'U3')
        self.assertTrue(all(g['status']=='stale' for g in after['gates'] if g['id'] in ['outline','script','storyboard']))
    def test_local_edit_preserves_other_sections_ids_and_official_file(self):
        self.ready_board();old=self.studio.view();formal=self.course.script()['text'];sections=copy.deepcopy(old['sections'])
        previous=sections[1]['paragraphs'][0]['id'];sections[1]['body']='发现不一致，先暂停并记录。'
        value=self.studio.save_sections(sections,self.rev(),old['editor']['revision'])
        self.assertEqual(value['sections'][1]['paragraphs'][0]['id'],previous)
        self.assertEqual(value['sections'][0],old['sections'][0]);self.assertEqual(value['sections'][2],old['sections'][2])
        self.assertEqual(self.course.script()['text'],formal)
        self.assertEqual(value['impact']['unit_ids'],['U2']);self.assertTrue(value['impact']['segment_ids'])
    def test_unbound_manual_text_is_not_guessed_or_lost_on_structure_change(self):
        self.studio.editor.save('完整人工稿，尚未给出章节身份。',0);before=self.studio.editor.path.read_bytes()
        with self.assertRaises(ValueError):self.studio.restructure('reorder',{'baseRevision':self.rev(),'order':['U3','U1','U2']})
        self.assertEqual(self.studio.editor.path.read_bytes(),before)
    def test_stale_revision_cannot_overwrite_a_newer_draft(self):
        revision=self.rev();self.studio.save_sections(self.sections(),revision,0)
        with self.assertRaises(FileExistsError):self.studio.save_sections(self.sections(),revision,0)
    def test_undo_is_monotonic_and_cannot_roll_back_a_later_ai_update(self):
        self.studio.save_sections(self.sections(),self.rev(),0);saved=self.studio.view()
        self.studio.undo(self.rev());self.assertFalse(self.studio.editor.read()['text'])
        self.assertGreater(self.studio.editor.read()['revision'],saved['editor']['revision'])
        self.studio.save_sections(self.sections(),self.rev(),self.studio.editor.read()['revision'])
        plan=read(self.course.plan_file);plan['audience']='另一个已更新的受众';self.course.save_plan(plan,self.rev())
        with self.assertRaises(ValueError):self.studio.undo(self.rev())
        self.assertEqual(read(self.course.plan_file)['audience'],'另一个已更新的受众')
    def test_source_upload_is_bounded_to_inputs_and_duplicate_hash_is_reused(self):
        revision=self.rev();value=self.studio.add_source('../原始资料.txt',b'new original',revision)
        self.assertTrue((self.root/'inputs/原始资料.txt').is_file());self.assertFalse((self.root.parent/'原始资料.txt').is_file())
        self.assertEqual(len(self.studio.add_source('another.txt',b'new original',self.rev())['sources']),len(value['sources']))
        self.assertFalse(any(g['status']=='confirmed' for g in value['gates']))
    def test_split_and_merge_retain_existing_paragraph_identity(self):
        self.ready_script();before=self.studio.view();ids=[p['id'] for s in before['sections'] for p in s['paragraphs']]
        split=self.studio.restructure('split',{'unit_id':'U1','paragraph_index':1,'baseRevision':self.rev()})
        self.assertEqual([p['id'] for s in split['sections'] for p in s['paragraphs']],ids)
        merged=self.studio.restructure('merge',{'unit_id':'U1','baseRevision':self.rev()})
        self.assertEqual([p['id'] for s in merged['sections'] for p in s['paragraphs']],ids)
    def test_proposal_does_not_overwrite_manual_text_until_adopted(self):
        self.studio.save_sections(self.sections(),self.rev(),0);before=self.studio.editor.read()['text']
        candidate=self.sections();candidate[0]['body']='修改建议正文。'
        proposed=self.studio.proposal('script',{'sections':candidate},self.rev())
        self.assertEqual(self.studio.editor.read()['text'],before)
        chosen=self.studio.action('adopt',{'id':proposed['proposals'][0]['id'],'baseRevision':self.rev()})
        self.assertIn('修改建议正文',chosen['editor']['text']);self.assertFalse(self.course.script()['text'])

    def test_export_navigation_is_bound_to_video_bytes_and_frozen_timeline(self):
        doc=dict(fps=30,sourceDurationFrames=900,holds=[dict(sourceFrame=300,frames=60)],cuts=[dict(startFrame=30,endFrame=60)],
                 storyboardBindings=[dict(segment_id='S2',option_id='A',startFrame=300,endFrame=600)],
                 scenes=[dict(id='scene2',chapter='第二章',sourceStartFrame=300,sourceEndFrame=600)])
        frozen=playback(doc,first=0,last=930)
        self.assertEqual(frozen['bindings'][0]['playback_start'],11)
        self.assertEqual(frozen['bindings'][0]['playback_end'],21)
        self.assertTrue(frozen['bindings'][0]['playback_complete'])
        self.assertEqual(frozen['chapters'][0]['start'],11)
        from workflow import sha
        video=self.root/'delivery/test.mp4';video.parent.mkdir(exist_ok=True);video.write_bytes(b'video fixture')
        atomic(video.with_suffix('.json'),dict(video_sha256=sha(video),playback=frozen))
        state=read(self.course.state_file);state['artifacts']={'pilot':['../delivery/test.mp4']};atomic(self.course.state_file,state)
        artifact=self.studio.view()['artifacts']['pilot'][0]
        self.assertEqual(artifact['chapters'][0]['start'],11)
        video.write_bytes(b'replaced video')
        self.assertEqual(self.studio.view()['artifacts']['pilot'][0]['bindings'],[])

    def test_cropped_or_cut_sample_is_not_reported_as_complete(self):
        doc=dict(fps=30,sourceDurationFrames=900,holds=[],cuts=[dict(startFrame=350,endFrame=400)],
                 storyboardBindings=[dict(segment_id='S2',startFrame=300,endFrame=600)],scenes=[])
        self.assertFalse(playback(doc)['bindings'][0]['playback_complete'])
        doc['cuts']=[]
        cropped=playback(doc,first=360,last=900)['bindings'][0]
        self.assertFalse(cropped['playback_complete']);self.assertEqual(cropped['playback_start'],0)
    def test_voice_label_and_rate_require_the_exact_audio_bytes(self):
        from workflow import sha
        audio=self.studio.project/'voice.wav';audio.write_bytes(b'voice metadata binding fixture')
        atomic(audio.with_suffix('.wav.json'),dict(audio_sha256=sha(audio),profile='didi',speed=1,delivery_rate=1.1))
        doc=dict(media=dict(audio='voice.wav'))
        self.assertEqual(audio_settings(doc,self.studio.project)['speed'],1.1)
        audio.write_bytes(b'changed audio binding fixture')
        self.assertEqual(audio_settings(doc,self.studio.project)['summary'],'')

if __name__=='__main__':unittest.main()
