"""Observable palette persistence, real compiler colours and frozen-course boundaries."""
import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'workbench'))
from course_palette import catalog, select, read_plan, bind, binding, check, family, validate, remap_nodes
from workflow import Course, atomic
from teaching_modules import expand, MODULES
from visual_styles import expand as styles, stage_style_assets, registry


class PaletteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)/'course/project'
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_draw_has_a_real_seed_and_reproduces_from_filtered_pool(self):
        plan = select(self.project, ['blue'])
        self.assertEqual(plan['palette'], random.Random(plan['seed']).choice(plan['candidate_pool']))
        self.assertEqual(len(plan['seed']), 32)
        self.assertTrue(all('blue' not in family(p[k]) for p in plan['candidate_pool'] for k in ['canvas','ink','accent','secondary','soft','stroke','muted','surface','error']))
        self.assertNotIn('green', set().union(*(family(p[k]) for p in catalog()['palettes'] for k in ['canvas','ink','accent','soft'])))

    def test_resume_and_repeated_select_do_not_draw_or_rewrite(self):
        plan = select(self.project)
        before = (self.project/'palette-plan.json').read_bytes()
        with patch('course_palette.secrets.token_hex', side_effect=AssertionError('must not redraw')):
            self.assertEqual(plan, select(self.project, seed='ignored'))
            self.assertEqual(plan, read_plan(self.project))
        self.assertEqual(before, (self.project/'palette-plan.json').read_bytes())

    def test_new_storyboard_course_gets_one_palette_and_no_approval(self):
        course = Course(self.project.parent)
        with patch('course_palette.secrets.token_hex', return_value='1'*32) as entropy:
            course.init('新课', planning='storyboard-v1')
            course.init('重复恢复')
            status = course.status()
            self.assertEqual(entropy.call_count, 1)
        self.assertEqual(status['palette_plan'], read_plan(self.project))
        self.assertTrue(all(g['status'] == 'open' for g in status['gates']))

    def test_existing_course_and_frozen_palette_are_preserved(self):
        course = Course(self.project.parent)
        course.init('原课')
        original = course.state_file.read_bytes()
        course.init('继续', planning='storyboard-v1')
        self.assertFalse((self.project/'palette-plan.json').exists())
        self.assertEqual(original, course.state_file.read_bytes())
        state = json.loads(original);state['visual_palette'] = {'approved':'actual-pilot'}
        atomic(course.state_file, state)
        with self.assertRaisesRegex(ValueError, '已有小样'):
            select(self.project)
        self.assertEqual(state, json.loads(course.state_file.read_text()))

    def test_redraw_needs_a_reason_and_keeps_the_prior_record(self):
        first = select(self.project, seed='first')
        with self.assertRaisesRegex(ValueError, '原因'):
            select(self.project, redraw=True)
        second = select(self.project, redraw=True, evidence='用户要求换色', seed='second')
        self.assertEqual(second['revision'], 2)
        self.assertEqual(json.loads(next((self.project/'palette-history').glob('*.json')).read_text()), first)

    def test_user_palette_takes_priority_and_exclusions_cannot_be_ignored(self):
        p = copy.deepcopy(catalog()['palettes'][0]);p.update(id='brand',name='用户品牌色',accent='#1B6044')
        plan = select(self.project, specified=p, evidence='用户指定品牌色')
        self.assertEqual(plan['mode'], 'specified');self.assertIsNone(plan['seed'])
        self.assertEqual(plan['palette']['accent'], '#1B6044')
        with self.assertRaisesRegex(ValueError, '没有合格'):
            select(self.project, ['green'], specified=p, redraw=True, evidence='改为排除绿')
        self.assertEqual(read_plan(self.project), plan)

    def test_no_eligible_pool_does_not_fall_back_and_bad_contrast_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '没有合格'):
            select(self.project, ['blue','purple','red','orange','yellow','pink'])
        self.assertFalse((self.project/'palette-plan.json').exists())
        p = copy.deepcopy(catalog()['palettes'][0]);p['ink'] = p['canvas']
        with self.assertRaisesRegex(ValueError, '对比不足'):
            validate(p)

    def test_palette_contract_reaches_all_seventeen_compiled_modules(self):
        scene = dict(id='S',sourceStartFrame=0,sourceEndFrame=180)
        for name in MODULES:
            with self.subTest(module=name):
                plan = select(self.project, seed='light')
                recipe = dict(id='M',module=name,sceneId='S',beats=[dict(startFrame=0,endFrame=30),dict(startFrame=30,endFrame=60),dict(startFrame=60,endFrame=90)],data=dict(title='核对记录',labels=['项目甲','项目乙','结果'],values=[18,25,30],choices=['核实','代办'],correct=0,items=['订单','实物'],records=['记录甲','记录乙'],assetId='fixture-photo',actorAssets=dict(body='fixture-body',kg='fixture-kg',open='fixture-open',blink='fixture-blink')))
                doc = expand(bind(dict(sourceDurationFrames=180,scenes=[scene],sceneGraph=dict(modules=[recipe])), plan))
                self.assertEqual(check(doc, plan), [])
                self.assertEqual(doc['sceneGraph']['nodes'][0]['fill'], plan['palette']['canvas'])

    def test_styles_compile_using_saved_colours_without_mutating_the_registry(self):
        plan = select(self.project, seed='style')
        scene = dict(id='S',sourceStartFrame=0,sourceEndFrame=120)
        before = registry()['pen-whiteboard']['palette'][:]
        spec = dict(sourceDurationFrames=120,scenes=[scene],sceneGraph=dict(styleScenes=[dict(id='art',style='pen-whiteboard',sceneId='S',data=dict(title='核对',labels=['订单','实物','结果']))]))
        out = styles(bind(spec, plan))
        self.assertEqual(out['visualStyles'][0]['style']['palette'][2], plan['palette']['accent'])
        self.assertEqual(check(out, plan), [])
        self.assertEqual(before, registry()['pen-whiteboard']['palette'])
        legacy = styles(spec)
        self.assertNotIn('coursePalette', legacy)
        self.assertEqual(legacy['visualStyles'][0]['style']['palette'], before)

    def test_default_green_leaks_canvas_changes_and_binding_tampering_fail(self):
        plan = select(self.project, ['green'])
        doc = bind(dict(sourceDurationFrames=60,sceneGraph=dict(nodes=[dict(id='card',type='rect',fill='#94b9a6',width=100,height=100)])), plan)
        self.assertTrue(any('禁用色' in e for e in check(doc, plan)))
        doc['sceneGraph']['nodes'][0]['fill'] = plan['palette']['surface']
        self.assertEqual(check(doc, plan), [])
        doc['coursePalette']['plan_sha256'] = 'wrong'
        self.assertTrue(any('没有沿用' in e for e in check(doc, plan)))
        with self.assertRaisesRegex(ValueError, '底色'):
            bind(dict(sceneGraph=dict(background='#FFFFFF')), plan)

    def test_registered_content_colour_does_not_exempt_an_unrelated_card(self):
        plan = select(self.project, ['green'])
        doc = bind(dict(sourceDurationFrames=60,sceneGraph=dict(nodes=[dict(id='device',type='group',contentColorReason='Apple实际设备的对象本色',children=[dict(id='screen',type='rect',fill='#94b9a6')]),dict(id='card',type='rect',fill='#94b9a6')])), plan)
        errors = check(doc, plan)
        self.assertTrue(any('card' in e for e in errors));self.assertFalse(any('screen' in e for e in errors))

    def test_installed_cli_saves_and_reuses_a_palette(self):
        cli = ROOT/'scripts/course_tools.py'
        a = subprocess.check_output([sys.executable,'-B',str(cli),'palette',str(self.project),'--exclude','green'],text=True)
        b = subprocess.check_output([sys.executable,'-B',str(cli),'palette',str(self.project)],text=True)
        self.assertEqual(json.loads(a), json.loads(b))

    def test_saved_storyboard_and_review_show_the_same_course_palette(self):
        from test_branch_workflow import design, approve_script
        from test_storyboard_workflow import fixture
        course = Course(self.project.parent);course.init('新课', planning='storyboard-v1')
        design(course);approve_script(course)
        course.select_branch('video',course.status()['revision'],'QA video fixture')
        course.save_storyboard(fixture(course),course.status()['revision'])
        plan = read_plan(self.project)
        self.assertEqual(course.storyboard()['coursePalette'], binding(plan))
        self.assertIn(plan['palette']['name'], (self.project/'storyboard.html').read_text())
        self.assertTrue(all(s['selected'] is None for s in course.storyboard()['segments']))

    def test_all_twenty_four_styles_bind_light_and_dark_palettes(self):
        scene = dict(id='S',sourceStartFrame=0,sourceEndFrame=120)
        for target in (catalog()['palettes'][0], catalog()['palettes'][4]):
            folder = self.project/target['id']/'project';folder.mkdir(parents=True)
            plan = select(folder, specified=target, evidence='QA light/dark compiler fixture')
            for sid in registry():
                with self.subTest(palette=target['id'], style=sid):
                    staged = stage_style_assets(folder.parent, sid, ROOT)
                    data = dict(staged['data'],title='核对记录',labels=['订单','实物','结果'],photoAsset='fixture-photo',photoSize=[1000,1000],annotations=[dict(label='设备',point=[.5,.5])])
                    spec = dict(sourceDurationFrames=120,scenes=[scene],assets=staged['assets'],sceneGraph=dict(styleScenes=[dict(id='art',style=sid,sceneId='S',data=data)]))
                    out = styles(bind(spec, plan))
                    self.assertEqual(check(out, plan), [])

    def test_palette_change_updates_the_board_and_invalidates_affected_confirmation(self):
        from test_branch_workflow import design, approve_script
        from test_storyboard_workflow import fixture
        course = Course(self.project.parent);course.init('改色检查', planning='storyboard-v1')
        design(course);approve_script(course);course.select_branch('video',course.status()['revision'],'QA video')
        course.save_storyboard(fixture(course),course.status()['revision'])
        course.choose_shot('all','recommended',course.status()['revision'],'QA choices')
        course.confirm('storyboard',course.status()['revision'],'QA fixture approval')
        old = copy.deepcopy(course.storyboard())
        target=next(p for p in catalog()['palettes'] if p['id'] != read_plan(self.project)['palette']['id'])
        select(self.project,specified=target,redraw=True,evidence='用户要求更换候选配色')
        self.assertEqual(course.storyboard()['coursePalette'], binding(read_plan(self.project)))
        gates = {g['id']:g['status'] for g in course.status()['gates']}
        self.assertEqual(gates['outline'], 'confirmed');self.assertEqual(gates['script'], 'confirmed')
        self.assertEqual(gates['storyboard'], 'stale')
        self.assertEqual([s['selected'] for s in course.storyboard()['segments']], [s['selected'] for s in old['segments']])
        self.assertTrue((self.project/'palette-history/000001-storyboard.json').is_file())


if __name__ == '__main__':
    unittest.main()
