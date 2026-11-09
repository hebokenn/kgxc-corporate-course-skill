"""Committed host metadata survives supervision without carrying tool bodies."""
import copy
import hashlib
import json
import subprocess
import unittest

import test_ai_review as fixtures
from ai_review import Review


def metadata(text='synthetic metadata'):
    data=text.encode('utf-8')
    return dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


class ExecutionEvidenceTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown

    def publish(self,events,phase='start',operation='synthetic-evidence'):
        return self.review.production_event(fixtures.PRODUCER,operation,phase,'storyboard',events)

    def packet(self,operation='synthetic-evidence'):
        return Review(self.course).supervisor_packet(operation_id=operation)['packet']

    def call(self):
        return dict(type='tool/call',seq=1,call_id='read-1',name='read',evidence=dict(arguments=metadata(),
                    read=dict(basis='committed_tool_arguments',path='work/合成回证.json',range={})))

    def result(self):
        return dict(type='tool/result',seq=2,call_id='read-1',failed=False,evidence=dict(result=dict(
                    basis='committed_tool_result',coverage='reported_fields_only',format='json',**metadata(),
                    structure=dict(type='object',fields=[dict(name='completed',type='boolean')],field_count=12),
                    reported=dict(completed=True,all_selected_A=True,workflow_revision=118,segments=16,options=48,
                                  storyboard_sha256='a'*64,receipt='work/合成回证.json',
                                  protected_files={'source/transcript.md':'b'*64},
                                  checks=dict(current_binding=True,continuous_AV=False),
                                  only_process_receipt_written=True,new_user_confirmation=False,
                                  review_not_triggered=True,independent_review_passed=False))))

    def test_tool_assertions_round_trip_without_claiming_independent_file_verification(self):
        events=[self.call(),self.result()];before=copy.deepcopy(self.review.load())
        self.publish(events);events[1]['evidence']['result']['reported']['completed']=False
        packet=self.packet();facts=packet['execution'][0]['execution']
        self.assertEqual(facts[0]['evidence']['read']['range'],{})
        result=facts[1]['evidence']['result'];self.assertTrue(result['reported']['completed'])
        self.assertEqual(result['coverage'],'reported_fields_only');self.assertEqual(result['basis'],'committed_tool_result')
        for key in ['new_user_confirmation','independent_review_passed']:
            self.assertIs(result['reported'][key],False)
        self.assertIs(result['reported']['checks']['continuous_AV'],False)
        self.assertFalse((self.project/'work/合成回证.json').exists())
        after=self.review.load()
        for key in ['nodes','requirements','authorizations','policy']:
            self.assertEqual(after[key],before[key])
        binding=packet['binding']
        event=self.result();event['seq']=3;event['evidence']['result']['reported']['completed']=False
        self.publish([event],'progress');self.assertNotEqual(self.packet()['binding'],binding)

    def test_actual_monitor_projection_and_opaque_boundaries_pass_the_backend(self):
        source="""import {readFileSync} from 'node:fs';
import {productionEventFact} from './plugin/production-monitor.mjs';
const events=JSON.parse(readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(events.map(productionEventFact)));
"""
        body='SYNTHETIC_PRIVATE_BODY_DO_NOT_FORWARD'
        output=dict(completed=True,new_user_confirmation=False,independent_review_passed=False,
                    protected_files={'source/transcript.md':'b'*64},checks=dict(current_binding=True),
                    receipt='work/合成回证.json',notes=body)
        def call(seq,name,args):
            return dict(seq=seq,time=seq,type='tool/call',data=dict(name=name,callId='call-'+str(seq),arguments=json.dumps(args,ensure_ascii=False)))
        events=[call(1,'read',dict(file_path='work/合成回证.py')),
                call(2,'bash',dict(command="python3 -B 'work/合成回证.py' 118 --stage=storyboard")),
                call(3,'bash',dict(command="python3 'work/check.py' --revision 1000000001")),
                call(4,'bash',dict(command="python3 'work/check.py' "+' '.join(['--check=json']*17))),
                call(5,'read',dict(file_path='work/../auth.json')),
                call(6,'bash',dict(command="python3 'work/check.py' --token="+body)),
                dict(seq=7,time=7,type='tool/result',data=dict(message=dict(toolCallId='call-2',content=[dict(type='text',text=json.dumps(output,ensure_ascii=False)+'\n[exit code: 0]')]))),
                dict(seq=8,time=8,type='job/settled',data=dict(jobId='job-2',status='complete',detail='[exit code: 0]'))]
        process=subprocess.run(['node','--input-type=module','-e',source],input=json.dumps(events,ensure_ascii=False),
                               cwd=fixtures.ROOT,text=True,capture_output=True,check=True)
        facts=json.loads(process.stdout);self.assertNotIn(body,process.stdout)
        self.assertEqual(facts[0]['evidence']['read']['range'],{})
        self.assertEqual(facts[1]['evidence']['command']['type'],'simple_script')
        self.assertEqual(facts[2]['evidence']['command']['argv'][-1]['kind'],'opaque')
        self.assertEqual(facts[3]['evidence']['command']['type'],'opaque')
        self.assertNotIn('path',facts[4]['evidence']['read'])
        self.assertEqual(facts[5]['evidence']['command']['argv'][-1]['kind'],'opaque')
        self.assertNotIn('evidence',facts[7])
        self.publish(facts)
        self.assertEqual(self.packet()['execution'][0]['execution'],facts)

    def test_native_write_edit_and_synthetic_patch_targets_and_actual_125_result_shape_reach_supervisor(self):
        # The keys and primitive types reproduce native 125; all paths/bodies are synthetic.
        source="""import {readFileSync} from 'node:fs';
import {productionEventFact} from './plugin/production-monitor.mjs';
process.stdout.write(JSON.stringify(JSON.parse(readFileSync(0,'utf8')).map(productionEventFact)));
"""
        private='SYNTHETIC_PRIVATE_CONTENT_MUST_NOT_CROSS_BOUNDARY'
        target='project/work/synthetic-storyboard-process/minimal-plan.md'
        def native_call(seq,name,args):
            return dict(seq=seq,time=seq,type='tool/call',data=dict(name=name,callId='call-'+str(seq),arguments=json.dumps(args,ensure_ascii=False)))
        def native_result(seq,call_id,value):
            return dict(seq=seq,time=seq,type='tool/result',data=dict(message=dict(toolCallId=call_id,content=[dict(type='text',text=value)])))
        events=[native_call(3275,'write',dict(file_path=target,content=private)),
                native_result(3276,'call-3275','synthetic native write acknowledgment'),
                native_call(3277,'edit',dict(file_path=target,old_string=private,new_string=private+' changed')),
                # No native apply_patch was observed in 125. This is explicitly synthetic coverage.
                native_call(3278,'apply_patch',dict(patch='*** Begin Patch\n*** Add File: project/work/synthetic-process/new.py\n+'+private+'\n*** End Patch')),
                native_result(3264,'call-3261',json.dumps(dict(backed_up_files=14,output='/tmp/synthetic-course/project/work/synthetic-process',baseline_matches=True,revision=121))),
                native_result(3280,'call-3279',json.dumps(dict(backed_up_files=0,output='work/synthetic-process',baseline_matches=False,revision=0)))]
        process=subprocess.run(['node','--input-type=module','-e',source],input=json.dumps(events,ensure_ascii=False),cwd=fixtures.ROOT,text=True,capture_output=True,check=True)
        self.assertNotIn(private,process.stdout);facts=json.loads(process.stdout)
        expected=dict(basis='committed_tool_arguments',scope='requested_targets',operation='write',fs_verified=False,paths=[target],paths_complete=True)
        self.assertEqual(facts[0]['evidence']['mutation'],expected)
        self.assertEqual(facts[2]['evidence']['mutation'],dict(expected,operation='edit'))
        self.assertEqual(facts[3]['evidence']['mutation'],dict(expected,operation='apply_patch',paths=['project/work/synthetic-process/new.py']))
        self.assertEqual(facts[1]['evidence']['result']['format'],'opaque')
        self.assertNotIn('reported',facts[1]['evidence']['result'])
        self.publish(facts);actual=self.packet()['execution'][0]['execution'];self.assertEqual(actual,facts)
        for fact in actual[4:]:
            result=fact['evidence']['result'];self.assertEqual(result['basis'],'committed_tool_result');self.assertEqual(result['coverage'],'reported_fields_only')
        self.assertIs(actual[4]['evidence']['result']['reported']['baseline_matches'],True)
        self.assertIs(actual[5]['evidence']['result']['reported']['baseline_matches'],False)
        self.assertEqual(actual[5]['evidence']['result']['reported']['backed_up_files'],0)
        self.assertEqual(actual[5]['evidence']['result']['reported']['revision'],0)
        self.assertFalse((self.project/'work/synthetic-process').exists())

    def mutation(self):
        return dict(type='tool/call',name='write',evidence=dict(arguments=metadata(),mutation=dict(
                    basis='committed_tool_arguments',scope='requested_targets',operation='write',fs_verified=False,paths=['work/synthetic-process/plan.md'],paths_complete=True)))

    def test_mutation_claims_are_bounded_tool_arguments_never_filesystem_proof(self):
        event=self.mutation();event['evidence']['mutation'].update(paths=[],paths_complete=False)
        self.publish([event]);self.assertEqual(self.packet()['execution'][0]['execution'],[event])
        mutations=[lambda e:e['evidence']['mutation'].update(content='private body'),
                   lambda e:e['evidence']['mutation'].update(basis='filesystem_readback'),
                   lambda e:e['evidence']['mutation'].update(scope='verified_files'),
                   lambda e:e['evidence']['mutation'].update(fs_verified=True),
                   lambda e:e['evidence']['mutation'].update(operation='edit'),
                   lambda e:e['evidence']['mutation'].update(paths_complete='false'),
                   lambda e:e['evidence']['mutation'].update(paths=['work/x.md']*33),
                   lambda e:e['evidence']['mutation'].update(paths=[dict(path='work/x.md')]),
                   lambda e:e['evidence']['mutation'].update(paths=['work/../auth.json']),
                   lambda e:e['evidence']['mutation'].update(paths=['work/.env']),
                   lambda e:e.update(name='read'),lambda e:e.update(type='tool/result')]
        for index,change in enumerate(mutations):
            event=self.mutation();change(event)
            with self.subTest(index=index):self.assert_rejected_unchanged(event)

    def test_new_fixed_reported_primitives_reject_unknown_types_and_unsafe_paths(self):
        for name,value in [('baseline_matches','true'),('baseline_matches',1),('backed_up_files',True),('backed_up_files',-1),
                           ('revision',1.2),('revision',10**9+1),('output','https://invalid.example/process'),('output','work/../process'),
                           ('output','work/auth.json'),('output',{'body':'private'}),('unapproved_assertion',True)]:
            event=self.result();event['evidence']['result']['reported'][name]=value
            with self.subTest(name=name,value=value):self.assert_rejected_unchanged(event)

    def assert_rejected_unchanged(self,event):
        before=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'监督证据'):
            self.publish([self.call(),event])
        self.assertEqual(self.review.path.read_bytes(),before)

    def test_unknown_nested_fields_and_raw_content_are_rejected_atomically(self):
        for target in ['top','read','arguments','reported','structure','field','checks']:
            with self.subTest(target=target):
                event=self.call() if target in ['top','read','arguments'] else self.result()
                evidence=event['evidence']
                if target=='top':evidence['raw_arguments']='private body'
                elif target=='read':evidence['read']['content']='private body'
                elif target=='arguments':evidence['arguments']['text']='private body'
                elif target=='reported':evidence['result']['reported']['source_text']='private body'
                elif target=='structure':evidence['result']['structure']['body']='private body'
                elif target=='field':evidence['result']['structure']['fields'][0]['value']='private body'
                else:evidence['result']['reported']['checks']['source_text']='private body'
                self.assert_rejected_unchanged(event)

    def test_invalid_types_sizes_and_claimed_independent_verification_are_rejected(self):
        changes=[lambda e:e['evidence']['result'].update(coverage='independently_verified'),
                 lambda e:e['evidence']['result'].update(basis='filesystem_readback'),
                 lambda e:e['evidence']['result'].update(bytes=True),
                 lambda e:e['evidence']['result'].update(bytes=2**53),
                 lambda e:e['evidence']['result']['reported'].update(segments=10**9+1),
                 lambda e:e['evidence']['result']['reported'].update(completed=1),
                 lambda e:e['evidence']['result']['reported'].update(checks={str(i):True for i in range(33)}),
                 lambda e:e['evidence']['result']['reported'].update(protected_files={'work/'+str(i)+'.json':'a'*64 for i in range(33)}),
                 lambda e:e['evidence']['result']['structure'].update(fields=[dict(name='A'+str(i),type='null') for i in range(33)],field_count=33),
                 lambda e:e['evidence']['result']['reported'].update({'A'+str(i)+'_sha256':'a'*64 for i in range(33)})]
        for change in changes:
            event=self.result();change(event)
            with self.subTest(event=changes.index(change)):self.assert_rejected_unchanged(event)
        event=self.call();event['evidence']['read']['range']['offset']=True;self.assert_rejected_unchanged(event)

    def test_unsafe_paths_and_unprojected_sensitive_arguments_are_rejected(self):
        for path in ['work/../receipt.json','https://example.test/receipt.json','work/auth.json','work/.env.local','work/id_rsa','work/private.pem','work/x;echo.json','work/x\n.json','work/'+('a'*1024)+'.json']:
            with self.subTest(path=path):
                event=self.call();event['evidence']['read']['path']=path;self.assert_rejected_unchanged(event)
                event=self.result();event['evidence']['result']['reported']['receipt']=path;self.assert_rejected_unchanged(event)
        command=dict(type='simple_script',interpreter='python3',script_path='work/check.py',argv=[],**metadata())
        variants=[[dict(kind='flag',value='--password'),dict(kind='enum',value='json')],
                  [dict(kind='flag',value='-c')],[dict(kind='number',value=10**9+1)],
                  [dict(kind='sha256',value='a'*64)],[dict(kind='opaque',value='private',**metadata())],
                  [dict(kind='enum',value='json')]*33]
        for argv in variants:
            event=dict(type='tool/call',name='bash',evidence=dict(arguments=metadata(),command=dict(command,argv=argv)))
            self.assert_rejected_unchanged(event)

    def test_opaque_results_and_job_exit_cannot_fabricate_completion_assertions(self):
        event=dict(type='tool/result',evidence=dict(result=dict(basis='committed_tool_result',coverage='reported_fields_only',format='opaque',**metadata())))
        self.publish([event,dict(type='job/settled',exit_code=0,status='complete')])
        facts=self.packet()['execution'][0]['execution']
        self.assertNotIn('reported',facts[0]['evidence']['result']);self.assertNotIn('evidence',facts[1])
        event['evidence']['result']['reported']=dict(completed=True);self.assert_rejected_unchanged(event)
        event=self.result();event['type']='job/settled';self.assert_rejected_unchanged(event)
        event=self.result();event['evidence']['arguments']=metadata();self.assert_rejected_unchanged(event)


if __name__=='__main__':unittest.main()
