"""Branch isolation, versioned approvals and durable recovery using real files."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from workflow import Course,atomic,sha,bundle_course


def design(course):
    source=course.root/'inputs/source.txt';source.parent.mkdir(exist_ok=True);source.write_text('先核对订单，再核对编码。')
    status=course.status();plan=status['plan'];plan.update(audience='新同事',performance_task='完成收货核对')
    plan['sources']=[dict(id='S',title='原始核对要求',kind='file',location='../inputs/source.txt')]
    plan['objectives']=[dict(id='O',statement='核对订单和编码',evidence='现场完成核对',criterion='信息对应')]
    plan['units']=[dict(id='U',title='核对',objective_ids=['O'],source_refs=[dict(source_id='S',locator='正文')],disposition='core',media='演示',media_reason='观察对应',activity='完成核对',teaching_method='示范后练习',teaching_reason='需要掌握实际核对动作')]
    plan['assessments']=[dict(id='A',objective_ids=['O'],task='核对编码',criteria='编码相同',feedback='逐项复核')]
    return course.save_plan(plan,status['revision'])


def approve_script(course):
    course.confirm('outline',course.status()['revision'],'QA：结构与讲法确认',actor='qa-operator')
    course.save_script('先核对订单，再核对编码。现在请完成一次核对，逐项复核。',course.status()['revision'])
    return course.confirm('script',course.status()['revision'],'QA：逐字稿确认',actor='qa-operator')


def director(course):
    folder=course.project/'director';folder.mkdir(exist_ok=True)
    styles=[]
    for i,color in enumerate(['#205c46','#293553','#a85b39']):
        p=folder/f'style-{i+1}.svg';p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="{color}"/><text x="100" y="300">核对订单</text></svg>')
        styles.append(dict(id=f'S{i+1}',title=f'风格{i+1}',rationale='匹配核对任务',motion='对象逐项对应',production_impact='使用可编辑矢量图',preview_file=str(p.relative_to(course.project))))
    return dict(basis='approved-transcript',script_sha256=course.script_sha(),script_excerpt='先核对订单，再核对编码。',
        inputs=[dict(role='transcript',path=course.script()['path']),dict(role='original',path='../inputs/source.txt')],recommended='S1',styles=styles,
        beats=[dict(id='B1',unit_id='U',script_excerpt='先核对订单，再核对编码。',picture='订单与编码并列',action='逐项连线对应',assessment_ids=['A'])])


def visual_director(course):
    data=director(course);data['style_scope']='visual'
    for style in data['styles']:
        style.pop('motion')
        style['visual']=dict(palette='品牌绿与暖白',typography='清晰中文黑体与分级字号',
            graphics='线描物件与纸张材质',atmosphere='安静、清楚、专业')
    return data


class BranchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);atomic(self.root/'project/workbench.json',{})
        self.course=Course(self.root);self.course.init('分支验收');design(self.course)
    def tearDown(self):self.tmp.cleanup()
    def branch(self,name):return self.course.select_branch(name,self.course.status()['revision'],'QA请求：'+name,actor='qa-operator')
    def video_ready(self):
        approve_script(self.course);self.branch('video');data=director(self.course);self.course.save_director(data,self.course.status()['revision'])
        self.course.select_style('S2',self.course.status()['revision'],'QA：确认S2的画面与动作',actor='qa-operator')
        return data
    def deck(self):
        p=self.root/'delivery/courseware/deck.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('<!doctype html><html lang="zh"><h1>核对订单</h1><p>请自行录制</p></html>');return p
    def test_script_cannot_precede_outline_approval(self):
        with self.assertRaises(ValueError):self.course.save_script('未经确认的正文',self.course.status()['revision'])
    def test_branch_cannot_precede_script_approval(self):
        self.course.confirm('outline',self.course.status()['revision'],'QA结构')
        self.course.save_script('先核对订单',self.course.status()['revision'])
        with self.assertRaises(ValueError):self.branch('video')
    def test_courseware_finishes_without_any_audio_or_video(self):
        approve_script(self.course);self.branch('courseware');p=self.deck()
        s=self.course.register('courseware',['../'+str(p.relative_to(self.root))],self.course.status()['revision'])
        self.assertEqual(s['stage'],'complete');self.assertEqual(s['narration_status'],'not_required')
        self.assertEqual([g['id'] for g in s['gates']],['outline','script','courseware'])
        self.assertEqual((self.root/'delivery/courseware/课程逐字稿.md').read_text(),self.course.script()['text'])
        with self.assertRaises(ValueError):self.course.require_video('script')
    def test_later_video_request_preserves_approved_script_and_deck(self):
        approve_script(self.course);self.branch('courseware');p=self.deck();self.course.register('courseware',['../delivery/courseware/deck.html'],self.course.status()['revision'])
        script_hash=self.course.script_sha();deck_hash=sha(p);receipt=copy.deepcopy(json.loads(self.course.state_file.read_text())['gates']['script'])
        s=self.branch('video');self.assertEqual(s['stage'],'style');self.assertEqual(sha(p),deck_hash);self.assertEqual(self.course.script_sha(),script_hash)
        self.assertEqual(s['narration_status'],'not_started')
        self.assertEqual(json.loads(self.course.state_file.read_text())['gates']['script'],receipt);self.assertEqual(len(s['deliveries']),1)
    def test_generated_deck_and_renamed_copy_are_rejected_as_director_input(self):
        approve_script(self.course);self.branch('courseware');p=self.deck();self.course.register('courseware',['../delivery/courseware/deck.html'],self.course.status()['revision']);self.branch('video')
        d=director(self.course);d['inputs'].append(dict(role='original',path='../delivery/courseware/deck.html'))
        with self.assertRaises(ValueError):self.course.save_director(d,self.course.status()['revision'])
        copy_path=self.root/'inputs/copied-original.html';copy_path.write_bytes(p.read_bytes());s=self.course.status();plan=s['plan'];plan['sources'].append(dict(id='COPY',title='重命名课件',kind='file',location='../inputs/copied-original.html'));self.course.save_plan(plan,s['revision'])
        self.course.confirm('outline',self.course.status()['revision'],'QA来源变更确认');self.course.confirm('script',self.course.status()['revision'],'QA本稿不变确认')
        d['inputs'][-1]['path']='../inputs/copied-original.html'
        with self.assertRaisesRegex(ValueError,'课件不能'):self.course.save_director(d,self.course.status()['revision'])
    def test_three_real_style_proposals_are_required_and_never_auto_selected(self):
        approve_script(self.course);self.branch('video');d=director(self.course)
        bad=copy.deepcopy(d);bad['styles']=bad['styles'][:2]
        with self.assertRaises(ValueError):self.course.save_director(bad,self.course.status()['revision'])
        s=self.course.save_director(d,self.course.status()['revision']);self.assertIsNone(s['selected_style'])
        with self.assertRaises(ValueError):self.course.require_video('style')
    def visual_ready(self):
        approve_script(self.course);self.branch('video');data=visual_director(self.course)
        self.course.save_director(data,self.course.status()['revision'])
        self.course.select_style('S2',self.course.status()['revision'],'QA：选择实际视觉方案，动作按内容安排',actor='qa-operator')
        return data
    def test_visual_choices_do_not_require_a_motion_option(self):
        data=self.visual_ready()
        self.assertEqual(self.course.status()['stage'],'pilot')
        bad=copy.deepcopy(data);bad['styles'][0].pop('visual');bad['styles'][0]['motion']='描线与遮罩'
        with self.assertRaisesRegex(ValueError,'视觉风格须说明'):
            self.course.save_director(bad,self.course.status()['revision'])
    def test_content_led_scene_revision_keeps_visual_choice_but_updates_export_context(self):
        data=self.visual_ready();before=self.course._video_context();proof=self.course._director_proof()
        data['beats'][0].update(picture='订单近景与核对人员同框',action='镜头推近编码，再展示核对结果')
        self.course.save_director(data,self.course.status()['revision'])
        self.assertEqual(self.course.status()['gates'][2]['status'],'confirmed')
        self.assertEqual(proof['style_sha256'],self.course._director_proof()['style_sha256'])
        self.assertNotEqual(before,self.course._video_context())
    def test_visual_pilot_allows_new_actions_without_unlocking_voice_visual_or_runtime(self):
        data=self.visual_ready()
        from test_motion_quality import linked_fixture
        doc=linked_fixture();doc['audio']=dict(voice='QA固定声音',speed=1,gain=1);doc['captionStyle']=dict(fontSize=42)
        native=self.course.project/'native';native.mkdir();(native/'scene-engine.js').write_text('// actual runtime fixture v1')
        atomic(self.course.project/'workbench.json',doc)
        self.course.register('pilot',[self.audiovisual()],self.course.status()['revision'])
        self.course.confirm('pilot',self.course.status()['revision'],'QA确认有声测试文件，非课程业务批准',actor='qa-operator')
        receipt=copy.deepcopy(json.loads(self.course.state_file.read_text())['gates']['pilot'])
        data['beats'][0].update(picture='增加流程近景',action='交接后显示记录结果')
        self.course.save_director(data,self.course.status()['revision'])
        doc['motionPlan'].update(language='mixed-content-actions',protectedEffects=['handoff','marker'])
        doc['sceneGraph']['nodes'][0]['effects'].append(dict(type='marker',startFrame=60,endFrame=75))
        atomic(self.course.project/'workbench.json',doc);self.course.require_video('pilot')
        self.assertEqual(json.loads(self.course.state_file.read_text())['gates']['pilot'],receipt)
        for key in ['voice','caption','runtime','visual','palette']:
            with self.subTest(change=key):
                changed=copy.deepcopy(doc);new_plan=copy.deepcopy(data)
                if key=='voice':changed['audio']['voice']='另一声音'
                elif key=='caption':changed['captionStyle']['fontSize']=64
                elif key=='runtime':(native/'scene-engine.js').write_text('// changed runtime')
                elif key=='palette':changed['sceneGraph']['background']='#eef1ed'
                else:new_plan['styles'][1]['visual']['typography']='另一字体体系'
                atomic(self.course.project/'workbench.json',changed);atomic(self.course.project/'director-plan.json',new_plan)
                with self.assertRaises(ValueError):self.course.require_video('pilot')
                (native/'scene-engine.js').write_text('// actual runtime fixture v1')
                atomic(self.course.project/'director-plan.json',data)
        atomic(self.course.project/'workbench.json',doc)
        frozen=self.course.relative(self.course.status()['artifacts']['pilot'][0]);frozen.write_bytes(frozen.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.course.require_video('pilot')
    def test_style_preview_change_invalidates_existing_selection(self):
        d=self.video_ready();self.assertEqual(self.course.status()['stage'],'pilot')
        self.course.relative(d['styles'][1]['preview_file']).write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>改变画面</text></svg>')
        self.assertEqual(self.course.status()['gates'][2]['status'],'stale')
    def test_freezing_exported_pilot_keeps_verified_range_for_palette_confirmation(self):
        self.visual_ready()
        from test_visual_identity import document
        doc=document()
        doc['sceneGraph']['nodes'].append(dict(id='unseen',type='rect',sceneId='B',fill='#eef1ed'))
        atomic(self.course.project/'workbench.json',doc)
        self.audiovisual();source=self.course.project/'sample.mp4'
        atomic(source.with_suffix('.json'),dict(video_sha256=sha(source),range=dict(firstFrame=0,lastFrame=30)))
        self.course.register('pilot',['sample.mp4'],self.course.status()['revision'])
        frozen=self.course.relative(self.course.status()['artifacts']['pilot'][0])
        self.assertTrue(frozen.with_suffix('.json').is_file())
        source.with_suffix('.json').unlink()
        self.course.confirm('pilot',self.course.status()['revision'],'QA确认实际有声范围，非业务批准',actor='qa-operator')
        lock=json.loads(self.course.state_file.read_text())['visual_palette']
        self.assertEqual(lock['scope'],'exported pilot source intervals')
        self.assertNotIn('#eef1ed',lock['palette']['surface'])
        gate=next(g for g in self.course.status()['gates'] if g['id']=='pilot')
        self.assertTrue(any('配色偏离已确认小样' in reason for reason in gate['reasons']))
        with self.assertRaises(ValueError):
            self.course.require_video('pilot')
    def test_mismatched_export_metadata_cannot_define_frozen_pilot_palette_range(self):
        self.visual_ready();self.audiovisual()
        source=self.course.project/'sample.mp4'
        atomic(source.with_suffix('.json'),dict(video_sha256='wrong-video',range=dict(firstFrame=0,lastFrame=30)))
        self.course.register('pilot',['sample.mp4'],self.course.status()['revision'])
        frozen=self.course.relative(self.course.status()['artifacts']['pilot'][0])
        self.assertFalse(frozen.with_suffix('.json').exists())
    def test_audio_only_cannot_pass_audiovisual_pilot(self):
        self.video_ready();p=self.course.project/'sample.wav';p.write_bytes(b'RIFF')
        with self.assertRaisesRegex(ValueError,'画面小样'):self.course.register('pilot',['sample.wav'],self.course.status()['revision'])
    def audiovisual(self):
        p=self.course.project/'sample.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=0.3',
                        '-f','lavfi','-i','sine=frequency=440:duration=0.3','-c:v','libx264','-pix_fmt','yuv420p',
                        '-c:a','aac','-shortest',str(p)],check=True)
        return 'sample.mp4'
    def test_real_audiovisual_pilot_requires_confirmation_before_full_video(self):
        self.video_ready();video=self.audiovisual()
        self.course.register('pilot',[video],self.course.status()['revision'])
        with self.assertRaises(ValueError):self.course.register('final',[video],self.course.status()['revision'])
        self.course.confirm('pilot',self.course.status()['revision'],'QA：已检查技术小样，非业务批准',actor='qa-operator')
        s=self.course.register('final',[video],self.course.status()['revision'])
        self.assertEqual(s['stage'],'complete');self.assertEqual(s['gates'][-1]['status'],'delivered')
    def test_approved_prototype_remains_valid_while_full_production_is_extended(self):
        self.video_ready();video=self.audiovisual();self.course.register('pilot',[video],self.course.status()['revision'])
        self.course.confirm('pilot',self.course.status()['revision'],'QA确认冻结的实际小样')
        receipt=copy.deepcopy(json.loads(self.course.state_file.read_text())['gates']['pilot'])
        atomic(self.course.project/'workbench.json',dict(sourceDurationFrames=900,sceneGraph=dict(nodes=[dict(id='new-scene',type='text',text='后续内容')]),captions=[]))
        (self.course.project/'source/full-production.json').write_text('{"new_content":"扩展完整课程"}')
        (self.course.project/'audio').mkdir();(self.course.project/'audio/full.wav').write_bytes(b'new full production audio fixture')
        self.course.require_video('pilot')
        self.assertEqual(self.course.status()['stage'],'final')
        self.assertEqual(json.loads(self.course.state_file.read_text())['gates']['pilot'],receipt)
    def test_unreviewed_pilot_cannot_be_approved_after_its_working_content_changes(self):
        self.video_ready();self.course.register('pilot',[self.audiovisual()],self.course.status()['revision'])
        atomic(self.course.project/'workbench.json',dict(changed='内容与实际小样不一致'))
        with self.assertRaises(ValueError):self.course.confirm('pilot',self.course.status()['revision'],'QA尝试确认过时小样')
    def test_voice_change_or_modified_frozen_pilot_invalidates_approval(self):
        self.video_ready();self.course.register('pilot',[self.audiovisual()],self.course.status()['revision'])
        self.course.confirm('pilot',self.course.status()['revision'],'QA确认小样')
        atomic(self.course.project/'workbench.json',dict(audio=dict(voice='另一位配音')))
        with self.assertRaises(ValueError):self.course.require_video('pilot')
        atomic(self.course.project/'workbench.json',{})
        frozen=self.course.relative(self.course.status()['artifacts']['pilot'][0]);frozen.write_bytes(frozen.read_bytes()+b'changed')
        with self.assertRaises(ValueError):self.course.require_video('pilot')
    def test_editing_independent_courseware_does_not_invalidate_video_confirmation(self):
        approve_script(self.course);self.branch('courseware');deck=self.deck()
        self.course.register('courseware',['../delivery/courseware/deck.html'],self.course.status()['revision'])
        self.branch('video');self.course.save_director(director(self.course),self.course.status()['revision'])
        self.course.select_style('S2',self.course.status()['revision'],'QA风格确认')
        self.course.register('pilot',[self.audiovisual()],self.course.status()['revision'])
        self.course.confirm('pilot',self.course.status()['revision'],'QA技术小样确认')
        deck.write_text('<!doctype html><html><h1>独立修改课件版式</h1></html>')
        self.assertEqual(self.course.status()['stage'],'final')
        self.assertEqual(self.course.status()['gates'][3]['status'],'confirmed')
    def test_branch_specific_video_issue_does_not_block_courseware(self):
        approve_script(self.course);s=self.course.status();plan=s['plan']
        plan['issues']=[dict(id='V',detail='尚待选定画面中的实际素材',state='open',blocks='production',gate='style',branches=['video'])]
        self.course.save_plan(plan,s['revision']);self.branch('courseware');self.deck()
        self.course.register('courseware',['../delivery/courseware/deck.html'],self.course.status()['revision'])
        self.assertEqual(self.course.status()['stage'],'complete');self.assertFalse(self.course.status()['pending'])
        self.branch('video');self.assertEqual(self.course.status()['pending'][0]['id'],'V')
        self.course.save_director(director(self.course),self.course.status()['revision'])
        with self.assertRaises(ValueError):self.course.select_style('S2',self.course.status()['revision'],'QA尝试越过未解决问题')
    def test_editing_transcript_invalidates_downstream_only(self):
        self.video_ready();self.course.save_script(self.course.script()['text']+'新增例外。',self.course.status()['revision'])
        gates={g['id']:g['status'] for g in self.course.status()['gates']};self.assertEqual(gates['outline'],'confirmed');self.assertEqual(gates['script'],'stale');self.assertEqual(gates['style'],'stale')
    def test_director_cannot_drop_an_exercise_or_invent_a_script_excerpt(self):
        approve_script(self.course);self.branch('video');d=director(self.course);d['beats'][0]['assessment_ids']=[]
        with self.assertRaisesRegex(ValueError,'练习与反馈'):self.course.save_director(d,self.course.status()['revision'])
        d=director(self.course);d['beats'][0]['script_excerpt']='原稿中没有的话'
        with self.assertRaises(ValueError):self.course.save_director(d,self.course.status()['revision'])
    def test_fresh_process_and_portable_package_recover_branch_and_receipts(self):
        self.video_ready();cli=Path(__file__).with_name('workflow.py');s=json.loads(subprocess.check_output([sys.executable,str(cli),'status',str(self.root),'--json']))
        self.assertEqual(s['branch'],'video');self.assertEqual(s['selected_style'],'S2');self.assertEqual(s['stage'],'pilot')
        bundle=self.root/'packages/course.zip';bundle_course(self.root,bundle);clone=self.root/'unpacked'
        with zipfile.ZipFile(bundle) as z:self.assertIsNone(z.testzip());z.extractall(clone)
        restored=Course(clone).status();self.assertEqual(restored['selected_style'],'S2');self.assertEqual(restored['stage'],'pilot')
    def test_concurrent_branch_change_rejects_stale_form(self):
        approve_script(self.course);revision=self.course.status()['revision'];self.branch('courseware')
        with self.assertRaises(FileExistsError):self.course.select_branch('video',revision,'过期页面')
    def test_v4_courses_keep_their_original_confirmation_chain(self):
        from workflow import LegacyCourse
        other=self.root/'legacy';atomic(other/'project/workbench.json',{});LegacyCourse(other).init()
        self.assertEqual([g['id'] for g in Course(other).status()['gates']],['source','outline','content','visual','pilot','final'])


if __name__=='__main__':unittest.main()
