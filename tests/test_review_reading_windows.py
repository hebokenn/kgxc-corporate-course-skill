"""Synthetic learner-visible windows never expose arbitrary production objects."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_ai_review as fixtures
import blind_review as blind
from workflow import atomic, hashed


class ReadingWindowTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    def board(self):
        reading=dict(information_groups=[dict(id='reference',screen_text='对照当前结果',
            stable_window=dict(coordinate='absolute-full-course-frames',fps=30,entrance=[676,700],stable=[700,1121]),
            semantic_window=dict(start_after='link-config',retain_until='segment_end_after_relevant_comparison_and_required_reading',
                                 requires='reference_visible_and_stable',audio_binding='unbound'))])
        board=dict(schema='course-storyboard/1',segments=[dict(id='S1',selected='A',script_excerpt='先核对订单，再核对编码。',
            options=[dict(id='A',reading_design=reading,motionPlan=dict(beats=[dict(id='link-config',startFrame=676,endFrame=700)]))])])
        atomic(self.project/'storyboard.json',board)
        return board

    def group(self,board):return board['segments'][0]['options'][0]['reading_design']['information_groups'][0]

    def test_typed_current_windows_survive_projection_packet_and_idempotence(self):
        board=self.board();original=copy.deepcopy(board);projected=blind.storyboard_artifact(board)
        self.assertEqual(self.group(projected),self.group(board))
        self.assertEqual(blind.storyboard_artifact(projected),projected);self.assertEqual(board,original)
        run=self.begin('storyboard',mode='continue');packet=self.review.packet('storyboard',run)['packet']
        self.assertEqual(self.group(packet['input']['storyboard']),self.group(board));blind.validate_packet(packet)

    def test_private_nested_objects_and_unverified_strings_are_never_forwarded(self):
        board=self.board();group=self.group(board)
        group['stable_window'].update(source='SOURCE_PRIVATE',history=['HISTORY_PRIVATE'],original=dict(text='ORIGINAL_PRIVATE'),notes='NOTES_PRIVATE')
        group['semantic_window'].update(start_after='UNVERIFIED_PRIVATE',requires='REQUIRES_PRIVATE',audio_binding='AUDIO_PRIVATE',producer=dict(goals='GOALS_PRIVATE'))
        projected=blind.storyboard_artifact(board);encoded=json.dumps(projected,ensure_ascii=False)
        self.assertNotIn('PRIVATE',encoded)
        self.assertEqual(self.group(projected)['semantic_window'],dict(retain_until='segment_end_after_relevant_comparison_and_required_reading'))
        self.assertEqual(self.group(projected)['stable_window'],dict(coordinate='absolute-full-course-frames',fps=30,entrance=[676,700],stable=[700,1121]))

    def test_wrong_window_types_nonfinite_fps_and_self_authenticating_ids_are_rejected(self):
        for window in [[False,12],[12,12],[12,11],[-1,12],[0,10**9+1],[0,1.5],{'start':0,'end':12},'SOURCE_PRIVATE']:
            board=self.board();self.group(board)['stable_window'].update(stable=window)
            self.assertNotIn('stable',self.group(blind.storyboard_artifact(board))['stable_window'])
        for fps in [True,0,-1,float('nan'),float('inf'),10**500,'30',{'source':'PRIVATE'}]:
            board=self.board();self.group(board)['stable_window'].update(fps=fps,coordinate={'source':'PRIVATE'})
            stable=self.group(blind.storyboard_artifact(board))['stable_window'];self.assertNotIn('fps',stable);self.assertNotIn('coordinate',stable)
        board=self.board();semantic=self.group(board)['semantic_window'];semantic.update(start_after='self-proof',id='self-proof')
        self.assertNotIn('start_after',self.group(blind.storyboard_artifact(board))['semantic_window'])

    def test_actual_window_and_existing_temporal_id_changes_change_learner_hash(self):
        board=self.board();baseline=hashed(blind.storyboard_artifact(board))
        changed=copy.deepcopy(board);self.group(changed)['stable_window']['stable'][1]=1200
        self.assertNotEqual(hashed(blind.storyboard_artifact(changed)),baseline)
        changed=copy.deepcopy(board);self.group(changed)['semantic_window']['start_after']='reference'
        self.assertNotEqual(hashed(blind.storyboard_artifact(changed)),baseline)

    def test_boundary_change_requires_targeted_acceptance_preserving_single_review_and_counters(self):
        self.board();old_file=self.root/'previous-boundary.py';old_file.write_text('synthetic previous policy boundary\n')
        with patch.object(blind,'__file__',str(old_file)):
            run=self.begin('storyboard',mode='continue');self.complete('storyboard',run,self.result('storyboard',run));self.review.finish('storyboard',run)
            before=self.review.node_view('storyboard');self.assertTrue(before['passed'])
        current=self.review.node_view('storyboard');self.assertEqual(current['status'],'stale');self.assertFalse(current['passed'])
        newer=self.begin('storyboard',request='changed-reading-boundary',mode='continue')
        self.assertEqual(newer,run);view=self.review.node_view('storyboard');self.assertEqual(view['calls'],before['calls'])
        self.assertTrue(view['review_cycle']['producer_only']);self.assertFalse(view['passed']);self.assertEqual(len(self.review.load()['nodes']['storyboard']['runs']),1)


if __name__=='__main__':unittest.main()
