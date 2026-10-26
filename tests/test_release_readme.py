"""README release checks and real packaging behavior in disposable directories."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_readme import ReadmeStructureError, check_readme


VALID = '# Skill\n\n## 用途\n\n制作课程。\n\n## 版本更新\n\n### 5.8.5\n\n修订。\n'


class ReadmeStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'README.md'

    def check(self, text):
        self.path.write_text(text, encoding='utf-8')
        return check_readme(self.path)

    def test_current_homepage_and_history_subheadings_pass(self):
        self.assertEqual(self.check(VALID).title, '版本更新')
        self.assertEqual(check_readme(ROOT / 'README.md').title, '版本更新')

    def test_later_sections_are_rejected_with_line_and_fix(self):
        for heading in ['## 安装方式', '# 新介绍', '安装方式\n--------']:
            with self.subTest(heading=heading):
                with self.assertRaisesRegex(ReadmeStructureError, '第 .* 行还有章节.*移到'):
                    self.check(VALID + '\n' + heading + '\n')

    def test_missing_or_non_section_mentions_do_not_pass(self):
        for text in ['', '# Skill\n\n这里提到版本更新。\n', '### 版本更新\n', '```md\n## 版本更新\n```\n']:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ReadmeStructureError, '缺少'):
                    self.check(text)

    def test_duplicate_history_sections_are_rejected(self):
        with self.assertRaisesRegex(ReadmeStructureError, '重复'):
            self.check(VALID + '\n## 版本更新\n')

    def test_backtick_and_tilde_examples_are_ignored(self):
        for fence in ['```', '~~~~']:
            example = f'{fence}markdown\n## 版本更新\n## 安装方式\n{fence}\n'
            with self.subTest(fence=fence):
                self.check(example + '\n' + VALID + '\n' + example)

    def test_shorter_fence_does_not_close_example(self):
        self.check(VALID + '\n~~~~\n~~~\n## 示例标题\n~~~~\n')

    def test_comments_and_indented_examples_are_ignored(self):
        self.check('<!--\n## 版本更新\n-->\n' + VALID + '\n<!-- ## 安装方式 -->\n    ## 示例\n\t## 示例\n')

    def test_comment_markers_inside_code_do_not_hide_later_sections(self):
        with self.assertRaisesRegex(ReadmeStructureError, '还有章节'):
            self.check(VALID + '\n```html\n<!--\n```\n\n## 安装方式\n')

    def test_setext_and_formatted_history_headings(self):
        for heading in ['版本更新\n--------', '## **版本更新** ##', '   ## 版本更新   ###']:
            with self.subTest(heading=heading):
                self.check('# Skill\n\n## 用途\n\n讲解。\n\n' + heading + '\n')

    def test_crlf_and_bom_are_supported(self):
        self.path.write_bytes(('\ufeff' + VALID.replace('\n', '\r\n')).encode('utf-8'))
        self.assertEqual(check_readme(self.path).title, '版本更新')

    def test_cli_returns_nonzero_on_failure(self):
        self.path.write_text(VALID + '\n## 安装\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/check_readme.py'), str(self.path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('版本更新必须放在主页最后', result.stderr)


class PackagingGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for name in ['build_release.py', 'check_readme.py']:
            shutil.copy2(ROOT / 'scripts' / name, scripts / name)
        (self.root / 'VERSION').write_text('5.8.5\n')
        for name in ['corporate-training-motion', 'elearning-course-design']:
            folder = self.root / 'skills' / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Fixture\n---\n')
            (folder / 'package-manifest.json').write_text('original manifest\n')
        validator = self.root / 'skills/corporate-training-motion/scripts'
        validator.mkdir()
        shutil.copy2(ROOT / 'skills/corporate-training-motion/scripts/check_skill_package.py', validator)

    def build(self):
        return subprocess.run([sys.executable, '-B', str(self.root / 'scripts/build_release.py')],
                              capture_output=True, text=True)

    def test_invalid_homepage_stops_before_manifests_or_output_creation(self):
        (self.root / 'README.md').write_text(VALID + '\n## 安装方式\n')
        manifests = list(self.root.glob('skills/*/package-manifest.json'))
        before = {p: p.read_bytes() for p in manifests}
        result = self.build()
        self.assertEqual(result.returncode, 1)
        self.assertIn('打包已阻止', result.stderr)
        self.assertIn('安装方式', result.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in manifests})
        self.assertFalse((self.root / 'dist').exists())

    def test_failure_preserves_previous_zip_and_checksum(self):
        (self.root / 'README.md').write_text('# Missing history\n')
        out = self.root / 'dist'
        out.mkdir()
        archive = out / 'kgxc-course-suite-v5.8.5.zip'
        checksum = out / 'SHA256SUMS'
        archive.write_bytes(b'previous archive')
        checksum.write_text('previous checksum\n')
        before = {p: p.read_bytes() for p in [archive, checksum]}
        self.assertEqual(self.build().returncode, 1)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_valid_homepage_still_builds_verified_zip_and_checksum(self):
        (self.root / 'README.md').write_text(VALID)
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        archive = self.root / 'dist/kgxc-course-suite-v5.8.5.zip'
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual((archive.parent / 'SHA256SUMS').read_text(), digest + '  ' + archive.name + '\n')
        with zipfile.ZipFile(archive) as bundle:
            self.assertIsNone(bundle.testzip())
            self.assertEqual(bundle.read('kgxc-course-suite/README.md').decode(), VALID)
            manifest = json.loads(bundle.read('kgxc-course-suite/bundle-manifest.json'))
            self.assertIn('scripts/check_readme.py', manifest['files'])


if __name__ == '__main__':
    unittest.main()
