"""Publication selection checks use small synthetic trees, never local profiles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class PublicationPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kgxc-publication-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        (self.root / 'scripts').mkdir()
        for name in ['build_plugin.py', 'check_readme.py']:
            shutil.copy2(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        (self.root / 'scripts/build_native_client.py').write_text('print("synthetic chunk fixture")\n')
        for name in ['corporate-training-motion', 'elearning-course-design']:
            skill = self.root / 'skills' / name
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic fixture\n---\n')
        validator = self.root / 'skills/corporate-training-motion/scripts'
        validator.mkdir()
        shutil.copy2(ROOT / 'skills/corporate-training-motion/scripts/check_skill_package.py', validator)
        for skill in (self.root / 'skills').iterdir():
            files = {str(p.relative_to(skill)): hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file()}
            (skill / 'package-manifest.json').write_text(json.dumps(dict(files=files)))
        (self.root / 'package.json').write_text(json.dumps(dict(name='kgxc-course-plugin', version='0.0.1', files=['plugin','docs','README.md'])))
        (self.root / 'plugin.json').write_text(json.dumps(dict(name='kgxc-course-plugin', version='0.0.1')))
        (self.root / 'VERSION').write_text('0.0.2\n')
        (self.root / 'README.md').write_text('# Home\n\n## 版本更新\n\nSynthetic.\n')
        for name in ['cordis.patch.yml', 'release.json', '安装制课插件.command', '安装或更新.command', 'install.sh', 'THIRD_PARTY_NOTICES.md', 'requirements.in', 'requirements.lock', 'requirements-voice.in', 'requirements-voice.lock']:
            (self.root / name).write_text('synthetic\n')
        (self.root / 'plugin').mkdir()
        (self.root / 'plugin/dsh.mjs').write_text('export const fixture=true;\n')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/PLUGIN.md').write_text('# Plugin guide\n')
        (self.root / 'docs/verification-release-v0.0.2.md').write_text('Synthetic verification\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_added.py').write_text('pass\n')
        (self.root / 'config').mkdir()
        (self.root / 'config/tools.example.json').write_text('{}\n')
        (self.root / 'config/tools.json').write_text('private-config\n')
        (self.root / 'docs/.private').mkdir()
        (self.root / 'docs/.private/review.md').write_text('private-review\n')
        (self.root / 'docs/linked.md').symlink_to(self.root / 'config/tools.json')

    def test_plugin_zip_contains_current_docs_tests_and_homepage_without_private_files(self):
        process = subprocess.run([sys.executable, '-B', str(self.root / 'scripts/build_plugin.py')], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        archive = self.root / 'dist/kgxc-course-plugin-v0.0.1.zip'
        with zipfile.ZipFile(archive) as bundle:
            self.assertIsNone(bundle.testzip())
            self.assertEqual((bundle.getinfo('kgxc-course-plugin/install.sh').external_attr >> 16) & 0o777, 0o755)
            self.assertEqual(bundle.read('kgxc-course-plugin/README.md'), (self.root / 'README.md').read_bytes())
            for name in ['docs/verification-release-v0.0.2.md', 'docs/PLUGIN.md', 'tests/test_added.py', 'scripts/build_plugin.py', 'config/tools.example.json']:
                self.assertIn('kgxc-course-plugin/' + name, bundle.namelist())
            for name in ['docs/.private/review.md', 'docs/linked.md', 'config/tools.json']:
                self.assertNotIn('kgxc-course-plugin/' + name, bundle.namelist())
            manifest = json.loads(bundle.read('kgxc-course-plugin/plugin-bundle-manifest.json'))
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(bundle.read('kgxc-course-plugin/' + name)).hexdigest(), digest)

    def test_install_tarball_omits_hidden_reviews_and_links_and_is_reproducible(self):
        spec = importlib.util.spec_from_file_location('publication_installer', ROOT / 'scripts/install_plugin.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with patch.object(installer, 'ROOT', self.root):
            archive = installer.local_package(Path(self.tmp.name) / 'vendor')
            first = archive.read_bytes()
            self.assertEqual(installer.local_package(Path(self.tmp.name) / 'vendor').read_bytes(), first)
        with tarfile.open(archive) as bundle:
            self.assertIn('package/docs/verification-release-v0.0.2.md', bundle.getnames())
            self.assertNotIn('package/docs/.private/review.md', bundle.getnames())
            self.assertNotIn('package/docs/linked.md', bundle.getnames())
            self.assertTrue(all(member.isfile() for member in bundle.getmembers()))


if __name__ == '__main__':
    unittest.main()
