"""Isolated archive validation and wait logic; never install or restart an app."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

PATH = Path(__file__).resolve().parents[1] / 'plugin/update-install-helper.py'
SPEC = importlib.util.spec_from_file_location('update_install_helper', PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class UpdateInstallHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.package = self.base / 'download.zip'
        self.target = self.base / 'target'
        self.target.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, *, version='0.9.3', bad_hash=False, extra=None, omitted=None):
        info = json.dumps(dict(name=helper.NAME, version=version)).encode()
        entries = {'package.json': info, 'plugin.json': info, 'VERSION': b'6.9.2\n',
                   'plugin/dsh.mjs': b'// fixture', 'scripts/install_plugin.py': b'# never run'}
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}
        if bad_hash:
            hashes['plugin/dsh.mjs'] = '1' * 64
        if omitted:
            hashes.pop(omitted)
        with zipfile.ZipFile(self.package, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, value in entries.items():
                z.writestr(helper.NAME + '/' + name, value)
            z.writestr(helper.NAME + '/' + helper.MANIFEST,
                       json.dumps(dict(name=helper.NAME, version=version, core_version='6.9.2', files=hashes)))
            if extra:
                z.writestr(*extra)
        self.package.chmod(0o600)
        return hashlib.sha256(self.package.read_bytes()).hexdigest()

    def test_hash_pinned_complete_manifest_and_correct_version(self):
        digest = self.archive()
        helper.private_file(self.package)
        helper.verify_extract(self.package, '0.9.3', digest, self.target)
        self.assertTrue((self.target / 'scripts/install_plugin.py').is_file())
        self.assertFalse((self.target / helper.MANIFEST).exists())

    def test_wrong_outer_sha_or_package_version_rejected(self):
        digest = self.archive()
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            helper.verify_extract(self.package, '0.9.3', '0' * 64, self.target)
        with self.assertRaisesRegex(ValueError, '发布版本'):
            helper.verify_extract(self.package, '0.9.4', digest, self.target)
        self.assertFalse(list(self.target.iterdir()))

    def test_inner_hash_and_exact_manifest_checked(self):
        digest = self.archive(omitted='plugin/dsh.mjs')
        with self.assertRaisesRegex(ValueError, '文件列表'):
            helper.verify_extract(self.package, '0.9.3', digest, self.target)
        digest = self.archive(bad_hash=True)
        with self.assertRaisesRegex(ValueError, '文件校验'):
            helper.verify_extract(self.package, '0.9.3', digest, self.target)

    def test_archive_rejects_symlink_traversal_and_case_collision(self):
        symlink = zipfile.ZipInfo(helper.NAME + '/symlink')
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for extra in [(symlink, b'plugin'), (helper.NAME + '/../escape', b'x'), (helper.NAME + '/PACKAGE.JSON', b'x')]:
            with self.subTest(extra=extra[0]):
                digest = self.archive(extra=extra)
                with self.assertRaises(ValueError):
                    helper.verify_extract(self.package, '0.9.3', digest, self.target)
                self.assertFalse(list(self.target.iterdir()))

    def test_private_file_and_atomic_status(self):
        self.archive()
        self.package.chmod(0o644)
        with self.assertRaisesRegex(ValueError, '私有普通文件'):
            helper.private_file(self.package)
        status = self.base / 'status.json'
        helper.private_file(status, existing=False)
        helper.write_status(status, 'waiting', '0.9.3', '等待')
        helper.write_status(status, 'installed', '0.9.3', '安装')
        self.assertEqual(stat.S_IMODE(status.stat().st_mode), 0o600)
        self.assertEqual(json.loads(status.read_text()), dict(status='installed', version='0.9.3', message='安装'))

    def test_wait_for_exact_host_and_ignores_reused_pid(self):
        app = str(helper.APP_EXECUTABLE)
        app_helper = str(self.base / 'plugin') + '/plugin/service.py'
        rows = iter([{101: 'node exact-old-host'}, {101: 'node exact-old-host', 102: app},
                     {103: 'python "' + app_helper + '"'}, {101: 'node unrelated-reused'}, {}])
        ticks = [0]
        def sleep(delay):
            ticks[0] += delay
        helper.wait_for_exit([101], self.base / 'plugin', seconds=3, read_processes=lambda: next(rows),
                             clock=lambda: ticks[0], sleep=sleep)
        self.assertEqual(ticks[0], 1.5)

    def test_timeout_does_not_kill_or_proceed(self):
        ticks = [0]
        with self.assertRaisesRegex(ValueError, '未安装'):
            helper.wait_for_exit([101], self.base / 'plugin', seconds=1,
                                 read_processes=lambda: {101: 'node host'}, clock=lambda: ticks[0],
                                 sleep=lambda delta: ticks.__setitem__(0, ticks[0] + delta))


if __name__ == '__main__':
    unittest.main()
