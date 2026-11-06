"""Synthetic production-render regressions for natural travel and solid character drawing."""
import copy
import hashlib
import http.server
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'workbench'))
from acting import natural_walk, facing_for, stage, errors, inspect
from render_routes import plan
from backend import Workspace, Handler
from runtime import activate, browser_options
import test_new_course_workbench as fixture
activate()


def design():
    return json.loads((ROOT/'assets/templates/acting-design.json').read_text())


class ChoreographyTests(unittest.TestCase):
    def test_travel_uses_distance_scale_and_cadence_not_narration(self):
        a = natural_walk(30, 200, 560, 1.5)
        b = natural_walk(30, 200, 920, 1.5)
        c = natural_walk(30, 200, 560, 3)
        self.assertGreater(b['steps'], a['steps'])
        self.assertGreater(b['endFrame'], a['endFrame'])
        self.assertLess(c['steps'], a['steps'])
        self.assertEqual(natural_walk(30, 560, 200, 1.5)['steps'], a['steps'])
        with self.assertRaises(ValueError): natural_walk(30, 200, 200)

    def test_crowded_turns_request_reblocking_instead_of_instant_flip(self):
        walks = [dict(startFrame=30, endFrame=70, fromX=0, toX=100),
                 dict(startFrame=75, endFrame=110, fromX=100, toX=0)]
        with self.assertRaisesRegex(ValueError, '转身时间'):
            facing_for(walks, 0, 160)

    def test_stage_uses_real_role_mark_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p/'workbench.json').write_text('{}')
            d = design(); d['characterRole'] = 'store_staff'
            first = stage(d, p, ROOT); second = stage(d, p, ROOT)
            self.assertEqual(first, second)
            a = first['assets'][0]; path = p/a['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), first['node']['vectorActor']['logoSha256'])
            path.write_bytes(b'local edit')
            with self.assertRaisesRegex(ValueError, '已编辑'): stage(d, p, ROOT)
            self.assertEqual(path.read_bytes(), b'local edit')

    def test_route_validation_and_dense_ranges_follow_real_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p/'workbench.json').write_text('{}')
            item = stage(design(), p, ROOT)
            doc = dict(sourceDurationFrames=330, sceneGraph=dict(nodes=[item['node']]), assets=[])
            self.assertEqual(plan(doc)['route'], 'motion-canvas')
            self.assertIn('situational-acting', plan(doc)['requiredEffects'])
            self.assertFalse(errors(doc))
            ranges = inspect(doc)['actors'][0]['denseSourceRanges']
            self.assertTrue(any(r['fromFrame'] <= 24 < r['toFrame'] for r in ranges))
            bad = copy.deepcopy(doc); bad['sceneGraph']['nodes'][0]['scaleX'] = -1
            self.assertTrue(errors(bad))
            bad = copy.deepcopy(doc); bad['sceneGraph']['nodes'][0]['vectorActor']['facing'] = []
            self.assertTrue(errors(bad))
            bad = copy.deepcopy(doc)
            for key in bad['sceneGraph']['nodes'][0]['vectorActor']['facing']: key['yaw'] = 0
            self.assertTrue(any('行进方向' in e for e in errors(bad)))


class ProductionActingTests(unittest.TestCase):
    def test_actual_managed_canvas_motion_opacity_editing_seek_and_encoded_pixels(self):
        from playwright.sync_api import sync_playwright
        from PIL import Image, ImageDraw
        f = fixture.NewCourseTests(); f.setUp()
        server = None
        try:
            item = stage(design(), f.p, ROOT); actor = item['node']
            # Synthetic own-line envelope; it is a technical stimulus, not a voice sample.
            actor['vectorActor']['speech'] = [dict(startFrame=110, envelope=[.8]*20)]
            actor['vectorActor']['targets'] = [dict(frame=0,id='listener')]
            other = copy.deepcopy(actor); other.update(id='listener', x=1150)
            other['vectorActor'] = dict(identity='listener', characterRole='customer', hair='bob',
                                        walks=[], facing=[dict(frame=0, yaw=-math.pi/3)], keys=[])
            audio = f.p/'audio/acting.wav'
            with wave.open(str(audio), 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(b'\0\0'*(24000*11))
            doc = f.ready(dict(sourceDurationFrames=330,
                 scenes=[dict(id='X', title='Synthetic acting', sourceStartFrame=0, sourceEndFrame=330)],
                 media=dict(audio='audio/acting.wav', intro=None, outro=None), captions=[],
                 sceneGraph=dict(background='#f7f4ec', nodes=[actor, other]), assets=[], rendering=dict(route='auto')))
            self.assertTrue((f.p/'native/motion/acting.js').is_file())
            space = Workspace(f.p)
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.workspace = space
            threading.Thread(target=server.serve_forever, daemon=True).start()
            out = Path(os.environ.get('ACTING_TEST_ARTIFACTS', str(f.p/'qa/acting-regression')))
            out.mkdir(parents=True, exist_ok=True)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, **browser_options())
                page = browser.new_page(viewport=dict(width=1920, height=1080), device_scale_factor=1)
                page.goto('http://127.0.0.1:'+str(server.server_port)+'/project/native/index.html')
                page.wait_for_function('window.ready===true')
                page.evaluate('d=>courseWorkbench.apply(d)', doc)
                states = page.evaluate('''async()=>{
                  const rows=[];for(let f=0;f<330;f++){
                    await courseWorkbench.seek(f/30);const states=courseWorkbench.objectReceipt();
                    rows.push({frame:f,actor:states['visitor-demo'].actor,listener:states.listener.actor});
                  }return rows;
                }''')
                walking = 0; planted = {}; max_drift = 0
                for row in states:
                    a = row['actor']; frame = row['frame']
                    self.assertLess(a['maxBoneError'], 1e-6)
                    self.assertLess(a['maxReachError'], 1e-6)
                    self.assertEqual(a['drawing']['minimumRelativeOpacity'], 1)
                    self.assertEqual(len(a['drawing']['armLayers']), 2)
                    self.assertEqual({v['side'] for v in a['drawing']['armLayers']}, {-1, 1})
                    self.assertTrue(a['drawing']['faceFeaturesClipped'])
                    self.assertTrue(any(v['stance'] for v in a['feet'].values()))
                    if a['walking']:
                        walking += 1
                        direction = 1 if frame < 200 else -1
                        for k in ['torsoYaw', 'headYaw', 'hipYaw']:
                            self.assertAlmostEqual(a['orientation'][k], direction*math.pi/2, places=6)
                    for key, foot in a['feet'].items():
                        if foot['stance'] and key in planted:
                            max_drift = max(max_drift, abs(foot['soleX']-planted[key]))
                        if foot['stance']: planted[key] = foot['soleX']
                        else: planted.pop(key, None)
                    self.assertEqual(row['listener']['mouthOpen'], 0)
                    self.assertEqual(a['mouthOpen'], .8 if 110 <= frame < 130 else 0)
                self.assertGreater(walking, 80)
                self.assertLess(max_drift, .01)  # subpixel heel/pivot numerical tolerance
                pairs = [(r['actor']['hands']['left']['x']-r['actor']['shoulders']['left']['x'],
                          r['actor']['hands']['right']['x']-r['actor']['shoulders']['right']['x'])
                         for r in states if 36 <= r['frame'] <= 70]
                means = [sum(v[i] for v in pairs)/len(pairs) for i in range(2)]
                cov = sum((x-means[0])*(y-means[1]) for x,y in pairs)
                den = math.sqrt(sum((x-means[0])**2 for x,y in pairs)*sum((y-means[1])**2 for x,y in pairs))
                self.assertLess(cov/den, -.95)
                await_frame = lambda frame: page.evaluate('async f=>{await courseWorkbench.seek(f/30);return courseWorkbench.objectReceipt()}', frame)
                forward = await_frame(114)
                page.screenshot(path=str(out/'gesture.png'))
                await_frame(270); reverse = await_frame(114)
                self.assertEqual(forward, reverse)
                before = hashlib.sha256(page.screenshot()).hexdigest()
                page.evaluate("courseWorkbench.isolate(['visitor-demo'])")
                await_frame(114)
                self.assertNotEqual(hashlib.sha256(page.screenshot()).hexdigest(), before)
                page.evaluate('courseWorkbench.isolate([])')
                changed = copy.deepcopy(doc)
                field = next(v for v in changed['fields'] if v['objectId'] == 'visitor-demo')
                field['dx'] = 35
                page.evaluate('d=>courseWorkbench.apply(d)', changed)
                moved = await_frame(114)
                self.assertAlmostEqual(moved['visitor-demo']['actor']['hands']['left']['x']-
                                       forward['visitor-demo']['actor']['hands']['left']['x'], 35)
                page.evaluate('d=>courseWorkbench.apply(d)', doc)
                captures = [0, 12, 24, 42, 65, 82, 95, 114, 138, 158, 197, 205, 217, 230, 258, 278, 295]
                for frame in captures:
                    await_frame(frame)
                    page.screenshot(path=str(out/f'pose-{frame:03}.png'))
                # Encode contiguous actual production frames around the former gray-arm failure.
                frame_dir = out/'onset'; frame_dir.mkdir(exist_ok=True)
                source_samples = []
                for i, frame in enumerate(range(21, 49)):
                    await_frame(frame)
                    # Pose and the saved document are passed explicitly to avoid a test-only renderer.
                    point = page.evaluate('''({n,f})=>{const p=CourseActors.pose(n,f),a=p.arms[0];return {
                      x:Math.round(p.g.x+(a.K[0]+a.Q[0])/2*p.scale),
                      y:Math.round(p.g.floor+(a.K[1]+a.Q[1])/2*p.scale)}}''', dict(n=actor, f=frame))
                    page.screenshot(path=str(frame_dir/f'{i:03}.png'))
                    rgb = Image.open(frame_dir/f'{i:03}.png').convert('RGB').getpixel((point['x'], point['y']))
                    self.assertLess(max(abs(x-y) for x,y in zip(rgb,(233,177,139))), 4)
                    source_samples.append((point, rgb))
                browser.close()
            video = out/'synthetic-onset.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(frame_dir/'%03d.png'),
                            '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-threads','2',str(video)], check=True)
            decoded = out/'decoded'; decoded.mkdir(exist_ok=True)
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-start_number','0',str(decoded/'%03d.png')], check=True)
            self.assertEqual(len(list(decoded.glob('*.png'))), 28)
            for i, (point, rgb) in enumerate(source_samples):
                actual = Image.open(decoded/f'{i:03}.png').convert('RGB').getpixel((point['x'], point['y']))
                self.assertLess(max(abs(x-y) for x,y in zip(rgb,actual)), 16)
            sheet = Image.new('RGB', (1440, 1080), '#fffdf7')
            draw = ImageDraw.Draw(sheet)
            for i, frame in enumerate(captures[:12]):
                thumb = Image.open(out/f'pose-{frame:03}.png').convert('RGB'); thumb.thumbnail((480,270))
                x,y = (i%3)*480,(i//3)*270; sheet.paste(thumb,(x,y)); draw.text((x+5,y+5), str(frame), fill='black')
            sheet.save(out/'contact-sheet.png')
            (out/'result.json').write_text(json.dumps(dict(status='pass', actorFrames=len(states)*2,
                  walkingFrames=walking, maxPlantedFootDrift=max_drift,
                  contiguousEncodedFrames=28, scope='synthetic production renderer, not course acceptance'), indent=2)+'\n')
        finally:
            if server: server.shutdown(); server.server_close()
            f.tearDown()


if __name__ == '__main__': unittest.main()
