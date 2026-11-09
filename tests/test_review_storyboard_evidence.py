"""Exact storyboard locator intake retains uncertain findings without granting a pass."""
import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import test_ai_review as fixtures
from ai_review import Review
import blind_review as blind
from workflow import atomic, read


class StoryboardEvidenceTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded

    def board(self):
        value=dict(schema='course-storyboard/1',visual_direction=dict(palette='红白',typography='无衬线',graphics='矢量对象',atmosphere='清晰'),segments=[])
        for sid,excerpt,action in [('S12','店长说："先稳住自己"。\n再回应员工。','先显示情绪温度计，再降低指针。'),('S13','先看见员工的情绪信号，再问一句。','把焦点移向左侧员工，再显示他的回应。')]:
            value['segments'].append(dict(id=sid,kind='concept',script_excerpt=excerpt,duration=12,selected='A',options=[dict(id='A',method='对象演示',opening='对象准备',action=action,result='结果停稳',focus='当前结果',characters=False)],motionPlan=dict(beats=[dict(id='B'+sid,start=0,end=3)])))
        atomic(self.project/'storyboard.json',value)
        return value

    def report(self,run,findings):
        packet=self.review.packet('storyboard',run)['packet']
        ref=dict(method='storyboard_read',locator='S12.script_excerpt',quote=packet['input']['storyboard']['segments'][0]['script_excerpt'])
        return dict(binding=packet['binding'],summary='合成分镜学员审阅',learner=dict(about='管理情绪',what_it_said='先稳住自己，再观察员工的情绪信号。',learned=['先稳定再回应'],confusions=[]),findings=copy.deepcopy(findings),
                    items=[dict(id=c['id'],verdict='通过',reason='引用当前实际分镜',evidence=[copy.deepcopy(ref)]) for c in packet['checklist']],inspected_frame_hashes=[],agent_audit=self.audit('reviewer',packet))

    def send(self,run,result):
        self.recorded('storyboard',run,result['agent_audit'],[])
        return self.review.submit('storyboard',run,result)

    def test_exact_unique_locator_prefix_resolves_without_inserting_segment_into_raw_refs(self):
        board=self.board();run=self.begin('storyboard',mode='continue')
        ref=dict(method='storyboard_read',locator='S13.A.action',quote=board['segments'][1]['options'][0]['action'])
        result=self.report(run,[dict(id='F1',problem='动作结果需要更清楚',evidence=[ref])]);before=copy.deepcopy(result)
        value=self.send(run,result);finding=next(i for i in value['report']['items'] if i['id']=='finding:F1')
        self.assertEqual(finding['verdict'],'需修改');self.assertTrue(finding['critical']);self.assertFalse(value['report']['passed'])
        self.assertEqual(result,before);self.assertNotIn('segment_id',finding['evidence'][0])
        private=self.review.producer_packet('storyboard',run)['packet'];self.assertEqual(private['blind_report']['findings'],before['findings'])

    def test_actual_string_leaf_handles_quotes_and_newlines_without_json_escape_mismatch(self):
        boundary_before=hashlib.sha256(Path(blind.__file__).read_bytes()).hexdigest()
        board=self.board();run=self.begin('storyboard',mode='continue');quote=board['segments'][0]['script_excerpt']
        self.assertFalse(blind.storyboard_reference(dict(segment_id='S12',quote=quote),board))
        self.assertTrue(self.review._storyboard_reference(dict(locator='S12.script_excerpt',quote=quote),board))
        value=self.send(run,self.report(run,[]));actual=self.review.node_view('storyboard')['run']['blind_report']
        self.assertTrue(all(i['verdict']=='通过' for i in actual['items']));self.assertTrue(actual['passed'])
        self.assertFalse(value['report']['passed'])  # Production QA and supervision remain mandatory.
        self.assertEqual(hashlib.sha256(Path(blind.__file__).read_bytes()).hexdigest(),boundary_before)

    def test_summary_evidence_stays_critical_unknown_and_full_raw_result_reaches_producer(self):
        board=self.board();run=self.begin('storyboard',mode='continue')
        refs=[dict(locator='S12.script_excerpt',quote=board['segments'][0]['script_excerpt']),dict(locator='S13.A.action',quote='概述：照顾员工并统筹全局')]
        result=self.report(run,[dict(id='F1',problem='有定位的问题',evidence=[refs[0]]),dict(id='F2',problem='尚未证实的问题',evidence=[refs[1]])]);before=copy.deepcopy(result)
        value=self.send(run,result);by_id={i['id']:i for i in value['report']['items']}
        self.assertEqual(by_id['finding:F1']['verdict'],'需修改');self.assertEqual(by_id['finding:F2']['verdict'],'无法验证')
        self.assertTrue(by_id['finding:F2']['critical']);self.assertIn('证据未匹配',by_id['finding:F2']['reason']);self.assertFalse(value['report']['passed'])
        self.assertTrue(value['needs_producer']);self.assertEqual(by_id['finding:F2']['evidence'],[refs[1]])
        run_data=self.review.node_view('storyboard')['run'];self.assertEqual(run_data['iterations'][0]['raw_result'],before)
        saved=read(self.project/'qa/ai-review'/run/'00/report.json');self.assertEqual(saved['raw_result'],before)
        private=self.review.producer_packet('storyboard',run)['packet'];self.assertEqual(private['blind_report']['findings'],before['findings'])
        self.assertFalse(private['blind_report']['passed']);self.assertEqual(private['blind_report']['agent_audit'],before['agent_audit'])

    def test_cross_segment_fake_or_ambiguous_locators_never_become_verified_evidence(self):
        board=self.board();board['segments'].append(dict(id='S12.A',kind='concept',script_excerpt='单独的一段',options=[]));atomic(self.project/'storyboard.json',board)
        run=self.begin('storyboard',mode='continue');q12=board['segments'][0]['script_excerpt'];q13=board['segments'][1]['script_excerpt']
        refs=[dict(segment_id='S12',locator='S13.script_excerpt',quote=q13),dict(locator='S120.script_excerpt',quote=q12),dict(locator='prefix.S12.script_excerpt',quote=q12),dict(locator='S999.script_excerpt',quote=q12),dict(locator='S12.A.action',quote=q12),dict(locator='S12.script_excerpt',quote=q12+board['segments'][0]['options'][0]['action'])]
        result=self.report(run,[dict(id='F'+str(i),problem='待核对的定位',evidence=[ref]) for i,ref in enumerate(refs)])
        value=self.send(run,result)
        for i,ref in enumerate(refs):
            item=next(v for v in value['report']['items'] if v['id']=='finding:F'+str(i))
            self.assertEqual(item['verdict'],'无法验证');self.assertEqual(item['evidence'],[ref]);self.assertTrue(item['critical'])
        self.assertFalse(value['report']['passed'])

    def test_beat_and_time_checks_still_delegate_to_original_strict_boundary(self):
        board=self.board();q=board['segments'][0]['script_excerpt'];raw=dict(locator='S12.motionPlan',quote=q,beat='BS12',time=1)
        with patch.object(blind,'storyboard_reference',wraps=blind.storyboard_reference) as original:
            self.assertTrue(self.review._storyboard_reference(raw,board));original.assert_called_once()
            self.assertEqual(original.call_args.args[0]['segment_id'],'S12');self.assertNotIn('quote',original.call_args.args[0])
        self.assertNotIn('segment_id',raw)
        self.assertFalse(self.review._storyboard_reference(dict(raw,time=999),board))
        self.assertFalse(self.review._storyboard_reference(dict(raw,beat='invented'),board))
        self.assertFalse(self.review._storyboard_reference(dict(raw,quote='概述而不是原句'),board))
        self.assertTrue(self.review._storyboard_reference(dict(segment_id='S12',quote=q),board))

    def navigation_board(self):
        board=self.board();board['navigation']=dict(schema='course-navigation/1',toc=dict(sections=[dict(unit_id='U',label=board['segments'][0]['script_excerpt'])]),
            actual_timeline=dict(fps=30,total_frames=900,body=[90,810],toc_visible=[90,150],section_title_windows=[dict(unit_id='U',window=[150,180])],basis='PRIVATE_SOURCE_BINDING'))
        atomic(self.project/'storyboard.json',board)
        return board

    def test_navigation_submit_preserves_exact_refs_and_locates_safe_label_and_frame_window(self):
        board=self.navigation_board();run=self.begin('storyboard',mode='continue')
        label=dict(method='storyboard_read',locator='input.storyboard.navigation.toc.sections[0].label',quote=board['navigation']['toc']['sections'][0]['label'])
        window=dict(method='storyboard_read',locator='input.storyboard.navigation.actual_timeline.section_title_windows[0].window',quote='[150,180]')
        with patch.object(blind,'storyboard_reference',wraps=blind.storyboard_reference) as boundary:
            self.assertTrue(self.review._storyboard_reference(label,board));boundary.assert_called_once_with(label,board)
        result=self.report(run,[dict(id='NAV1',problem='合成标题窗口仍有待制作端核对的教学问题',evidence=[window])])
        for item in result['items']:item['evidence']=[copy.deepcopy(label)]
        before=copy.deepcopy(result);value=self.send(run,result);actual=self.review.node_view('storyboard')['run']['blind_report']
        finding=next(i for i in actual['items'] if i['id']=='finding:NAV1')
        self.assertEqual(finding['verdict'],'需修改');self.assertTrue(finding['critical']);self.assertEqual(finding['evidence'],[window])
        self.assertTrue(all(i['verdict']=='通过' for i in actual['items'] if i['id']!='finding:NAV1'))
        self.assertEqual(result,before);self.assertFalse(value['report']['passed']);self.assertTrue(value['needs_producer'])
        private=self.review.producer_packet('storyboard',run)['packet'];self.assertEqual(private['blind_report']['findings'],before['findings'])

    def test_navigation_submit_never_uses_raw_private_fields_or_ignores_fake_locator_time_or_segment(self):
        board=self.navigation_board();run=self.begin('storyboard',mode='continue');quote=board['segments'][0]['script_excerpt']
        valid=dict(method='storyboard_read',locator='input.storyboard.navigation.toc.sections[0].label',quote=quote)
        refs=[dict(valid,locator='input.storyboard.navigation.actual_timeline.basis',quote='PRIVATE_SOURCE_BINDING'),
              dict(valid,quote='概述不是当前导航原句'),dict(valid,locator='input.storyboard.navigation.toc.sections[99].label'),
              dict(valid,locator='input.storyboard.navigation_typo.toc.sections[0].label',segment_id='S12'),
              dict(valid,time=1),dict(valid,beat='BS12'),dict(valid,segment_id='S12'),dict(valid,option_id='A')]
        result=self.report(run,[dict(id='NAV'+str(i),problem='合成待核实导航定位',evidence=[ref]) for i,ref in enumerate(refs)]);before=copy.deepcopy(result)
        value=self.send(run,result);actual=self.review.node_view('storyboard')['run']['blind_report']
        for i,ref in enumerate(refs):
            finding=next(item for item in actual['items'] if item['id']=='finding:NAV'+str(i))
            self.assertEqual(finding['verdict'],'无法验证');self.assertTrue(finding['critical']);self.assertEqual(finding['evidence'],[ref])
        self.assertFalse(value['report']['passed']);self.assertEqual(result,before)
        self.assertEqual(self.review.node_view('storyboard')['run']['iterations'][0]['raw_result'],before)

    def test_write_payload_binding_and_artifact_scope_are_still_fatal(self):
        self.board();run=self.begin('storyboard',mode='continue');base=self.report(run,[])
        wrong_binding=copy.deepcopy(base);wrong_binding['binding']['packet_sha256']='forged'
        wrong_scope=copy.deepcopy(base);wrong_scope['agent_audit']['artifact_ids']=['other-stage-artifact']
        for wrong in [dict(base,repairs=[]),wrong_binding,wrong_scope]:
            with self.assertRaises(ValueError):self.send(run,wrong)
            self.assertEqual(self.review.node_view('storyboard')['run']['iterations'],[])
        # Invalid script/media evidence remains fatal in the existing regression suite.


if __name__=='__main__':unittest.main()
