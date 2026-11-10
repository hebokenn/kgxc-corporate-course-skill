"""Synthetic regressions only: no private course text, media or model calls."""
import copy,json,sys,tempfile,unittest,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from ordered_reveals import plan,inspect,encoded_presence
from intro_pacing import inspect as intro,timing_bindings,frozen_intervals
from production_validation import sha

def codes(r):return {x['code']for x in r['errors']}
def fixture(times=(10,30,50)):
 texts=['核实清单。','识别风险。','落实行动。'];words=[];chars=[];events=[];nodes=[];rows=[]
 for i,(s,f)in enumerate(zip(texts,times)):
  a=i*5;z=a+5;wid='w'+str(i);eid='e'+str(i);nid='n'+str(i)
  words.append(dict(word_id=wid,start_frame=f,end_frame=f+5,alignment_kind='actual-word'));chars.append(dict(raw_start=a,raw_end=z,word_ids=[wid],alignment_kind='actual-word'))
  events.append(dict(id=eid,segment_id='s',paragraph_id='p1',sentence=s,sentence_span=[a,z],quote=s,raw_span=[a,z],occurrence=0,trigger_frame=f))
  nodes.append(dict(id=nid,type='text',text=str(i+1)+' '+s,x=4,y=20+i*30,startFrame=f,endFrame=100,orderedList=dict(group_id='g',index=i+1)))
  rows.append(dict(number=i+1,event_id=eid,node_id=nid,stable_frame=f+1,probe=dict(region=[4,20+i*30,10,10],rgb=[255,0,0],tolerance=30,minimum_pixels=70)))
 m=dict(segments=[dict(id='s',paragraph_id='p1',narration=''.join(texts),words=words,char_map=chars)])
 g=[dict(id='g',mode='sequential',layout='vertical',end_frame=100,rows=rows)]
 d=dict(fps=30,sourceDurationFrames=100,introFrames=0,scenes=[dict(id='s',sourceStartFrame=0,sourceEndFrame=100)],media={},sceneGraph=dict(nodes=nodes))
 return m,g,events,d

class OrderTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def cfg(self,times=(10,30,50)):
  m,g,e,d=fixture(times);(self.p/'script').write_text(m['segments'][0]['narration']);(self.p/'voice').write_bytes(b'synthetic identity only')
  m.update(script_sha256=sha(self.p/'script'),audio_sha256=sha(self.p/'voice'));d['media']['audio']='voice';d['orderedRevealGroups']=g
  c=dict(requirements=dict(direction=dict(semantic_alignment=dict(mapping=m,events=e,script_path='script',script_sha256=m['script_sha256'],audio_path='voice',audio_sha256=m['audio_sha256']))));return m,g,e,d,c
 def test_exact_and_monotonic(self):
  m,g,e,d=fixture();self.assertEqual([r['trigger_frame']for r in plan(m,g,e)[0]['rows']],[10,30,50])
 def test_three_reported_failure_shapes(self):
  for ts in [(651,1247,346),(681,1265,349),(358,2876,2151)]:
   m,g,e,d=fixture(ts);g[0]['end_frame']=4000
   with self.subTest(times=ts),self.assertRaises(ValueError):plan(m,g,e)
 def test_max_clamp_rejected(self):
  m,g,e,d=fixture((20,10,30));e[1]['trigger_frame']=21
  with self.assertRaises(ValueError):plan(m,g,e)
 def test_time_sort_rejected(self):
  m,g,e,d=fixture((20,10,30));g[0]['rows'][0],g[0]['rows'][1]=g[0]['rows'][1],g[0]['rows'][0]
  with self.assertRaises(ValueError):plan(m,g,e)
 def test_specific_sentence_paragraph_occurrence_required(self):
  for key in ['sentence_span','sentence','paragraph_id','occurrence']:
   m,g,e,d=fixture();e[0].pop(key)
   with self.subTest(key=key),self.assertRaises(ValueError):plan(m,g,e)
 def test_generic_first_phrase_rejected(self):
  m,g,e,d=fixture();m['segments'][0]['narration']='这节课。识别风险。落实行动。';e[0].update(sentence='这节课。',sentence_span=[0,4],quote='这节课',raw_span=[0,3])
  with self.assertRaises(ValueError):plan(m,g,e)
 def test_proportional_and_first_match_alignment_rejected(self):
  for kind in ['proportional','first-match','max-clamp','duration-ratio']:
   m,g,e,d=fixture();m['segments'][0]['char_map'][0]['alignment_kind']=kind
   with self.subTest(kind=kind),self.assertRaises(ValueError):plan(m,g,e)
 def test_script_change_invalidates(self):
  m,g,e,d,c=self.cfg();self.assertTrue(inspect(self.p,d,None,'storyboard',c)['ready']);(self.p/'script').write_text('新开场'+m['segments'][0]['narration'])
  self.assertIn('REVEAL_SCRIPT_STALE',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_audio_change_invalidates(self):
  m,g,e,d,c=self.cfg();(self.p/'voice').write_bytes(b'new audio');self.assertIn('REVEAL_AUDIO_STALE',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_simultaneous_is_not_sequential(self):
  m,g,e,d,c=self.cfg((30,10,20));g[0]['mode']='simultaneous'
  for n in d['sceneGraph']['nodes']:n['startFrame']=0
  self.assertTrue(inspect(self.p,d,None,'storyboard',c)['ready']);d['sceneGraph']['nodes'][1]['startFrame']=2
  self.assertIn('REVEAL_NOT_SIMULTANEOUS',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_layout_not_repaired_by_renumbering(self):
  m,g,e,d,c=self.cfg();d['sceneGraph']['nodes'][1]['y']=95
  self.assertIn('REVEAL_LAYOUT_ORDER',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_previous_rows_retained(self):
  m,g,e,d,c=self.cfg();d['sceneGraph']['nodes'][0]['endFrame']=25
  self.assertIn('REVEAL_RETENTION_MISSING',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_annotation_requires_group(self):
  m,g,e,d,c=self.cfg();d['orderedRevealGroups']=[]
  self.assertIn('REVEAL_GROUP_MISSING',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_sound_follows_new_event(self):
  m,g,e,d,c=self.cfg();g[0]['rows'][0].update(sound_event_id='a',sound_required=True);c['requirements']['sfx']=dict(plan_path=dict(events=[dict(id='a',frame=9,visual_event_id='e0')]))
  self.assertIn('REVEAL_SOUND_MISMATCH',codes(inspect(self.p,d,None,'storyboard',c)));c['requirements']['sfx']['plan_path']['events'][0]['frame']=10
  self.assertTrue(inspect(self.p,d,None,'storyboard',c)['ready'])
 def test_required_sound_missing(self):
  m,g,e,d,c=self.cfg();g[0]['rows'][0]['sound_required']=True
  self.assertIn('REVEAL_SOUND_MISSING',codes(inspect(self.p,d,None,'storyboard',c)))
 def test_prevoice_defers_media_only(self):
  m,g,e,d=fixture();d['orderedRevealGroups']=g;self.assertTrue(inspect(self.p,d,None,'storyboard',{})['ready']);g[0]['rows'][1]['number']=3
  self.assertIn('REVEAL_LAYOUT_INVALID',codes(inspect(self.p,d,None,'storyboard',{})))
 def test_aggregate_gate_executes_order_checker(self):
  from production_validation import inspect_extra
  m,g,e,d,c=self.cfg();d['sceneGraph']['nodes'][1]['y']=95
  result=inspect_extra(self.p,d,None,'storyboard',c)
  self.assertIn('ordered_reveals',result['checks']);self.assertIn('intro_pacing',result['checks']);self.assertIn('REVEAL_LAYOUT_ORDER',codes(result))
 def test_cli_checks_both_related_lessons(self):
  m,g,e,d,c=self.cfg();(self.p/'production-contract.json').write_text(json.dumps(c));one=self.p/'one.json';two=self.p/'two.json';one.write_text(json.dumps(d));d['sceneGraph']['nodes'][1]['startFrame']=0;two.write_text(json.dumps(d))
  r=subprocess.run([sys.executable,str(ROOT/'skills/corporate-training-motion/scripts/course_tools.py'),'reveal-check','--project',str(self.p),'--spec',str(one),str(two)],capture_output=True,text=True)
  self.assertEqual(r.returncode,2,r.stderr);data=json.loads(r.stdout);self.assertEqual(len(data['lessons']),2);self.assertTrue(data['lessons'][0]['result']['ready']);self.assertFalse(data['lessons'][1]['result']['ready'])
 def test_absent_groups_does_not_claim_ocr(self):
  d=fixture()[3]
  for n in d['sceneGraph']['nodes']:n.pop('orderedList')
  self.assertTrue(inspect(self.p,d,None,'final',{})['ready'])

class CompilerTests(unittest.TestCase):
 def build(self,beats,mode='sequential'):
  from teaching_modules import Build
  return Build(dict(id='m',module='whiteboard',sceneId='s',startFrame=0,endFrame=100,beats=beats,data=dict(labels=['甲','乙','丙'],numberedMode=mode)),dict(id='s',sourceStartFrame=0,sourceEndFrame=100)).build()
 def test_shared_compiler_rejects_reverse_beats(self):
  with self.assertRaises(ValueError):self.build([dict(startFrame=f,endFrame=f+5)for f in [10,30,5]])
 def test_shared_compiler_does_not_reuse_last_beat(self):
  with self.assertRaises(ValueError):self.build([dict(startFrame=10,endFrame=20)])
 def test_explicit_full_page_uses_one_actual_beat(self):
  nodes=self.build([dict(startFrame=10,endFrame=20)],'simultaneous');steps=[n for n in nodes if '-step-'in n['id']];self.assertEqual(len(steps),3);self.assertEqual({n['effects'][0]['startFrame']for n in steps},{10})

class IntroTests(unittest.TestCase):
 def doc(self,n=45,fps=30):
  d=dict(fps=fps,introFrames=n,sourceDurationFrames=600,bodyEndFrame=580,captions=[],chapterTable=[],audio=dict(speed=.9),media={},holds=[],cuts=[])
  d['introPolicy']=dict(max_seconds=2,max_static_seconds=2,first_speech_source_frame=n,max_speech_gap_seconds=.1,source_ref='qa-user-choice',reason='synthetic short intro');d['introPolicy']['timing_bindings']=timing_bindings(d);return d
 def test_selected_budget_at_multiple_fps(self):
  for fps in [24,30,60]:self.assertTrue(intro('.',self.doc(round(fps*1.5),fps),None,'storyboard',{})['ready'])
 def test_old_371_frame_packaging_is_rejected(self):self.assertIn('INTRO_TOO_LONG',codes(intro('.',self.doc(371),None,'storyboard',{})))
 def test_short_card_remaining_wait_rejected(self):
  d=self.doc();d['introPolicy']['first_speech_source_frame']=200;self.assertIn('INTRO_SPEECH_DELAY',codes(intro('.',d,None,'storyboard',{})))
 def test_hold_counts_toward_whole_intro(self):
  d=self.doc();d['holds']=[dict(sourceFrame=20,frames=150)];d['introPolicy']['timing_bindings']=timing_bindings(d)
  self.assertIn('INTRO_TOO_LONG',codes(intro('.',d,None,'storyboard',{})))
 def test_all_timing_dependencies_become_stale(self):
  for key,value in [('introFrames',30),('captions',[dict(startFrame=20)]),('chapterTable',[dict(start=30)]),('audio',dict(speed=.81)),('sfxEvents',[dict(frame=20)]),('sourceDurationFrames',550)]:
   d=self.doc();d[key]=value
   with self.subTest(key=key):self.assertIn('INTRO_TIMELINE_STALE',codes(intro('.',d,None,'storyboard',{})))
 def test_no_global_two_second_hard_limit(self):
  d=self.doc(150);d.pop('introPolicy');self.assertTrue(intro('.',d,None,'storyboard',{})['ready']);d=self.doc(150);d['introPolicy'].update(max_seconds=6,max_static_seconds=6);self.assertTrue(intro('.',d,None,'storyboard',{})['ready'])

@unittest.skipUnless(shutil.which('ffmpeg')and shutil.which('ffprobe'),'real media tools required')
class EncodedTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def make(self,name,times=(10,30,50)):
  f='color=c=white:s=160x120:r=30:d=4'
  for i,t in enumerate(times):f+=f",drawbox=x=4:y={20+i*30}:w=10:h=10:c=red:t=fill:enable='gte(n,{t})'"
  p=self.p/name;subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i',f,'-c:v','libx264','-pix_fmt','yuv420p',str(p)],check=True);return p
 def test_actual_before_at_stable_pixels(self):
  m,g,e,d=fixture();self.assertEqual(len(encoded_presence(self.make('ok.mp4'),plan(m,g,e))['observations']),9)
 def test_correct_final_page_does_not_hide_early_third(self):
  m,g,e,d=fixture()
  with self.assertRaisesRegex(ValueError,'presence/order'):encoded_presence(self.make('bad.mp4',(10,30,5)),plan(m,g,e))
 def test_invalid_probe_rejected(self):
  m,g,e,d=fixture();g[0]['rows'][0]['probe']['region']=[0,0,999,100]
  with self.assertRaisesRegex(ValueError,'probe'):encoded_presence(self.make('ok.mp4'),plan(m,g,e))
 def test_frame_counter_survives_stream_metadata_change(self):
  from media_frames import extract
  from production_validation import decoded_frame_hashes
  from PIL import Image
  parts=[]
  for i,(color,sar)in enumerate([('red','1/1'),('blue','2/1')]):
   p=self.p/('part'+str(i)+'.mp4');subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={color}:s=160x120:r=4:d=1','-vf','setsar='+sar,'-c:v','libx264','-pix_fmt','yuv420p',str(p)],check=True);parts.append(p)
  listing=self.p/'concat';listing.write_text(''.join("file '"+str(p)+"'\n"for p in parts));video=self.p/'metadata.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(video)],check=True)
  image=self.p/'six.png';extract(video,6,image,width=None);rgb=Image.open(image).getpixel((20,20));self.assertGreater(rgb[2],200);self.assertLess(rgb[0],40)
  self.assertEqual(set(decoded_frame_hashes(video,[0,6])),{0,6})
 def test_actual_fps_cannot_be_relabelled_to_hide_wait(self):
  video=self.make('fps.mp4');d=IntroTests().doc(45,60);self.assertIn('INTRO_MEDIA_UNVERIFIED',codes(intro(self.p,d,video,'final',{})))
 def test_actual_static_title_measurement(self):
  p=self.make('still.mp4',(0,0,0));d=IntroTests().doc(90);d['introPolicy'].update(max_seconds=4,max_static_seconds=.5)
  self.assertIn('INTRO_STATIC_HOLD_LONG',codes(intro(self.p,d,p,'final',{})));self.assertGreater(frozen_intervals(p,90,30)[0]['duration_seconds'],2)

if __name__=='__main__':unittest.main()
