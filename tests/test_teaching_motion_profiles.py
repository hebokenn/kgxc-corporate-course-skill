"""Opt-in teaching phases keep legacy geometry and appear in the real canvas."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/corporate-training-motion'
WORKBENCH = SKILL / 'workbench'
sys.path[:0] = [str(WORKBENCH), str(SKILL / 'scripts')]
from motion_catalog import CATALOG, TEACHING_PROFILE_ACTIONS
from render_routes import effect_errors

SCRIPTS = [
    *(SKILL / 'libraries/illustration/scripts/engine/lib' / name for name in
      ['util.js', 'paint.js', 'motion.js', 'typo.js', 'diagram.js', 'ui.js', 'camera.js']),
    WORKBENCH / 'motion/effects.js',
    WORKBENCH / 'motion/teaching-effects.js',
]


def fixture(kind, **params):
    effect = dict(type=kind, startFrame=20, endFrame=120, **params)
    child = dict(id='object', type='rect', width=30, height=30, fill='#ee1438')
    children = [child]
    if kind == 'callout':
        children = [
            dict(id='leader', type='path', points=[[10, 25], [210, 25], [210, 125]],
                 path='M10 25H210V125', fill=None, stroke='#ee1438', lineWidth=6),
            dict(id='label', type='rect', x=250, y=80, width=160, height=70, fill='#1d8140'),
        ]
    node = dict(id='teaching-effect', type='group', x=100, y=300, width=30,
                height=30, effects=[effect], children=children)
    return dict(fps=24, sourceDurationFrames=150, assets=[], fields=[],
                sceneGraph=dict(background='#ffffff', nodes=[node]),
                scenes=[dict(id='S1', sourceStartFrame=0, sourceEndFrame=150)])


class TeachingProfileTests(unittest.TestCase):
    def test_opt_in_catalog_and_rejections(self):
        self.assertEqual({k for k, v in CATALOG.items() if v.get('motionProfiles') == ['teaching']},
                         {'handoff', 'swimlane-transfer', 'callout'})
        for kind in TEACHING_PROFILE_ACTIONS:
            self.assertEqual(effect_errors(fixture(kind, motionProfile='teaching')), [])
            self.assertEqual(effect_errors(fixture(kind)), [])
        for kind, params in [
            ('handoff', dict(motionProfile='bounce')),
            ('handoff', dict(motionProfile='teaching', tilt=float('inf'))),
            ('swimlane-transfer', dict(motionProfile='teaching', split=.95)),
            ('swimlane-transfer', dict(motionProfile='teaching', split='half')),
        ]:
            self.assertTrue(effect_errors(fixture(kind, **params)))
        for pts in [None, [[1, 2], [1, 2]], [[1, 2], [float('nan'), 0]]]:
            spec = fixture('callout', motionProfile='teaching')
            spec['sceneGraph']['nodes'][0]['children'][0]['points'] = pts
            self.assertTrue(effect_errors(spec))
        # Legacy callout may be a pure fade on a single label.
        legacy = fixture('callout')
        legacy['sceneGraph']['nodes'][0]['children'].pop(0)
        self.assertEqual(effect_errors(legacy), [])

    @unittest.skipUnless(shutil.which('ffprobe'), 'requires FFprobe for actual gallery build')
    def test_current_action_and_module_galleries_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, options in [('actions', []), ('modules', ['--modules'])]:
                dest = root / name
                subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/motion_gallery.py'), str(dest), *options],
                               check=True, capture_output=True, text=True)
                doc = json.loads((dest / 'project/workbench.json').read_text())
                self.assertEqual(doc['continuityPlan']['pauses'], [])
                # Silent technical previews do not mutate or fabricate course approvals.
                self.assertFalse((dest / 'project/course-state.json').exists())
                if name == 'actions':
                    nodes = {n['id']: n for n in doc['sceneGraph']['nodes']}
                    self.assertEqual(len(doc['scenes']), len(CATALOG))
                    from verify_motion_library import gallery_issues
                    self.assertEqual(gallery_issues(dest / 'project', doc), [])
                    for kind in TEACHING_PROFILE_ACTIONS:
                        self.assertEqual(nodes['object-' + kind]['effects'][0]['motionProfile'], 'teaching')
                    for node in nodes.values():
                        node.pop('effects', None)
                    self.assertGreaterEqual(len(gallery_issues(dest / 'project', doc)), len(CATALOG))
                else:
                    from teaching_modules import MODULES
                    self.assertEqual(len(doc['scenes']), len(MODULES))

    @unittest.skipUnless(shutil.which('node'), 'requires Node')
    def test_phase_math_and_legacy_transforms(self):
        test = r"""
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const s={};s.window=s;vm.createContext(s);
for(const f of JSON.parse(process.argv[1]))vm.runInContext(fs.readFileSync(f,'utf8'),s);
const C=s.CourseMotion,n={width:100,height:80};
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,a+' versus '+b);
function ops(kind,q,params) {
  const e={type:kind,startFrame:20,endFrame:120,...params}, calls=[];
  C.beginFrame(20+100*q);
  C.before({translate:(x,y)=>calls.push([x,y]),rotate:a=>calls.push(a)}, {...n,effects:[e]},20+100*q);
  return calls;
}
const hand={dx:200,dy:20,lift:40,tilt:.1};
const teach={...hand,motionProfile:'teaching'};
assert.ok(ops('handoff',.14,teach)[0][0]<0);
const middle=ops('handoff',.48,teach);
assert.ok(middle[0][0]>0&&middle[0][0]<200);
assert.ok(middle[0][1]<-25,'actual arc altitude');
near(ops('handoff',.82,teach)[0][0],200);
near(ops('handoff',.82,teach)[0][1],20);
assert.ok(ops('handoff',.82,teach)[2]>0,'rotation settles on contact');
near(ops('handoff',.96,teach)[2],0);
near(ops('handoff',1,teach)[2],0);
assert.equal(middle.length,4,'no squashing or stretching transforms');
const classic=ops('handoff',.5,hand);near(classic[0][0],100);near(classic[0][1],-30);near(classic[2],.1);
const lanes={motionProfile:'teaching',dx:250,dy:200,split:.5};
for(const t of [.44,.5,.56])assert.deepEqual(ops('swimlane-transfer',t,lanes),[[0,200]]);
assert.ok(ops('swimlane-transfer',.66,lanes)[0][0]>0);
assert.deepEqual(ops('swimlane-transfer',1,lanes),[[250,200]]);
const kids=[{id:'line',type:'path',points:[[0,0],[20,0],[20,10]]},{id:'label',x:75,width:240,opacity:.8}];
const call=q=>C.children({children:kids,effects:[{type:'callout',motionProfile:'teaching',startFrame:20,endFrame:120}]},20+100*q);
assert.equal(call(.08)[1].opacity,0);assert.ok(call(.4)[0].drawProgress>0&&call(.4)[0].drawProgress<1);
assert.equal(call(.69)[0].drawProgress,1);assert.equal(call(.69)[1].opacity,0);
assert.ok(call(.81)[1].opacity>0);assert.equal(call(1)[1].opacity,.8);
assert.equal(call(1)[1].x,75);assert.equal(call(1)[1].width,240);
assert.equal(kids[0].drawProgress,undefined);
"""
        subprocess.run(['node', '-e', test, json.dumps(list(map(str, SCRIPTS)))], check=True)

    @unittest.skipUnless(os.environ.get('KGXC_CHROMIUM_EXECUTABLE') or
                         os.environ.get('COURSE_BROWSER_CHANNEL') == 'chromium',
                         'requires explicit Chromium browser validation')
    def test_actual_canvas_phase_pixels_and_reverse_seek(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            exe = os.environ.get('KGXC_CHROMIUM_EXECUTABLE')
            browser = pw.chromium.launch(headless=True, **({'executable_path': exe} if exe else {}))
            page = browser.new_page()
            page.set_content('<canvas width="1920" height="1080"></canvas>')
            for src in [*SCRIPTS, WORKBENCH / 'starter/scene-engine.js']:
                page.add_script_tag(path=str(src))
            page.evaluate('async d=>await courseWorkbench.apply(d)', fixture('callout', motionProfile='teaching'))

            def probe(frame, points):
                return page.evaluate("""async ([frame, points])=>{
                    await courseWorkbench.seek(frame/24);
                    const canvas=document.querySelector('canvas'), ctx=canvas.getContext('2d');
                    return points.map(([x,y])=>Array.from(ctx.getImageData(x,y,1,1).data));
                }""", [frame, points])

            white, red, green = [255]*4, [238,20,56,255], [29,129,64,255]
            points = [[120,325],[310,410],[360,400]]
            self.assertEqual(probe(20, points), [white, white, white])
            self.assertEqual(probe(56, points), [red, white, white])
            self.assertEqual(probe(90, points), [red, red, white])
            self.assertEqual(probe(115, points), [red, red, green])
            self.assertEqual(probe(56, points), [red, white, white])

            def encoded(frame):
                return page.evaluate("async f=>{await courseWorkbench.seek(f/24);return document.querySelector('canvas').toDataURL()}", frame)

            page.evaluate('async d=>await courseWorkbench.apply(d)',
                          fixture('swimlane-transfer', motionProfile='teaching', dx=250, dy=200))
            at_boundary = encoded(65)
            self.assertEqual(at_boundary, encoded(75))
            self.assertNotEqual(at_boundary, encoded(100))
            self.assertEqual(at_boundary, encoded(65))

            page.evaluate('async d=>await courseWorkbench.apply(d)',
                          fixture('handoff', motionProfile='teaching', dx=200, dy=20, lift=40, tilt=0))
            self.assertEqual(probe(20, [[111,310], [309,326]]), [red, white])
            self.assertEqual(probe(68, [[204,281], [309,326]]), [red, white])
            self.assertEqual(probe(119, [[111,310], [309,326]]), [white, red])
            self.assertEqual(encoded(119), encoded(135))
            browser.close()


if __name__ == '__main__':
    unittest.main()
