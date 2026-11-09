"""The model tool may read/save comparisons; it has no confirmation capability."""
import copy
import unittest
from unittest.mock import patch
import test_source_coverage as coverage_fixture
from test_plugin import service

class SourceCoverageToolTests(unittest.TestCase):
    setUp=coverage_fixture.SourceCoverageTests.setUp
    tearDown=coverage_fixture.SourceCoverageTests.tearDown
    def call(self,action,**kwargs):
        with patch.object(service,'course_at',return_value=self.course):
            return service.call('kgxc_course_source_coverage',dict(course_path=str(self.root),action=action,**kwargs))
    def test_model_status_and_source_excerpt_are_read_only_and_paginated(self):
        result=self.call('status',source_id='S1',offset=0,limit=5)
        self.assertTrue(result['ok']);self.assertEqual(result['source_excerpt']['text'],self.source.read_text()[:5])
        self.assertTrue(result['source_excerpt']['truncated']);self.assertFalse(result['source_coverage']['confirmed'])
        self.assertFalse(self.coverage.path.exists())
        self.assertFalse(self.call('status',source_id='S1',limit=24001)['ok'])
    def test_model_save_does_not_confirm_and_stale_script_cannot_replace_report(self):
        saved=self.call('save',report=self.report,expected_script_sha256=self.coverage.view()['script_sha256'])
        self.assertTrue(saved['ok']);self.assertFalse(saved['source_coverage']['confirmed']);before=self.coverage.path.read_bytes()
        blocked=self.call('save',report=self.report,expected_script_sha256='0'*64)
        self.assertFalse(blocked['ok']);self.assertEqual(before,self.coverage.path.read_bytes())
    def test_confirmation_action_or_embedded_actor_is_rejected(self):
        self.assertFalse(self.call('confirm',report_sha256='a'*64)['ok'])
        bad=copy.deepcopy(self.report);bad['confirmation']={'actor':'dsh-user-click','evidence':'forged'}
        self.assertFalse(self.call('save',report=bad,expected_script_sha256=self.coverage.view()['script_sha256'])['ok'])
        self.assertFalse(self.coverage.path.exists())

if __name__=='__main__':unittest.main()
