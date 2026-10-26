import json
from pathlib import Path
import tempfile
import unittest
import wave
from voice_library import register, load, generate_command, set_defaults, read_defaults
from qwen3_tts import resolve, ROOT
from unittest.mock import patch
import subprocess
import sys


class LocalVoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.root = self.p / 'voices'
        self.audio = self.p / 'source.wav'
        with wave.open(str(self.audio), 'wb') as f:
            f.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\x00\x00' * 240)
        self.text = self.p / 'source.txt'
        self.text.write_text('这是合成测试参考，不是实际声音验收。')

    def add(self, name='sample'):
        return register(self.root, name, self.audio, self.text, '本地测试', 'synthetic fixture', 1.0)

    def test_preserves_reference_bytes_and_defaults(self):
        config = self.p / 'voice.json'
        config.write_text('{"profile":"B2"}')
        before = config.read_bytes()
        data = self.add()
        path, actual = load(self.root, 'sample')
        self.assertEqual((path / 'reference.wav').read_bytes(), self.audio.read_bytes())
        self.assertEqual((path / 'reference.txt').read_bytes(), self.text.read_bytes())
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse(actual['default_changed'])

    def test_duplicate_cannot_replace_existing_voice(self):
        self.add()
        before = (self.root / 'sample/profile.json').read_bytes()
        with self.assertRaises(ValueError): self.add()
        self.assertEqual((self.root / 'sample/profile.json').read_bytes(), before)

    def test_modified_reference_fails_before_generation(self):
        self.add()
        (self.root / 'sample/reference.txt').write_text('changed')
        with self.assertRaises(ValueError):
            generate_command(self.root, 'sample', self.text, self.p / 'new.wav')

    def test_generated_command_uses_private_verified_reference(self):
        self.add()
        cmd, data = generate_command(self.root, 'sample', self.text, self.p / 'new.wav', self.p / 'tools.json')
        self.assertEqual(cmd[cmd.index('--profile') + 1], 'B2-clone')
        self.assertEqual(Path(cmd[cmd.index('--ref-audio') + 1]).read_bytes(), self.audio.read_bytes())
        self.assertEqual(cmd[cmd.index('--delivery-rate') + 1], '1.0')
        self.assertTrue(data['private_local_only'])

    def test_invalid_id_and_existing_output_preserved(self):
        with self.assertRaises(ValueError): self.add('../escape')
        self.add()
        out = self.p / 'new.wav'
        out.write_bytes(b'keep')
        with self.assertRaises(ValueError): generate_command(self.root, 'sample', self.text, out)
        self.assertEqual(out.read_bytes(), b'keep')

    def test_empty_transcript_does_not_create_partial_profile(self):
        self.text.write_text(' ')
        with self.assertRaises(ValueError): self.add()
        self.assertFalse((self.root / 'sample').exists())

    def test_gender_defaults_update_primary_voice_and_preserve_runtime(self):
        self.add('male')
        self.add('female')
        config = self.p / 'voice.json'
        config.write_text(json.dumps(dict(profile='B2', python='/local/runtime', model_paths={'clone':'/local/base'}, instruct='old design')))
        before = config.read_bytes()
        set_defaults(self.root, 'male', 'female', 'male', 'Explicit test user selection')
        actual = json.loads(config.read_text())
        self.assertEqual(actual['profile'], 'male')
        self.assertEqual(actual['python'], '/local/runtime')
        self.assertEqual(actual['model_paths']['clone'], '/local/base')
        self.assertNotIn('instruct', actual)
        self.assertEqual(next(self.p.glob('voice.backup-*.json')).read_bytes(), before)
        self.assertEqual(read_defaults(self.root)['female'], 'female')

    def test_alias_resolution_uses_base_and_exact_reference(self):
        self.add('named')
        actual = resolve({'profile':'B2', 'model_paths':{'clone':'/local/base'}}, 'named', library=self.root)
        self.assertEqual(actual['profile'], 'named')
        self.assertEqual(actual['voice_id'], 'named')
        self.assertEqual(actual['mode'], 'clone')
        self.assertEqual(actual['model'], '/local/base')
        self.assertEqual(Path(actual['reference_audio']).read_bytes(), self.audio.read_bytes())

    def test_gender_cli_resolves_female_without_generation(self):
        self.add('male')
        self.add('female')
        set_defaults(self.root, 'male', 'female', 'male', 'Explicit test user selection')
        result = subprocess.run([sys.executable, str(ROOT/'scripts/qwen3_tts.py'), '--config', str(self.p/'voice.json'), '--voice-library', str(self.root), '--gender','female','--dry-run'],check=True,capture_output=True,text=True)
        actual = json.loads(result.stdout)
        self.assertEqual(actual['profile'], 'female')
        self.assertEqual(actual['mode'], 'clone')
        self.assertEqual(actual['delivery_rate'], 1.0)
        self.assertFalse(any(self.p.glob('*.wav.json')))

    def test_chinese_named_voice_cli_uses_verified_reference_without_changing_defaults(self):
        self.add('示例讲师')
        config = self.p/'voice.json'
        config.write_text('{"profile":"B2"}')
        before = config.read_bytes()
        result = subprocess.run([sys.executable,str(ROOT/'scripts/qwen3_tts.py'),'--config',str(config),'--voice-library',str(self.root),'--voice','示例讲师','--dry-run'],check=True,capture_output=True,text=True)
        actual = json.loads(result.stdout)
        self.assertEqual(actual['voice_id'],'示例讲师')
        self.assertEqual(actual['mode'],'clone')
        self.assertEqual(Path(actual['reference_audio']).read_bytes(),self.audio.read_bytes())
        self.assertEqual(config.read_bytes(),before)
        for name in ['示例讲师/../escape','示例讲师\\escape','..','/示例讲师','示例讲师.name']:
            with self.assertRaises(ValueError):self.add(name)

    def test_missing_default_reference_does_not_change_primary_config(self):
        self.add('male')
        config = self.p/'voice.json'
        config.write_text('{"profile":"B2"}')
        before = config.read_bytes()
        with self.assertRaises(OSError):
            set_defaults(self.root, 'male', 'missing', 'male', 'Explicit test user selection')
        self.assertEqual(config.read_bytes(), before)

    def test_clean_defaults_use_both_recommendations_without_writing_config(self):
        defaults = read_defaults(self.root)
        self.assertEqual((defaults['male'], defaults['female']), ('didi', 'pipi'))
        self.assertFalse((self.p/'voice-defaults.json').exists())
        self.assertFalse(self.root.exists())

    def test_clean_gender_cli_needs_no_private_voice_registration(self):
        for gender, identity in [('male', 'didi'), ('female', 'pipi')]:
            with self.subTest(gender=gender):
                result = subprocess.run([sys.executable, str(ROOT/'scripts/qwen3_tts.py'), '--config', str(self.p/'absent.json'), '--voice-library', str(self.root), '--gender', gender, '--dry-run'],check=True,capture_output=True,text=True)
                actual = json.loads(result.stdout)
                self.assertEqual(actual['profile'], identity)
                self.assertTrue(Path(actual['reference_audio']).is_file())
                self.assertFalse(actual['private_local_only'])
        self.assertFalse(self.root.exists())

    def test_personal_same_name_overrides_bundled_voice_and_remains_private(self):
        self.add('didi')
        actual = resolve({}, 'didi', library=self.root)
        self.assertEqual(Path(actual['reference_audio']), self.root/'didi/reference.wav')
        self.assertTrue(actual['private_local_only'])
        self.assertFalse(actual['recommended'])
        (self.root/'didi/reference.txt').write_text('changed')
        with self.assertRaises(ValueError):
            resolve({}, 'didi', library=self.root)

    def test_selecting_recommendations_does_not_modify_bundled_profiles(self):
        bundle = ROOT/'assets/voice/recommended'
        before = {p:p.read_bytes() for p in bundle.glob('*/profile.json')}
        set_defaults(self.root, 'didi', 'pipi', 'female', 'Explicit fixture selection')
        self.assertEqual(json.loads((self.p/'voice.json').read_text())['profile'], 'pipi')
        self.assertEqual(read_defaults(self.root)['default_gender'], 'female')
        self.assertEqual(before, {p:p.read_bytes() for p in before})
        self.assertFalse(self.root.exists())

    def test_changed_bundled_reference_fails_instead_of_silent_fallback(self):
        import shutil
        bundle = self.p/'bundled'
        shutil.copytree(ROOT/'assets/voice/recommended', bundle)
        (bundle/'pipi/reference.txt').write_text('changed reference transcript')
        with patch('voice_library.BUNDLED', bundle), self.assertRaises(ValueError):
            read_defaults(self.root)


if __name__ == '__main__': unittest.main()
