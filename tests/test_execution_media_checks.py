"""Bounded 04–09 positive/negative execution fixtures; no production course data."""
import copy,json,hashlib,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from production_validation import digest,sha,inspect_extra
from author_input_checks import inspect as author
from presentation_signatures import signature,inspect as presentation
from semantic_alignment import inspect as semantic
from emphasis_checks import inspect as emphasis
from chapter_table import inspect as chapters,canonical_table,progress
from export_playback import playback


def codes(r):return {e['code'] for e in r['errors']}


def doc():
    return dict(fps=25,width=1920,height=1080,sourceDurationFrames=100,holds=[],cuts=[],captions=[],fields=[],assets=[],
        scenes=[dict(id='s',sourceStartFrame=0,sourceEndFrame=100)],media={},
        sceneGraph=dict(nodes=[dict(id='group',type='group',startFrame=0,endFrame=100,children=[
            dict(id='field',type='text',text='事实',role='subject',sceneId='s',startFrame=10,endFrame=100,x=100,y=100),
            dict(id='marker',type='rect',role='subject',sceneId='s',startFrame=10,endFrame=100,x=100,y=160,width=200,height=4,
                 motion=[dict(property='width',startFrame=10,endFrame=20,**{'from':0,'to':200},ease='linear')])])]))


def contract():
    return dict(choices=dict(flower_text='off',sound_effects='off'),requirements=dict(direction={}))


class ExecutionChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.d=doc();self.c=contract()
    def tearDown(self):self.tmp.cleanup()
    def input(self):
        self.c['requirements']['direction']['author_input']=dict(script_text='核对BI口径',terms=[dict(term='BI',first_raw_start=2,
            explanation='本企业经营数据平台',source_ref='manual:1',meaning_verified=True)],specialist_terms=[],has_sources=False)
        return self.c['requirements']['direction']['author_input']
    def test_04_term_positive_and_unverified_negative(self):
        data=self.input();self.assertTrue(author(self.p,self.d,None,'script',self.c)['ready'])
        del data['terms'][0]['explanation'];self.assertIn('TERM_UNVERIFIED',codes(author(self.p,self.d,None,'script',self.c)))
    def test_04_incomplete_source_cannot_report_full_rate(self):
        data=self.input();data.update(has_sources=True,source_coverage=dict(rate=100,source_inventory=[dict(fully_read=False)],points=[dict(source_quote='规则',reason='采用',disposition='retained',critical=True)]))
        r=author(self.p,self.d,None,'script',self.c);self.assertIn('SOURCE_COVERAGE_FALSE_RATE',codes(r));self.assertIn('SOURCE_RULE_CONDITION_MISSING',codes(r))
    def test_04_demonstration_and_early_answer_with_parent(self):
        data=self.input();data['demonstrations']=[dict(id='demo',action='加强沟通')]
        self.assertIn('DEMONSTRATION_ABSTRACT',codes(author(self.p,self.d,None,'script',self.c)))
        data['demonstrations']=[dict(id='demo-real',object_ids=['marker'],action='核对标记展开',before='宽度为零',process='按核对动作展开',after='保留核对标记')]
        self.assertTrue(author(self.p,self.d,None,'storyboard',self.c)['ready'])
        data['demonstrations']=[]
        self.d['sceneGraph']['nodes'][0]['children'].append(dict(id='answer',type='text',text='答案',startFrame=0,endFrame=100))
        data['exercises']=[dict(id='quiz',question_node_ids=['field'],material_node_ids=[],option_node_ids=[],answer_node_ids=['answer'],question_start=10,pause_cue='思考',answer_trigger=60)]
        self.assertIn('EXERCISE_ANSWER_EARLY',codes(author(self.p,self.d,None,'storyboard',self.c)))
        self.d['sceneGraph']['nodes'][0]['children'][-1]['startFrame']=60
        self.assertTrue(author(self.p,self.d,None,'storyboard',self.c)['ready'])
    def test_04_listener_absence_and_body_labels(self):
        data=self.input();data['dialogues']=[dict(id='d',speaker_id='field',addressee_ids=['marker'],speech_range=[10,30],listen_state='listening',facing_target='marker',response_action='nod',leave_after_frame=30)]
        self.d['sceneGraph']['nodes'][0]['children'][1]['endFrame']=20
        self.assertIn('DIALOGUE_LISTENER_ABSENT',codes(author(self.p,self.d,None,'storyboard',self.c)))
        data['dialogues']=[];data['diagrams']=[dict(id='diag',object_ids=['marker'],label_node_ids=['field'],meaning='核对',direction='left-to-right',frame_window=[10,20])]
        self.d['sceneGraph']['nodes'][0]['children'][0]['role']='navigation'
        self.assertIn('DIAGRAM_BODY_LABEL_MISSING',codes(author(self.p,self.d,None,'storyboard',self.c)))
    def test_05_skin_names_mirror_and_real_operation(self):
        s=dict(scene_id='s',node_ids=['group'])
        a=signature(self.d,s)
        other=copy.deepcopy(self.d)
        def alter(n):
            n['id']='new-'+n['id'];n['text']='不同文本';n['fill']='#f00';n['x']=-n.get('x',0)-n.get('width',0)
            for x in n.get('children',[]):alter(x)
        for n in other['sceneGraph']['nodes']:alter(n)
        self.assertEqual(a['sha256'],signature(other,dict(node_ids=['new-group']))['sha256'])
        other['sceneGraph']['nodes'][0]['children'][1]['motion'][0]['property']='height'
        self.assertNotEqual(a['sha256'],signature(other,dict(node_ids=['new-group']))['sha256'])
    def test_05_duplicate_is_blocking_not_method_name(self):
        self.c['requirements']['direction'].update(scenes=[dict(scene_id='a',node_ids=['group']),dict(scene_id='b',node_ids=['group'])],presentation=dict(chapters=[dict(teaching_task='task',primary_structure='map')],scenes=[]))
        self.assertIn('DUPLICATE_PRESENTATION',codes(presentation(self.p,self.d,None,'storyboard',self.c)))
    def aligned(self):
        a=self.p/'voice.wav';a.write_bytes(b'current source audio identity')
        text='一千随后一千';rows=[(0,2,10,20,'w1'),(2,4,20,30,'w2'),(4,6,40,50,'w3')]
        mapping=dict(audio_sha256=sha(a),segments=[dict(id='s',narration=text,
            words=[dict(word_id=w,start_frame=f,end_frame=z,alignment_kind='ASR-exact-text') for x,y,f,z,w in rows],
            char_map=[dict(raw_start=x,raw_end=y,start_frame=f,end_frame=z,word_ids=[w],alignment_kind='ASR-exact-text') for x,y,f,z,w in rows])])
        event=dict(id='e',segment_id='s',quote='一千',raw_span=[4,6],occurrence=1,trigger_frame=40,result_frame=40,node_ids=['field'],semantic_anchor=dict(word_ids=['w3'],raw_span=[4,6]))
        data=dict(audio_path='voice.wav',audio_sha256=sha(a),mapping=mapping,events=[event]);self.c['requirements']['direction']['semantic_alignment']=data
        self.d['sceneGraph']['nodes'][0]['children'][0]['startFrame']=40
        return data,event
    def test_06_exact_occurrence_and_current_audio(self):
        data,e=self.aligned();self.assertTrue(semantic(self.p,self.d,None,'storyboard',self.c)['ready'])
        e['occurrence']=0;self.assertIn('SEMANTIC_ANCHOR_MISSING',codes(semantic(self.p,self.d,None,'storyboard',self.c)))
        e['occurrence']=1;(self.p/'voice.wav').write_bytes(b'changed')
        self.assertIn('SEMANTIC_AUDIO_STALE',codes(semantic(self.p,self.d,None,'storyboard',self.c)))
    def test_06_early_child_and_fake_nearest_cue(self):
        data,e=self.aligned();self.d['sceneGraph']['nodes'][0]['children'][0]['startFrame']=0
        self.assertIn('SEMANTIC_FIELD_TIME_MISMATCH',codes(semantic(self.p,self.d,None,'storyboard',self.c)))
        self.d['sceneGraph']['nodes'][0]['children'][0]['startFrame']=40;e['technical_anchor']=dict(cueId='wrong',phrase='一千',atFrame=40)
        self.d['captions']=[dict(id='wrong',text='别的词',startFrame=39,endFrame=51)]
        self.assertIn('SEMANTIC_TECHNICAL_ANCHOR_INVALID',codes(semantic(self.p,self.d,None,'storyboard',self.c)))
    def flower(self):
        self.c['choices']['flower_text']='on'
        e=dict(id='f',requirement_id='focus',quote='事实',purpose='强调事实',emphasis_text='事实',visual_treatment='字组和核对标记一体落位',
            semantic_anchor=dict(raw_span=[0,2]),sound_or_silence_reason='需要读图所以静音',text_node_ids=['field'],marker_node_ids=['marker'],target_node_ids=['group'],
            animation_start=10,animation_end=20,landing_frame=20,reading_window=[20,90])
        self.d['readingPlan']=dict(groups=[dict(id='g',sceneId='s',textIds=['field'],window=dict(startFrame=20,endFrame=90),minimumStableSeconds=1.2)])
        self.c['requirements']['emphasis']=dict(events=[e]);return e
    def test_07_special_treatment_and_plain_font_negative(self):
        e=self.flower();self.assertTrue(emphasis(self.p,self.d,None,'storyboard',self.c)['ready'])
        self.d['sceneGraph']['nodes'][0]['children'][1]['motion']=[]
        self.d['sceneGraph']['nodes'][0]['children'][0]['fontFamily']='CourseHeavy'
        self.assertIn('EMPHASIS_UNIMPLEMENTED',codes(emphasis(self.p,self.d,None,'storyboard',self.c)))
    def test_07_ancestor_motion_and_negation(self):
        e=self.flower();self.d['sceneGraph']['nodes'][0]['motion']=[dict(property='x',startFrame=20,endFrame=89,**{'from':0,'to':10})]
        self.assertIn('EMPHASIS_READING_SHORT',codes(emphasis(self.p,self.d,None,'storyboard',self.c)))
        e.update(quote='不能跳过核实',emphasis_text='跳过核实',protected_tokens=[])
        self.assertIn('EMPHASIS_SEMANTIC_CHANGED',codes(emphasis(self.p,self.d,None,'storyboard',self.c)))
    def test_07_runtime_window_is_one_continuous_interval_not_first_to_last(self):
        from reading_pacing import RuntimeAudit
        self.d['readingPolicy']=dict(required=True)
        self.d['readingPlan']=dict(schema='course-reading-plan/1',referenceTextIds=[],groups=[dict(id='g',sceneId='s',textIds=['field'],task='Read facts',window=dict(startFrame=10,endFrame=100),minimumStableSeconds=1.2,retention=dict(mode='replace',reason='next task'))])
        audit=RuntimeAudit(self.d,0,100)
        for f in range(100):
            receipts=[dict(objectId='field',text='事实',alpha=1,complete=True,inFrame=True,occluded=False,bounds=[100,100,180,148])] if 10<=f<40 or 60<=f<100 else []
            audit.consume(f,f,receipts)
        r=audit.result();self.assertEqual(r['groups'][0]['actualStableWindow'],[60,100]);self.assertEqual(r['groups'][0]['actualStableSeconds'],1.6)
    def test_07_empty_enabled_and_selected_off_are_distinct(self):
        self.c['choices']['flower_text']='on';self.c['requirements']['emphasis']=dict(required=False,events=[])
        self.assertIn('EMPHASIS_UNIMPLEMENTED',codes(emphasis(self.p,self.d,None,'storyboard',self.c)))
        self.c['choices']['flower_text']='off';self.assertTrue(emphasis(self.p,self.d,None,'storyboard',self.c)['ready'])
    def nav(self):
        self.d['holds']=[dict(sourceFrame=40,frames=20)];self.d['cuts']=[dict(startFrame=60,endFrame=80)]
        rows=[dict(chapter_id='c1',label='交接',source_start=0,source_end=50,body_visible_windows=[[0,100]],nav_node_ids=['nav1']),dict(chapter_id='c2',label='核对',source_start=50,source_end=100,body_visible_windows=[[0,100]],nav_node_ids=['nav2'])]
        rows=canonical_table(self.d,rows);self.d['chapterTable']=rows
        for j,r in enumerate(rows,1):
            self.d['sceneGraph']['nodes'].append(dict(id='nav'+str(j),type='group',role='navigation',startFrame=0,endFrame=100,children=[
                dict(id='label'+str(j),type='text',text=r['label'],role='navigation',startFrame=0,endFrame=100),
                dict(id='fill'+str(j),type='rect',role='navigation',startFrame=0,endFrame=100,width=0,navigation=dict(kind='progress-fill',chapter_id=r['chapter_id'],segment_width=200),motion=[dict(property='width',startFrame=r['source_start'],endFrame=r['source_end'],**{'from':0,'to':200},ease='linear')])]))
        self.c['requirements']['chapters']=dict(chapter_table=rows,table_sha256=digest(rows),label_mode='names',allow_state_words=False)
        return rows
    def test_09_cut_hold_seek_and_unique_consumers(self):
        rows=self.nav();self.assertEqual((rows[0]['display_end'],rows[1]['display_end']),(70,100))
        self.assertAlmostEqual(progress(rows[0],50),5/7)
        self.assertTrue(chapters(self.p,self.d,None,'storyboard',self.c)['ready'])
        self.assertEqual(playback(self.d)['chapters'][1]['start'],70/25)
        self.d['chapterTable'][1]['display_start']=50
        self.assertIn('CHAPTER_TABLE_STALE',codes(chapters(self.p,self.d,None,'storyboard',self.c)))
    def test_09_static_fake_parent_and_status_words_fail(self):
        self.nav();node=self.d['sceneGraph']['nodes'][-1]
        node['children'][0]['text']='已学 核对';node['children'][1]['motion']=[];node['motion']=[dict(property='x',startFrame=0,endFrame=100,**{'from':0,'to':1})]
        r=chapters(self.p,self.d,None,'storyboard',self.c)
        self.assertIn('NAV_CHOICE_IGNORED',codes(r));self.assertIn('NAV_TIME_MISMATCH',codes(r))
    def test_aggregator_context_fail_closed(self):
        self.d['media']['audio']='unavailable-current-voice.wav'
        for name,obj in [('doc.json',self.d),('contract.json',self.c)]:
            (self.p/name).write_text(json.dumps(obj))
        r=inspect_extra(self.p,dict(current_document='doc.json',current_contract='contract.json',purpose='storyboard'))
        self.assertFalse(r['ready']);self.assertIn('SEMANTIC_ANCHOR_MISSING',codes(r));self.assertIn('CHAPTER_TABLE_STALE',codes(r))

if __name__=='__main__':unittest.main()
