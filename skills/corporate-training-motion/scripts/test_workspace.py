#!/usr/bin/env python3
"""Check scaffold preservation and real path/hash failures without touching a course."""
import json,tempfile,unittest,hashlib
from pathlib import Path
from scaffold import create
from workspace_check import check
from review_gate import check as approvals
class WorkspaceTests(unittest.TestCase):
 def test_layout_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'course';create(p);self.assertTrue(check(p)['ok'])
   original=(p/'project/project.json').read_bytes()
   with self.assertRaises(SystemExit):create(p)
   self.assertEqual(original,(p/'project/project.json').read_bytes())
 def test_hash_and_old_root_and_escaped_link(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'course';create(p);v=p/'delivery/final.mp4';v.write_bytes(b'current')
   w=json.loads((p/'workspace.json').read_text());w['retain_artifacts']=[{'path':'delivery/final.mp4','sha256':hashlib.sha256(b'current').hexdigest()}];(p/'workspace.json').write_text(json.dumps(w))
   self.assertTrue(check(p)['ok']);v.write_bytes(b'changed');self.assertFalse(check(p)['ok'])
   (p/'old-v1').mkdir();(p/'project/escape').symlink_to(Path(tmp));errors=check(p)['errors']
   self.assertTrue(any('Historical version' in x for x in errors));self.assertTrue(any('escaping' in x for x in errors))
 def test_approval_boundary_accepts_own_input_rejects_other_project(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'course';create(p);f=p/'inputs/doc';f.write_bytes(b'source')
   entry={'status':'approved','reviewer':'fixture','confirmed_at':'2026-01-01','user_confirmation':'fixture only','artifacts':{'../inputs/doc':hashlib.sha256(b'source').hexdigest()}}
   a=p/'project/approval_records.json';a.write_text(json.dumps({'source':entry}));self.assertEqual(approvals(p/'project','script'),[])
   outside=Path(tmp)/'other';outside.write_bytes(b'source');entry['artifacts']={'../../other':hashlib.sha256(b'source').hexdigest()};a.write_text(json.dumps({'source':entry}));self.assertTrue(any('APPROVAL_PATH' in x for x in approvals(p/'project','script')))
if __name__=='__main__':unittest.main()
