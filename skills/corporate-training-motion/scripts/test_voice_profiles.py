"""Verify voice selection does not mix incompatible model variants or rewrite audio."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from qwen3_tts import resolve,ROOT,CATALOG
from scaffold import create

class VoiceProfileTests(unittest.TestCase):
    def test_clean_install_resolves_recommended_didi(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=resolve({},library=Path(tmp)/'voices')
        self.assertEqual(c['profile'],'didi');self.assertEqual(c['mode'],'clone');self.assertEqual(c['delivery_rate'],1.0)
        self.assertIn('Base',c['model']);self.assertEqual(c['speed'],1.0);self.assertEqual(c['seed'],20261020)
        self.assertFalse(c['private_local_only']);self.assertTrue(c['recommended'])
        self.assertTrue(Path(c['reference_audio']).is_relative_to(ROOT/'assets/voice/recommended'))
    def test_preset_override_resets_model_style_and_speed(self):
        old={**resolve({}),'model':'/example/voice-design','python':'/example/python','model_paths':{'custom_voice':'/example/preset'}}
        c=resolve(old,'Aiden');self.assertEqual(c['mode'],'custom_voice');self.assertEqual(c['model'],'/example/preset');self.assertIsNone(c['instruct']);self.assertEqual(c['delivery_rate'],1.0)
        self.assertEqual(c['python'],'/example/python')
    def test_clone_resets_voice_model_and_has_real_matching_reference(self):
        import hashlib
        c=resolve(resolve({}),'B2-clone');self.assertEqual(c['mode'],'clone');self.assertIn('Base',c['model']);self.assertNotIn('instruct',c)
        self.assertEqual(hashlib.sha256(Path(c['reference_audio']).read_bytes()).hexdigest(),c['reference_sha256']);self.assertTrue(Path(c['reference_text']).read_text().strip())
    def test_old_personal_preset_remains_selected(self):
        c=resolve({'voice_id':'Aiden','model':'/example/custom'});self.assertEqual(c['profile'],'Aiden');self.assertEqual(c['model'],'/example/custom')
    def test_new_course_follows_personal_voice_without_copying_runtime_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'config').mkdir();(p/'config/voice.json').write_text(json.dumps(dict(profile='Dylan',python='/example/python')))
            with patch.dict(os.environ,{'COURSE_CONFIG_DIR':str(p/'config')}):create(p/'course')
            c=json.loads((p/'course/project/project.json').read_text())['voice'];self.assertEqual(c['voice_id'],'Dylan');self.assertNotIn('python',c);self.assertIn('CustomVoice',c['model'])
    def test_set_default_backs_up_and_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'voice.json';p.write_text(json.dumps(dict(profile='Aiden',custom='preserved in backup')));before=p.read_bytes()
            cmd=[sys.executable,str(ROOT/'scripts/qwen3_tts.py'),'--config',str(p),'--profile','B2','--set-default']
            subprocess.run(cmd+['--dry-run'],check=True,capture_output=True);self.assertEqual(p.read_bytes(),before)
            subprocess.run(cmd,check=True,capture_output=True);self.assertEqual(json.loads(p.read_text())['profile'],'B2')
            self.assertEqual(next(p.parent.glob('voice.backup-*.json')).read_bytes(),before)
    def test_invalid_clone_pair_fails_before_generation(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/qwen3_tts.py'),'--ref-audio','missing.wav','--dry-run'],capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertIn(b'both',result.stderr)

if __name__=='__main__':unittest.main()
