"""Real default CLI sound path: explicit events, stereo PCM, canonical receipts.

These fixtures never approve listening or a course. Required policy exercises the
same public sfx-plan/mix commands used by producers, not a substitute mixer.
"""
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile,unittest,wave,uuid
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WB=ROOT/'skills/corporate-training-motion/workbench';CLI=ROOT/'skills/corporate-training-motion/scripts/course_tools.py'
sys.path[:0]=[str(WB),str(ROOT/'skills/corporate-training-motion/scripts')]
from backend import atomic,read
from sound import make_plan,mix,sha,RATE,source_timeline
from production_validation import digest
from sfx_evidence import inspect as inspect_sfx,decode
from execution_requirements import update
from handoff_contract import create,submit
from evidence_versions import file_ref


def pcm(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(data.shape[1]);f.setframerate(RATE);f.setsampwidth(2);f.writeframes((np.clip(data,-1,1)*32767).astype('<i2').tobytes())


class DefaultSoundExecution(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)/'course/project';self.p.mkdir(parents=True)
        self.doc=dict(status='draft',fps=24,sourceDurationFrames=96,scenes=[dict(id='S',sourceStartFrame=0,sourceEndFrame=96)],holds=[],cuts=[],
            sceneGraph=dict(nodes=[dict(id='subject',type='rect',startFrame=0,endFrame=96,width=40,height=20,motion=[dict(property='width',startFrame=22,endFrame=24,**{'from':0,'to':40},ease='linear'),dict(property='width',startFrame=46,endFrame=48,**{'from':40,'to':80},ease='linear')])]),
            motionPlan=dict(beats=[dict(id='place-a',kind='action',startFrame=22,endFrame=24,objectIds=['subject']),dict(id='place-b',kind='action',startFrame=46,endFrame=48,objectIds=['subject'])]),media={})
        atomic(self.p/'workbench.json',dict(status='draft',fps=24));atomic(self.p/'source/spec.json',self.doc)
        atomic(self.p/'production-contract.json',dict(choices=dict(sound_effects='native'),requirements=dict(sfx=dict(required=True,palette='teaching-native-v1',events=[],review={}))))
        row=dict(id='sound',source_type='user_current',source_ref='source/synthetic-request.txt',original_quote='Use exact native sound on the two actual landings; preserve dry stereo.',stage='pilot',scope=dict(scenes=['S'],feature='sfx'),required_behavior='Native timed stereo effects',acceptance_checks=['source-presence'],implementation_refs=[],evidence_refs=[],status='not_started',changes=[])
        (self.p/'source/synthetic-request.txt').write_text(row['original_quote']);self.assertTrue(update(self.p,[row])['ready'])
        t=np.arange(4*RATE+17)/RATE
        self.dry=np.column_stack([.006*np.sin(2*np.pi*(131*t+13*t*t)),.007*np.sin(2*np.pi*(223*t+7*t*t))]);pcm(self.p/'audio/dry.wav',self.dry)
        self.events=dict(task_id='sound-default-cli',events=[dict(id='a',frame=24,role='appear',visual_event_id='place-a',visual_phase='result',trigger_kind='peak',group_id='pair',equal_options=True),dict(id='b',frame=48,role='appear',visual_event_id='place-b',visual_phase='result',trigger_kind='peak',group_id='pair',equal_options=True)])
        atomic(self.p/'source/events.json',self.events)
        self.task=dict(task_id='sound-default-cli',requirement_ids=['sound'],inputs=[file_ref(self.p,'production-contract.json'),file_ref(self.p,'source/spec.json'),file_ref(self.p,'audio/dry.wav')],owned_scope=['audio','source/spec.json','work/implementation-bindings/sound-default-cli'],forbidden_scope=['production-contract.json'],quotes={'sound':row['original_quote']},actual_objects=['subject'],choices={'sound_effects':'native'},return_files=['audio/current-execution-receipt.json','source/spec.json'],required_checks=['source-presence'],purpose='pilot',issue_ids=[],implementation_outputs=['native_sfx'])
        atomic(self.p/'source/task.json',self.task)
        dispatch=subprocess.run([sys.executable,str(ROOT/'skills/corporate-training-motion/scripts/execution_tools.py'),'dispatch','--project',str(self.p),'--input',str(self.p/'source/task.json')],capture_output=True,text=True)
        self.assertEqual(dispatch.returncode,0,dispatch.stdout+dispatch.stderr)
    def cli(self,*args,success=True):
        run=subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True)
        if success:self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        else:self.assertNotEqual(run.returncode,0,run.stdout+run.stderr)
        return run
    def plan(self):return json.loads(self.cli('sfx-plan',self.p,'--events',self.p/'source/events.json','--spec','source/spec.json').stdout)
    def mix(self,plan=None,out='audio/current.wav'):
        return json.loads(self.cli('sfx-mix',self.p,'--plan',self.p/(plan or 'audio/sfx-plan.json'),'--narration','audio/dry.wav','--out',out,'--bind').stdout)
    def test_cli_plan_mix_current_receipt_stereo_and_B_signal(self):
        before=sha(self.p/'audio/dry.wav');planned=self.plan();initial=sha(self.p/'audio/sfx-plan.json')
        self.assertEqual(planned['plan']['events'][0]['visual_event_id'],'place-a');self.assertFalse(planned['verified'])
        receipt=self.mix();self.assertEqual(sha(self.p/'audio/dry.wav'),before);self.assertEqual(sha(self.p/'audio/sfx-plan.json'),initial)
        self.assertEqual(receipt['samples'],len(self.dry));self.assertEqual((receipt['dry_channels'],receipt['output_channels']),(2,2))
        self.assertFalse(receipt['narration_timeline_changed']);self.assertFalse(receipt['hearing_review'])
        with wave.open(str(self.p/'audio/current.wav'),'rb') as f:self.assertEqual((f.getnframes(),f.getnchannels()),(len(self.dry),2))
        contract=read(self.p/'production-contract.json');req=contract['requirements']['sfx'];prepared=read(self.p/req['plan_path'])
        self.assertNotEqual(req['plan_path'],'audio/sfx-plan.json');self.assertEqual(req['status'],'implemented_unverified');self.assertEqual(req['review'],{})
        self.assertTrue(all(e['timing_contract']['declared_before_mix'] for e in prepared['events']))
        self.assertEqual({e['gain'] for e in prepared['events']},{planned['plan']['events'][0]['gain']})
        self.assertEqual(prepared['dry_sha256'],before)
        side=read(self.p/'audio/current.json');canonical=read(self.p/req['receipt'])
        self.assertEqual(canonical['plan_sha256'],digest(prepared));self.assertEqual(side['plan_sha256'],sha(self.p/req['plan_path']))
        video=self.p/'current.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=64x64:r=24:d=4','-i',str(self.p/'audio/current.wav'),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(video)],check=True,capture_output=True)
        # Technical current evidence is explicit; no listening record is fabricated.
        req['review']=dict(video_sha256=sha(video),mix_sha256=receipt['mix_sha256'])
        result=inspect_sfx(self.p,read(self.p/'source/spec.json'),video,'final',contract)
        errors={e['code'] for e in result['errors']};self.assertEqual(errors,{'AUDIO_REVIEW_UNVERIFIED'},result)
        self.assertEqual({e['status'] for e in result['details']['signal_results']},{'detected'})
        atomic(self.p/'qa/source-presence.json',result)
        dispatch=read(self.p/'work/handoffs/sound-default-cli.json')
        returned=dict(task_id=dispatch['task_id'],dispatch_sha256=sha(self.p/'work/handoffs/sound-default-cli.json'),requirement_ids=dispatch['requirement_ids'],output_paths=[file_ref(self.p,receipt['receipt_path']),file_ref(self.p,'source/spec.json')],object_bindings=[dict(event_id='a',quote=self.task['quotes']['sound'],object_ids=['subject'],allowed_types=['rect'],frame_range=[22,49])],checks_run=[dict(id='source-presence',status='passed',evidence_ref='qa/source-presence.json')],evidence_refs=[file_ref(self.p,'qa/source-presence.json')],unresolved_items=[],issue_ids=[])
        atomic(self.p/'source/return.json',returned)
        return_cli=subprocess.run([sys.executable,str(ROOT/'skills/corporate-training-motion/scripts/execution_tools.py'),'return','--project',str(self.p),'--input',str(self.p/'source/return.json'),'--document',str(self.p/'source/spec.json')],capture_output=True,text=True)
        self.assertEqual(return_cli.returncode,0,return_cli.stdout+return_cli.stderr)
        current=read(self.p/'production-contract.json');self.assertEqual(current['obligations'][0]['status'],'implemented_unverified');self.assertEqual(current['requirements']['sfx']['review'],{})
        absent=self.p/'absent.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=64x64:r=24:d=4','-i',str(self.p/'audio/dry.wav'),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(absent)],check=True,capture_output=True)
        missing_contract=copy.deepcopy(contract);missing_contract['requirements']['sfx']['review']['video_sha256']=sha(absent)
        missing=inspect_sfx(self.p,read(self.p/'source/spec.json'),absent,'final',missing_contract)
        self.assertIn('SFX_NOT_IN_ENCODE',{e['code'] for e in missing['errors']});atomic(self.p/'qa/absent-source-signal.json',missing)
        # Actual left/right source balance is preserved instead of a mono collapse.
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(self.p/'audio/current-sfx.wav'),'-f','f64le','-'])
        channels=np.frombuffer(raw,dtype='<f8').reshape(-1,2);self.assertGreater(np.max(np.abs(channels[:,0]-channels[:,1])),1e-8)
        if os.environ.get('EXECUTION_SOUND_EVIDENCE_DIR'):
            dest=Path(os.environ['EXECUTION_SOUND_EVIDENCE_DIR'])/('cli-positive-'+uuid.uuid4().hex[:12]);shutil.copytree(self.p,dest);atomic(dest/'B-technical-inspection.json',result)
    def test_missing_or_false_visual_mapping_fails_before_plan(self):
        for change in [dict(visual_event_id='missing'),dict(frame=23),dict(group_id='')]:
            e=copy.deepcopy(self.events);e['events'][0].update(change);atomic(self.p/'source/events.json',e)
            run=self.cli('sfx-plan',self.p,'--events',self.p/'source/events.json','--spec','source/spec.json',success=False)
            self.assertIn('SFX_',run.stderr);self.assertFalse((self.p/'audio/sfx-plan.json').exists())
    def test_mismatch_equal_options_rejected(self):
        events=copy.deepcopy(self.events);events['events'][1]['gainDb']=-3;atomic(self.p/'source/events.json',events)
        run=self.cli('sfx-plan',self.p,'--events',self.p/'source/events.json','--spec','source/spec.json',success=False)
        self.assertIn('SFX_OPTION_WEIGHT_MISMATCH',run.stderr)
    def test_stale_source_duration_tail_and_existing_outputs_rejected(self):
        self.plan();before=sha(self.p/'audio/sfx-plan.json')
        self.cli('sfx-plan',self.p,'--events',self.p/'source/events.json','--spec','source/spec.json',success=False);self.assertEqual(sha(self.p/'audio/sfx-plan.json'),before)
        pcm(self.p/'audio/dry.wav',np.zeros((6*RATE,2)))
        run=self.cli('sfx-mix',self.p,'--plan',self.p/'audio/sfx-plan.json','--narration','audio/dry.wav','--out','audio/too-long.wav',success=False)
        self.assertIn('SFX_NARRATION_DURATION_MISMATCH',run.stderr);self.assertFalse((self.p/'audio/too-long.wav').exists())
        pcm(self.p/'audio/dry.wav',self.dry);receipt=self.mix()
        output_hash=sha(self.p/'audio/current.wav');run=self.cli('sfx-mix',self.p,'--plan',self.p/receipt['plan_path'],'--narration','audio/dry.wav','--out','audio/current.wav',success=False)
        self.assertIn('SFX_OUTPUT_EXISTS',run.stderr);self.assertEqual(sha(self.p/'audio/current.wav'),output_hash)
    def test_24_and_2997_spec_fps_are_actual_not_forced_thirty(self):
        self.assertEqual(source_timeline(self.p,'source/spec.json')[0]['fps'],24)
        self.doc['fps']=29.97;self.doc['sourceDurationFrames']=120;atomic(self.p/'source/spec.json',self.doc)
        data=self.plan()['plan'];self.assertEqual(data['fps'],29.97)
        self.assertEqual(data['events'][0]['peak_or_onset_frame'],24)
        result=self.mix();self.assertEqual(result['samples'],len(self.dry))
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(self.p/'audio/current-sfx.wav'),'-ac','1','-f','f64le','-'])
        stem=np.frombuffer(raw,dtype='<f8');expected=round(24*RATE/29.97)
        self.assertLessEqual(abs(int(np.argmax(np.abs(stem[:RATE])))-expected),1)
    def test_no_truncation_of_early_or_late_native_source(self):
        self.doc['motionPlan']['beats'][0].update(startFrame=0,endFrame=0);self.doc['sceneGraph']['nodes'][0]['motion'][0].update(startFrame=0,endFrame=1);self.events['events'][0]['frame']=0
        atomic(self.p/'source/spec.json',self.doc);atomic(self.p/'source/events.json',self.events);self.plan()
        run=self.cli('sfx-mix',self.p,'--plan',self.p/'audio/sfx-plan.json','--narration','audio/dry.wav','--out','audio/outside.wav',success=False)
        self.assertIn('SFX_TAIL_OUT_OF_RANGE',run.stderr);self.assertFalse((self.p/'audio/outside.wav').exists())
    def test_clipping_refused_without_automatic_voice_ducking(self):
        events=copy.deepcopy(self.events)
        for e in events['events']:e['gain']=4
        atomic(self.p/'source/events.json',events);self.plan()
        pcm(self.p/'audio/dry.wav',np.full_like(self.dry,.99))
        run=self.cli('sfx-mix',self.p,'--plan',self.p/'audio/sfx-plan.json','--narration','audio/dry.wav','--out','audio/clipped.wav',success=False)
        self.assertIn('SFX_CLIPPING',run.stderr);self.assertFalse((self.p/'audio/clipped.wav').exists())

if __name__=='__main__':unittest.main()
