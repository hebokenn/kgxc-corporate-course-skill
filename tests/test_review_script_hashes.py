"""Producer-only hash metadata distinguishes JSON text from actual UTF-8 bytes."""
import hashlib
import json
import unittest
from unittest.mock import patch

import test_ai_review as fixtures
from script_editor import ScriptEditor
from workflow import atomic, hashed, sha


class ProducerScriptHashTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin

    def test_existing_hash_stays_json_and_new_hashes_match_their_explicit_algorithms(self):
        text='同一份讲稿：先读“订单A”，再核对编码。\n不要把JSON转义引号当成稿件修改。'
        self.studio.save_sections([dict(unit_id='U',body=text)],self.course.status()['revision'],official=True)
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];text=packet['input']['text'];proof=packet['evidence']['script']
        raw=hashlib.sha256(text.encode('utf-8')).hexdigest()
        serialized=hashlib.sha256(json.dumps(text,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        self.assertNotEqual(raw,serialized);self.assertEqual(proof['sha256'],hashed(text));self.assertEqual(proof['sha256'],serialized)
        self.assertEqual(proof['sha256_semantics'],'json-serialized-text');self.assertEqual(proof['json_text_sha256'],serialized)
        self.assertEqual(proof['raw_text_sha256'],raw);self.assertEqual(packet['editable_files'][0]['sha256'],raw)
        source=self.course.relative(self.course.script()['path'])
        self.assertEqual(proof['current_source_file_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertTrue(proof['current_source_file_matches_raw_text']);self.assertFalse(self.review.node_view('script')['passed'])

    def test_current_draft_and_official_source_keep_distinct_truthful_hashes(self):
        source=self.course.relative(self.course.script()['path']);original=source.read_bytes()
        editor=ScriptEditor(self.space);value=editor.read();editor.save(value['text']+'\n人工草稿新增核对步骤。',value['revision'])
        run=self.begin(mode='continue');packet=self.review.producer_packet('script',run)['packet'];proof=packet['evidence']['script']
        self.assertEqual(proof['raw_text_sha256'],hashlib.sha256(packet['input']['text'].encode('utf-8')).hexdigest())
        self.assertEqual(proof['current_source_file_sha256'],hashlib.sha256(original).hexdigest())
        self.assertFalse(proof['current_source_file_matches_raw_text']);self.assertEqual(source.read_bytes(),original)
        self.assertFalse(self.review.node_view('script')['user_confirmed'])

    def test_unavailable_source_file_never_claims_a_matching_file_hash(self):
        run=self.begin()
        with patch.object(self.course,'script',return_value=dict(path='source/unavailable.md')):
            proof=self.review.producer_packet('script',run)['packet']['evidence']['script']
        self.assertIsNone(proof['current_source_file_sha256']);self.assertIsNone(proof['current_source_file_matches_raw_text'])
        self.assertEqual(proof['json_text_sha256'],proof['sha256']);self.assertEqual(len(proof['raw_text_sha256']),64)

    def test_legacy_frozen_packet_is_not_rewritten_and_fresh_attempt_gets_new_fields(self):
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];state=self.review.load();task=state['nodes']['script']['runs'][-1]
        fields=['sha256_semantics','raw_text_sha256','json_text_sha256','current_source_file_sha256','current_source_file_matches_raw_text']
        for key in fields:packet['evidence']['script'].pop(key)
        path=self.project/task['producer_packet_path'];atomic(path,packet);digest=sha(path)
        task['producer_packet_sha256']=digest;task['producer_attempt']['packet_sha256']=digest;task['producer_packet_history'][-1]['sha256']=digest;atomic(self.review.path,state)
        original=path.read_bytes();self.assertEqual(self.review.producer_packet('script',run)['packet'],packet);self.assertEqual(path.read_bytes(),original)
        self.review.finish('script',run,error='合成旧包保留，不改变旧结论')
        fresh=self.begin(request='fresh-hash-metadata',mode='continue');current=self.review.producer_packet('script',fresh)['packet']
        for key in fields:self.assertIn(key,current['evidence']['script'])
        self.assertEqual(path.read_bytes(),original);self.assertEqual(current['evidence']['script']['sha256'],packet['evidence']['script']['sha256'])


if __name__=='__main__':unittest.main()
