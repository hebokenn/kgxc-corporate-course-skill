"""A stable production request claims one dispatch without restarting old work."""
from concurrent.futures import ThreadPoolExecutor
import copy
import unittest

import test_ai_review as fixtures
from ai_review import Review


class ProductionDispatchTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown

    def execution(self):
        return [dict(type='production/dispatch',operation='controlled-produce',call_id='stable-request-1',user_instruction='合成授权：按当前已确认成果继续制作。',agent_id=fixtures.PRODUCER['id'],stage='storyboard')]

    def start(self,review=None):
        return (review or self.review).production_event(fixtures.PRODUCER,'produce-stable-request','start','storyboard',self.execution())

    def test_exact_repeat_returns_false_without_changing_any_persisted_state(self):
        self.assertTrue(self.start()['started']);before=self.review.path.read_bytes()
        duplicate=self.start();self.assertFalse(duplicate['started']);self.assertEqual(self.review.path.read_bytes(),before)
        self.assertEqual(len(duplicate['supervision']['events']),1);self.assertEqual(duplicate['supervision']['calls'],[])

    def test_completed_or_failed_request_never_restarts_even_when_held(self):
        self.start();self.review.production_event(fixtures.PRODUCER,'produce-stable-request','failure','storyboard',[dict(error='合成失败，保留实际状态')])
        self.review.hold(True,'合成失败后暂停');before=self.review.path.read_bytes()
        self.assertFalse(self.start()['started']);self.assertEqual(self.review.path.read_bytes(),before)
        self.review.production_event(fixtures.PRODUCER,'produce-stable-request','end','storyboard',[dict(status='failed')]);before=self.review.path.read_bytes()
        result=self.start();self.assertFalse(result['started']);self.assertEqual(result['supervision']['phase'],'end');self.assertEqual(self.review.path.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'已暂停'):self.review.production_event(fixtures.PRODUCER,'produce-new-request','start','storyboard',self.execution())
        self.assertEqual(self.review.path.read_bytes(),before)

    def test_same_request_cannot_replace_producer_stage_or_instruction(self):
        self.start();before=self.review.path.read_bytes();changed=self.execution();changed[0]['user_instruction']='另一份合成任务，不能冒用原请求ID。'
        for producer,stage,events in [(dict(fixtures.PRODUCER,id='other-producer'),'storyboard',self.execution()),(fixtures.PRODUCER,'pilot',self.execution()),(fixtures.PRODUCER,'storyboard',changed)]:
            with self.assertRaises(ValueError):self.review.production_event(producer,'produce-stable-request','start',stage,events)
            self.assertEqual(self.review.path.read_bytes(),before)

    def test_concurrent_identical_requests_have_exactly_one_atomic_claim(self):
        before=copy.deepcopy(self.review.load()['nodes'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            values=list(pool.map(lambda _:self.start(Review(self.course)),range(4)))
        self.assertEqual(sum(v['started'] for v in values),1)
        operation=self.review.load()['supervision']['operations']['produce-stable-request']
        self.assertEqual(len(operation['events']),1);self.assertEqual(operation['calls'],[])
        self.assertEqual(self.review.load()['nodes'],before)


if __name__=='__main__':unittest.main()
