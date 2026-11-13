"""Cross-host operations against isolated real course files and a real workbench."""
from pathlib import Path
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kgxc_plugin_service', ROOT / 'plugin/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kgxc-plugin-test-')
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config'; self.config.mkdir()
        existing = service.config_dir() / 'tools.json'
        if existing.exists():
            (self.config / 'tools.json').write_bytes(existing.read_bytes())
        self.env = patch.dict(os.environ, {'COURSE_CONFIG_DIR': str(self.config), 'KGXC_COURSES_DIR': str(self.root / 'courses')})
        self.env.start()

    def tearDown(self):
        for record in self.root.rglob('workbench-service.json'):
            try:
                data = json.loads(record.read_text())
                os.kill(data['pid'], signal.SIGTERM)
            except (OSError, ValueError, KeyError):
                pass
        self.env.stop()
        self.tmp.cleanup()

    def test_expired_workbench_restarts_on_the_same_origin_and_keeps_course(self):
        created=service.call('kgxc_course_create',dict(title='空闲恢复技术夹具'))
        self.assertTrue(created['ok'],created);path=created['course_path'];course=service.course_at(path)
        first=json.loads((course.project/'work/workbench-service.json').read_text())
        self.assertTrue(service.workspace_action('workbench_live',dict(course_path=path))['alive'])
        os.kill(first['pid'],signal.SIGTERM)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and service.workspace_action('workbench_live',dict(course_path=path))['alive']:time.sleep(.02)
        self.assertFalse(service.workspace_action('workbench_live',dict(course_path=path))['alive'])
        resumed=service.call('kgxc_course_resume',dict(course_path=path));self.assertTrue(resumed['ok'],resumed)
        second=json.loads((course.project/'work/workbench-service.json').read_text())
        self.assertEqual(first['url'],second['url']);self.assertNotEqual(first['pid'],second['pid'])
        self.assertTrue(service.workspace_action('workbench_live',dict(course_path=path))['alive'])

    def test_missing_source_and_nonempty_target_are_preserved(self):
        target = self.root / 'missing'
        result = service.call('kgxc_course_create', {'title': '测试', 'course_path': str(target), 'source_path': str(self.root / 'no.txt')})
        self.assertFalse(result['ok']); self.assertFalse(target.exists())
        target.mkdir(); (target / 'keep.txt').write_text('保留')
        result = service.call('kgxc_course_create', {'title': '测试', 'course_path': str(target)})
        self.assertFalse(result['ok']); self.assertEqual((target / 'keep.txt').read_text(), '保留')

    def test_workspace_course_default_and_verified_relocation_keep_identity_draft_and_original(self):
        workspace = (self.root / 'workspace').resolve(); workspace.mkdir()
        created = service.call('kgxc_course_create', {'title':'工作区课程','workspace_path':str(workspace)})
        self.assertTrue(created['ok'],created)
        self.assertTrue(Path(created['course_path']).is_relative_to(workspace))
        original = self.root / '原始资料.txt'; original.write_text('保留业务事实')
        legacy = service.call('kgxc_course_create', {'title':'迁移课程','source_path':str(original)})
        course = service.course_at(legacy['course_path'])
        draft = course.project / 'script-editor.json'; draft.write_text('{"text":"人工稿","revision":3}')
        before_state = course.state_file.read_bytes()
        moved = service.workspace_action('relocate', {'course_path':legacy['course_path'],'workspace_path':str(workspace)})
        self.assertTrue(moved['ok'],moved); self.assertTrue(moved['moved'])
        target = Path(moved['course_path'])
        self.assertFalse(Path(legacy['course_path']).exists())
        self.assertEqual((target/'project/course-state.json').read_bytes(),before_state)
        self.assertEqual((target/'project/script-editor.json').read_text(),'{"text":"人工稿","revision":3}')
        self.assertEqual((target/'inputs'/original.name).read_bytes(),original.read_bytes())
        self.assertEqual(service.course_at(legacy['course_path']).root,target)
        self.assertEqual(service.local_json(moved['workbench_url']+'/api/identity')['course_root'],str(target))

    def test_real_course_resume_revision_and_approval_gates(self):
        original = self.root / '核对要求.txt'; original.write_text('先核对订单，再核对编码。')
        result = service.call('kgxc_course_create', {'title': '插件隔离测试', 'source_path': str(original)})
        self.assertTrue(result['ok'], result)
        path = result['course_path']; first = result['workflow']
        self.assertEqual((Path(path) / 'inputs' / original.name).read_bytes(), original.read_bytes())
        identity = service.local_json(result['workbench_url'] + '/api/identity')
        self.assertEqual(identity['course_id'], first['course_id'])
        self.assertEqual(identity['course_root'], path)
        self.assertEqual(identity['lifecycle_policy'],'completed-idle/1')
        resumed=service.call('kgxc_course_resume',{'course_path':path})
        self.assertEqual(resumed['workbench_url'],result['workbench_url'])
        self.assertEqual(service.local_json(resumed['workbench_url']+'/api/identity')['pid'],identity['pid'])
        self.assertEqual(service.call('kgxc_course_editor',{'course_path':path,'action':'read'})['editor_url'],result['editor_url'])
        self.assertEqual(service.call('kgxc_course_list', {})['courses'][0]['course_path'], path)
        blocked = service.call('kgxc_course_update', {'course_path': path, 'base_revision': first['revision'], 'stage': 'script', 'text': '未经确认的正文'})
        self.assertFalse(blocked['ok']); self.assertIn('确认', blocked['error'])
        blocked = service.call('kgxc_course_export', {'course_path': path, 'base_revision': first['revision'], 'purpose': 'final'})
        self.assertFalse(blocked['ok']); self.assertFalse((Path(path) / 'project/work/workbench/exports').exists())
        course = service.course_at(path); plan = course.status()['plan']; source_id = plan['sources'][0]['id']
        plan.update(audience='新同事', performance_task='完成收货核对')
        plan['objectives'] = [dict(id='O', statement='核对订单和编码', evidence='现场完成核对', criterion='信息对应')]
        plan['units'] = [dict(id='U', title='核对', objective_ids=['O'], source_refs=[dict(source_id=source_id, locator='正文')], disposition='core', media='演示', media_reason='观察对应', activity='完成核对', teaching_method='示范后练习', teaching_reason='掌握核对动作')]
        plan['assessments'] = [dict(id='A', objective_ids=['O'], task='核对编码', criteria='编码相同', feedback='逐项复核')]
        saved = service.call('kgxc_course_update', {'course_path': path, 'base_revision': first['revision'], 'stage': 'design', 'data': plan})
        self.assertTrue(saved['ok'], saved)
        stale = service.call('kgxc_course_update', {'course_path': path, 'base_revision': first['revision'], 'stage': 'design', 'data': plan})
        self.assertFalse(stale['ok'])
        # Isolated QA fixture only: exercise the same endpoint used by the review UI.
        confirmed = service.local_json(result['workbench_url'] + '/api/workflow/confirm', dict(gate='outline', baseRevision=saved['workflow']['revision'], evidence='隔离技术测试：测试操作员确认结构；不代表真实课程验收'))
        script = service.call('kgxc_course_update', {'course_path': path, 'base_revision': confirmed['revision'], 'stage': 'script', 'text': '先核对订单，再核对编码。现在请完成一次核对，逐项复核。'})
        self.assertTrue(script['ok'], script)
        self.assertTrue(script['workflow']['ai_review']['enabled'])
        with self.assertRaisesRegex(ValueError,'原件覆盖'):
            course.confirm('script',course.status()['revision'],'技术夹具：不能绕过原件对照人工确认')
        from source_coverage_fixture import confirm_fixture_coverage
        confirm_fixture_coverage(course)
        with self.assertRaisesRegex(ValueError,'AI审阅'):
            course.confirm('script',course.status()['revision'],'技术夹具：不能绕过AI审阅')
        resumed = service.call('kgxc_course_resume', {'course_path': path})
        self.assertTrue(resumed['ok'], resumed)
        self.assertEqual(resumed['workflow']['course_id'], first['course_id'])
        self.assertEqual(resumed['workbench_url'], result['workbench_url'])
        gates = {gate['id']: gate['status'] for gate in resumed['workflow']['gates']}
        self.assertEqual(gates['outline'], 'confirmed'); self.assertEqual(gates['script'], 'open')
        # A fresh process reads exactly the same state, not an in-process cache.
        request = dict(name='kgxc_course_status', arguments=dict(course_path=path))
        process = subprocess.run([sys.executable, str(ROOT / 'plugin/service.py'), '--once'], input=json.dumps(request), text=True, capture_output=True, check=True)
        reloaded = json.loads(process.stdout)
        self.assertEqual(reloaded['workflow']['revision'], resumed['workflow']['revision'])
        self.assertEqual(reloaded['workflow']['gates'], resumed['workflow']['gates'])

    def test_mcp_negotiation_and_tool_errors(self):
        requests = [dict(jsonrpc='2.0', id=1, method='initialize', params=dict(protocolVersion='2025-06-18')), dict(jsonrpc='2.0', method='notifications/initialized'), dict(jsonrpc='2.0', id=2, method='tools/list'), dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(name='kgxc_course_environment', arguments={})), dict(jsonrpc='2.0', id=4, method='tools/call', params=dict(name='kgxc_course_status', arguments=dict(course_path='/missing-course')))]
        process = subprocess.run(['node', str(ROOT / 'plugin/bridge.mjs'), '--stdio'], input=''.join(json.dumps(item) + '\n' for item in requests), text=True, capture_output=True, check=True)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([response['id'] for response in responses], [1, 2, 3, 4])
        self.assertEqual(responses[0]['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(len(responses[1]['result']['tools']), 10)
        self.assertTrue(responses[2]['result']['structuredContent']['ok'])
        self.assertTrue(responses[3]['result']['isError'])

    def test_arguments_cannot_inject_commands_or_fake_confirmation(self):
        self.assertFalse(service.call('kgxc_course_status', {'course_path': '/missing', 'command': 'anything'})['ok'])
        self.assertFalse(service.call('kgxc_course_review', {'gate': 'pilot', 'evidence': 'fake'})['ok'])
        self.assertFalse(service.call('kgxc_course_job', {'course_path': '/missing', 'job_id': '../../file'})['ok'])

    def test_export_uses_edited_timeline_and_document_revision(self):
        project = self.root / 'project'; project.mkdir()
        (project / 'workbench.json').write_text(json.dumps(dict(revision=7, sourceDurationFrames=300, fps=30,
            holds=[dict(sourceFrame=150, frames=60)], cuts=[dict(startFrame=30, endFrame=120)])))
        course = SimpleNamespace(root=self.root, project=project, status=lambda: {'revision': 4}, require_video=lambda gate: None)
        with patch.object(service, 'course_at', return_value=course), patch.object(service, 'workbench', return_value='http://127.0.0.1:12345'), patch.object(service, 'local_json', return_value={'id': 'abcdef123456', 'status': 'queued'}) as submit:
            result = service.call('kgxc_course_export', dict(course_path=str(self.root), base_revision=4, purpose='final'))
        self.assertTrue(result['ok'])
        payload = submit.call_args.args[1]
        self.assertEqual(payload['revision'], 7)
        self.assertEqual(payload['end'], 9)
        self.assertEqual(result['job']['status'], 'queued')


if __name__ == '__main__':
    unittest.main()
