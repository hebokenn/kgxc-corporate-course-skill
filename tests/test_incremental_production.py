import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/corporate-training-motion/scripts'
sys.path.insert(0, str(SCRIPTS))
from incremental_production import SCHEMA, compare, snapshot


class IncrementalProductionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.course = Path(self.directory.name) / 'course'
        self.project = self.course / 'project'
        self.project.mkdir(parents=True)
        self.nodes = dict(
            voice=dict(layer='narration', inputs=['script.txt'], output='narration.wav'),
            body=dict(layer='body', inputs=['scene.txt'], dependsOn=['voice'], output='body.mp4'),
            mix=dict(layer='mix', inputs=['sfx.json'], dependsOn=['voice'], output='mix.wav'),
            mux=dict(layer='package', inputs=['export.json'], dependsOn=['body','mix'], output='final.mp4'))
        self.spec = dict(schema=SCHEMA, nodes=self.nodes)
        for node in self.nodes.values():
            for file in node['inputs'] + [node['output']]:
                (self.project/file).write_text(file)
        self.baseline = snapshot(self.course, self.spec)

    def changed(self):
        return compare(self.course, self.baseline, snapshot(self.course, self.spec))['decisions']

    def test_sfx_only_keeps_approved_voice_and_render(self):
        (self.project/'sfx.json').write_text('different timing')
        changes = self.changed()
        self.assertEqual([k for k, v in changes.items() if v['action'] == 'reuse'], ['voice', 'body'])
        self.assertEqual(changes['mix']['reasons'], ['input_bytes_or_paths_changed'])
        self.assertEqual(changes['mux']['upstream'], ['mix'])

    def test_modified_upstream_rebuilds_all_dependents(self):
        (self.project/'script.txt').write_text('one changed sentence')
        self.assertTrue(all(v['action'] == 'rebuild' for v in self.changed().values()))

    def test_missing_or_changed_artifact_rebuilds_and_invalidates_consumers(self):
        (self.project/'body.mp4').unlink()
        changes = self.changed()
        self.assertEqual(changes['body']['reasons'], ['previous_output_missing_or_bytes_changed'])
        self.assertEqual(changes['mux']['upstream'], ['body'])
        self.assertEqual(changes['mix']['action'], 'reuse')
        (self.project/'body.mp4').write_text('same filename, different bytes')
        self.assertEqual(self.changed()['body']['action'], 'rebuild')

    def test_refuses_stale_snapshot_and_other_course(self):
        (self.project/'sfx.json').write_text('different bytes')
        with self.assertRaisesRegex(ValueError, '已过期'):
            compare(self.course, self.baseline, self.baseline)
        other = self.course.parent/'other'
        (other/'project').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, '不是当前课程'):
            compare(other, self.baseline, self.baseline)

    def test_refuses_untracked_dependency_cycle_and_duplicate_writer(self):
        for updates, message in [
            ({'dependsOn': ['not-declared']}, '未登记'),
            ({'dependsOn': ['mux']}, '依赖循环'),
            ({'output': 'body.mp4'}, '两个产物写入'),
            ({'inputs': ['mix.wav']}, 'dependsOn'),
        ]:
            with self.subTest(updates=updates):
                modified = copy.deepcopy(self.spec)
                modified['nodes']['voice'].update(updates)
                with self.assertRaisesRegex(ValueError, message):
                    snapshot(self.course, modified)

    def test_refuses_symlink_and_absolute_input(self):
        (self.project/'link.txt').symlink_to(self.project/'script.txt')
        for name in ['link.txt', str(self.project/'script.txt'), '../script.txt']:
            with self.subTest(name=name):
                modified = copy.deepcopy(self.spec)
                modified['nodes']['voice']['inputs'] = [name]
                with self.assertRaises(ValueError):
                    snapshot(self.course, modified)

    def test_cli_output_read_only_and_fail_closed(self):
        spec_file = self.course/'spec.json'
        spec_file.write_text(json.dumps(self.spec))
        command = [sys.executable, str(SCRIPTS/'incremental_production.py')]
        result = subprocess.run(command + ['snapshot', str(self.course), '--spec', str(spec_file)],
                                check=True, capture_output=True, text=True)
        previous = self.course/'baseline.json'
        previous.write_text(result.stdout)
        self.assertEqual(json.loads(result.stdout), self.baseline)
        count = len(list(self.project.iterdir()))
        result = subprocess.run(command + ['compare', str(self.course), '--previous', str(previous), '--current', str(previous)],
                                check=True, capture_output=True, text=True)
        self.assertTrue(all(v['action'] == 'reuse' for v in json.loads(result.stdout)['decisions'].values()))
        self.assertEqual(len(list(self.project.iterdir())), count)
        (self.project/'script.txt').unlink()
        result = subprocess.run(command + ['compare', str(self.course), '--previous', str(previous), '--current', str(previous)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('无法安全计划复用', result.stderr)
        self.assertFalse(result.stdout)


if __name__ == '__main__':
    unittest.main()
