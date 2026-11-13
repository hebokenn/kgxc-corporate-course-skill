"""Installer behavior tests use disposable paths; never touch user skills/config."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kgxc_install',ROOT/'scripts/install.py')
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.base=Path(self.t.name)
        self.root=self.base/'release';self.source=self.root/'skills'/i.NAME;self.source.mkdir(parents=True)
        (self.source/'SKILL.md').write_text('---\nname: corporate-training-motion\ndescription: KGXC\n---\n')
        (self.source/'scripts').mkdir();(self.source/'scripts/kgxc_course.py').write_text('print("ok")\n')
        (self.root/'VERSION').write_text('3.4.0');i.write(self.root/'release.json',dict(repository='hebokenn/kgxc-corporate-course-skill'))
        self.manifest();self.dest=self.base/'installed skill';self.data=self.base/'data';self.cfg=self.base/'config';self.bin=self.base/'bin'
        design=self.root/'skills/elearning-course-design';design.mkdir()
        (design/'SKILL.md').write_text('---\nname: elearning-course-design\ndescription: Course design\n---\n')
        i.write(design/'package-manifest.json',dict(name='elearning-course-design',version='1.0.0',files={'SKILL.md':i.digest(design/'SKILL.md')}))
    def tearDown(self):self.t.cleanup()
    def manifest(self):
        files={str(p.relative_to(self.source)):i.digest(p) for p in self.source.rglob('*') if p.is_file() and p.name!='package-manifest.json'}
        i.write(self.source/'package-manifest.json',dict(name=i.NAME,version='3.4.0',files=files))
    def args(self,*extra):return ['install.py','--dest',str(self.dest),'--data-dir',str(self.data),'--config-dir',str(self.cfg),'--bin-dir',str(self.bin),*extra]
    def invoke(self,*extra):
        with patch.object(i,'ROOT',self.root),patch('sys.argv',self.args(*extra)):return i.main()
    def test_clean_repeat_and_tamper_detection(self):
        self.assertEqual(i.install_skill(self.source,self.dest,self.data),'installed')
        self.assertEqual(i.install_skill(self.source,self.dest,self.data),'already_current')
        (self.dest/'SKILL.md').write_text('local edits')
        with self.assertRaisesRegex(ValueError,'本地修改'):i.install_skill(self.source,self.dest,self.data)
        self.assertEqual((self.dest/'SKILL.md').read_text(),'local edits')
        i.install_skill(self.source,self.dest,self.data,replace=True)
        self.assertEqual(next((self.data/'backups').glob('*/corporate-training-motion/SKILL.md')).read_text(),'local edits')
    def test_modified_source_and_symlink_rejected(self):
        (self.source/'SKILL.md').write_text('tampered')
        with self.assertRaises(ValueError):i.install_skill(self.source,self.dest,self.data)
        self.manifest();other=self.base/'other';other.mkdir();self.dest.symlink_to(other,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'符号链接'):i.install_skill(self.source,self.dest,self.data)
    def test_update_rolls_back_if_final_move_fails(self):
        i.install_skill(self.source,self.dest,self.data);old=(self.dest/'SKILL.md').read_bytes()
        (self.source/'SKILL.md').write_text('updated');self.manifest();original=Path.rename
        def rename(path,target):
            if path.name.startswith('.corporate-training-motion-'):raise OSError('simulated final move failure')
            return original(path,target)
        with patch.object(Path,'rename',rename),self.assertRaises(OSError):i.install_skill(self.source,self.dest,self.data)
        self.assertEqual((self.dest/'SKILL.md').read_bytes(),old)
    def test_runtime_preserves_user_config_and_default_installs_voice(self):
        i.write(self.cfg/'tools.json',dict(python='/personal/python',custom='kept'))
        i.write(self.cfg/'voice.json',dict(voice_id='Aiden',custom='kept'))
        with patch.object(i,'prepare_runtime',return_value=dict(python='/generated/python',node='/generated/node')) as media,patch.object(i,'prepare_voice') as voice,patch.object(i.subprocess,'call',return_value=0) as doctor:
            self.assertEqual(self.invoke('--uv','uv'),0);self.assertEqual(self.invoke('--uv','uv'),0)
            self.assertEqual(media.call_count,2);self.assertEqual(voice.call_count,2)
            self.assertNotIn('--media-only',doctor.call_args.args[0])
        tools=i.read(self.cfg/'tools.json');self.assertEqual(tools['python'],'/personal/python');self.assertEqual(tools['custom'],'kept')
        self.assertEqual(i.read(self.cfg/'voice.json')['custom'],'kept')
        self.assertIn(str(self.cfg),(self.bin/'kgxc-course').read_text())
    def test_skill_only_and_uninstall_keep_configs_and_courses(self):
        i.write(self.cfg/'tools.json',dict(custom='kept'));course=self.base/'my course';course.mkdir();(course/'original').write_text('keep')
        with patch.object(i,'prepare_runtime') as media,patch.object(i,'prepare_voice') as voice:
            self.assertEqual(self.invoke('--skill-only'),0);self.assertEqual(self.invoke('--skill-only'),0)
            media.assert_not_called();voice.assert_not_called()
        self.assertEqual(self.invoke('--uninstall'),0);self.assertFalse(self.dest.exists());self.assertFalse((self.bin/'kgxc-course').exists())
        self.assertFalse((self.dest.parent/'elearning-course-design').exists())
        self.assertEqual((course/'original').read_text(),'keep');self.assertEqual(i.read(self.cfg/'tools.json')['custom'],'kept')
        self.assertTrue(list((self.data/'uninstalled').glob('*/corporate-training-motion/SKILL.md')))
        with self.assertRaises(ValueError):self.invoke('--uninstall')
    def test_foreign_launcher_is_preserved(self):
        self.bin.mkdir();(self.bin/'kgxc-course').write_text('user command')
        with self.assertRaisesRegex(ValueError,'同名文件'):self.invoke('--skill-only')
        self.assertEqual((self.bin/'kgxc-course').read_text(),'user command')
    def test_skip_voice_reports_media_only(self):
        with patch.object(i,'prepare_runtime',return_value={}),patch.object(i,'prepare_voice') as voice,patch.object(i.subprocess,'call',return_value=0) as doctor:
            self.assertEqual(self.invoke('--uv','uv','--skip-voice'),0);voice.assert_not_called();self.assertIn('--media-only',doctor.call_args.args[0])

if __name__=='__main__':unittest.main()
