import json
from pathlib import Path
import tempfile
import unittest
import wave
from voice_library import register, load, generate_command, set_defaults, read_defaults
from qwen3_tts import resolve, ROOT
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

    def test_missing_default_reference_does_not_change_primary_config(self):
        self.add('male')
        config = self.p/'voice.json'
        config.write_text('{"profile":"B2"}')
        before = config.read_bytes()
        with self.assertRaises(OSError):
            set_defaults(self.root, 'male', 'missing', 'male', 'Explicit test user selection')
        self.assertEqual(config.read_bytes(), before)


if __name__ == '__main__': unittest.main()
