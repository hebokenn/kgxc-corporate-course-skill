"""Real entry points reject unfinished production contracts before state/file mutation."""
from contextlib import nullcontext
from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/corporate-training-motion'
sys.path[:0] = [str(ROOT / 'plugin'), str(SKILL / 'workbench')]
from workflow import Course, atomic, read, sha
from production import handoff
from production_preferences import load as preferences, selection_errors
from production_contract import ensure, load
from delivery import deliver, receipt_file
from service import summary


class ProductionContractEntrypointsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / 'workspace'
        self.root = self.workspace / 'courses/fixture'
        self.project = self.root / 'project'
        atomic(self.project / 'workbench.json', dict(title='制作合同入口夹具', scenes=[], media={}))
        self.course = Course(self.root)
        self.course.init('制作合同入口夹具')
        state = read(self.course.state_file)
        state['branch'] = 'video'
        atomic(self.course.state_file, state)
        self.env = patch.dict(os.environ, {'COURSE_CONFIG_DIR': str(self.base / 'config')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp.cleanup)

    def video(self):
        target = self.root / 'delivery/current.mp4'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'entrypoint rejection fixture, not encoded media')
        return target

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/course_tools.py'), *map(str, args)],
                              capture_output=True, text=True, check=False)

    def test_active_missing_preferences_remain_required_without_inventing_answers(self):
        value = preferences(self.project)
        self.assertTrue(value['required'])
        self.assertEqual(len(selection_errors(self.project)), 3)
        self.assertFalse((self.project / 'production-preferences.json').exists())
        ensure(self.project)
        self.assertTrue(load(self.project)['required'])

    def test_direct_and_cli_handoff_include_the_six_contracts(self):
        value = handoff(self.project, dict(branch='video', stage='storyboard', planning_workflow='storyboard-v1'))
        contract = value['production_contract']
        self.assertTrue(contract['required'])
        self.assertEqual(set(contract['requirements']), {'sfx', 'emphasis', 'direction', 'logo', 'chapters', 'bookends'})
        self.assertIn('production-contract.json', contract['contract_path'])
        for key, requirement in contract['requirements'].items():
            self.assertTrue(requirement.get('id'), key)
        # The compact plugin response is the direct MCP/DSH continuation surface.
        direct = summary(self.course)
        self.assertIn('production_handoff', direct['workflow'])
        self.assertIn('production_contract', direct['paths'])
        cli = self.cli('production-contract', self.root, '--read')
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(set(json.loads(cli.stdout)['requirements']), set(contract['requirements']))

    def test_readonly_status_and_direct_summary_do_not_create_contract_files(self):
        before = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        status = self.course.status()
        self.assertTrue(status['production_handoff']['production_contract']['required'])
        direct = summary(self.course)
        self.assertTrue(direct['workflow']['production_handoff']['production_contract']['required'])
        after = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.project / 'production-contract.json').exists())
        self.assertFalse((self.project / 'production-contract-required.json').exists())

    def test_checkpoint_rejects_missing_contract_before_copy_or_registration(self):
        video = self.video()
        ensure(self.project)
        (self.project / 'production-contract.json').unlink()
        before = self.course.state_file.read_bytes()
        for gate in ['pilot', 'final']:
            with self.subTest(gate=gate):
                with self.assertRaisesRegex(ValueError, '制作合同未完成'):
                    self.course.register(gate, ['../delivery/' + video.name], read(self.course.state_file)['revision'])
                self.assertEqual(self.course.state_file.read_bytes(), before)
                self.assertFalse((self.project / 'qa/reviews').exists())
        self.assertFalse((self.project / 'production-contract.json').exists())

    def test_registered_current_video_cannot_become_legacy_by_deleting_its_contract(self):
        video = self.video()
        ensure(self.project)
        state = read(self.course.state_file)
        state.update(gates=dict(final=dict(sha256='recorded-current-gate')),
                     artifacts=dict(final=['../delivery/' + video.name]),
                     deliveries=[dict(branch='video', files=[dict(path='../delivery/' + video.name, sha256=sha(video))])])
        atomic(self.course.state_file, state)
        (self.project / 'production-contract.json').unlink()
        from production import require_contract
        with self.assertRaisesRegex(ValueError, '制作合同未完成'):
            require_contract(self.project, video)

    def test_workflow_checkpoint_cli_uses_the_same_gate(self):
        video = self.video()
        before = read(self.course.state_file)
        result = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/workflow.py'), 'checkpoint',
                                 str(self.root), '--gate', 'final', '--artifact', '../delivery/' + video.name],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('制作合同未完成', result.stderr)
        self.assertEqual(read(self.course.state_file), before)
        self.assertFalse((self.project / 'qa/reviews').exists())

    def test_production_check_accepts_standalone_input_and_returns_json_failure(self):
        document = self.project / 'standalone.json'
        atomic(document, dict(fps=30, sourceDurationFrames=30, scenes=[], media={}))
        video = self.video()
        result = self.cli('production-check', self.root, '--document', document, '--video', video, '--purpose', 'pilot')
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertTrue(report['required'])
        self.assertFalse(report['ready'])
        self.assertTrue(report['errors'])
        self.assertTrue(all({'id', 'requirement', 'message', 'evidence'} <= set(error) for error in report['errors']))

    def test_desktop_save_rejects_contract_before_copy_or_receipt(self):
        video = self.video()
        ensure(self.project)
        status = dict(stage='complete', course_id='a' * 32, title='制作合同入口夹具', revision=9,
                      gates=[dict(id='final', status='delivered')], jobs=[],
                      artifacts=dict(final=['../delivery/' + video.name]), plan=dict(sources=[]))
        course = self.course
        class FinishedSurface:
            root = course.root
            project = course.project
            def locked(self): return nullcontext()
            def status(self): return copy.deepcopy(status)
            def relative(self, name): return course.relative(name)
        destination = self.base / 'desktop'
        with self.assertRaisesRegex(ValueError, '制作合同未完成'):
            deliver(FinishedSurface(), self.workspace, destination)
        self.assertFalse(destination.exists())
        self.assertFalse(receipt_file(status['course_id']).exists())
        self.assertFalse(read(self.course.state_file).get('formal_deliveries'))

    def test_verified_legacy_delivery_is_read_without_migration_or_approval_changes(self):
        video = self.video()
        state = read(self.course.state_file)
        state.update(version='6.4.0', artifacts=dict(final=['../delivery/' + video.name]))
        atomic(self.course.state_file, state)
        atomic(self.project / 'production-preferences.json', dict(choices=dict(customer='none', flower_text='off', sound_effects='off'),
            recorded_existing_production=dict(video_path='../delivery/' + video.name, video_sha256=sha(video),
                actor='historical-producer', evidence='Previously recorded actual legacy video bytes')))
        before_state = self.course.state_file.read_bytes()
        before_preferences = (self.project / 'production-preferences.json').read_bytes()
        value = handoff(self.project, dict(branch='video', stage='complete'))
        self.assertFalse(value['production_contract']['required'])
        result = self.cli('production-check', self.root, '--video', video)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['required'])
        self.assertFalse((self.project / 'production-contract.json').exists())
        self.assertEqual(self.course.state_file.read_bytes(), before_state)
        self.assertEqual((self.project / 'production-preferences.json').read_bytes(), before_preferences)

    def test_cli_activates_legacy_only_explicitly_and_rejects_readonly_combination(self):
        video = self.video()
        state = read(self.course.state_file)
        state.update(version='6.4.0', artifacts=dict(final=['../delivery/' + video.name]))
        atomic(self.course.state_file, state)
        atomic(self.project / 'production-preferences.json', dict(choices=dict(customer='none', flower_text='off', sound_effects='off'),
            recorded_existing_production=dict(video_path='../delivery/' + video.name, video_sha256=sha(video),
                actor='historical-producer', evidence='Previously recorded actual legacy video bytes')))
        before_state = self.course.state_file.read_bytes()
        for option in ['--read', '--dry-run']:
            with self.subTest(option=option):
                rejected = self.cli('production-contract', self.root, '--activate', option)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn('--activate', rejected.stderr)
                self.assertFalse((self.project / 'production-contract.json').exists())
                self.assertFalse((self.project / 'production-contract-required.json').exists())
        activated = self.cli('production-contract', self.root, '--activate')
        self.assertEqual(activated.returncode, 0, activated.stderr)
        self.assertTrue(json.loads(activated.stdout)['required'])
        self.assertTrue((self.project / 'production-contract.json').is_file())
        self.assertTrue((self.project / 'production-contract-required.json').is_file())
        self.assertEqual(self.course.state_file.read_bytes(), before_state)

    def test_courseware_does_not_create_or_require_a_video_contract(self):
        state = read(self.course.state_file)
        state['branch'] = 'courseware'
        atomic(self.course.state_file, state)
        atomic(self.project / 'production-preferences.json', dict(choices={}))
        before = self.course.state_file.read_bytes()
        value = handoff(self.project, dict(branch='courseware', stage='courseware'))
        self.assertFalse(value['production_contract']['required'])
        self.assertFalse(preferences(self.project)['required'])
        self.assertFalse((self.project / 'production-contract.json').exists())
        self.assertEqual(self.course.state_file.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
