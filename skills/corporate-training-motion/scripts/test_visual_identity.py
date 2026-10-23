"""Regressions for palette drift between a reviewed pilot and new scenes."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workbench'))
from visual_identity import capture, check, digest


def document():
    return dict(sourceDurationFrames=60, scenes=[dict(id='A', sourceStartFrame=0, sourceEndFrame=30), dict(id='B', sourceStartFrame=30, sourceEndFrame=60)],
                holds=[], cuts=[], sceneGraph=dict(background='#ffffff', nodes=[
                    dict(id='card', type='rect', sceneId='A', fill='#eeeeee'),
                    dict(id='label', type='text', sceneId='A', fill='#222222', text='核对'),
                    dict(id='emphasis', type='text', sceneId='A', fill='#b12b3e', text='检查')]))


class PaletteTests(unittest.TestCase):
    def test_same_palette_and_new_neutral_layout_pass(self):
        doc = document(); lock = capture(doc)
        doc['sceneGraph']['nodes'].append(dict(id='new', type='rect', sceneId='B', fill='#f7f7f7'))
        self.assertEqual(check(doc, lock), [])

    def test_green_container_and_changed_canvas_are_rejected(self):
        for field in ['surface', 'canvas']:
            doc = document(); lock = capture(doc)
            if field == 'surface':
                doc['sceneGraph']['nodes'].append(dict(id='new', type='rect', sceneId='B', fill='#eef1ed'))
            else:
                doc['sceneGraph']['background'] = '#edf3ed'
            self.assertTrue(check(doc, lock))

    def test_approved_colored_style_is_preserved(self):
        doc = document(); doc['sceneGraph']['background'] = '#153950'
        doc['sceneGraph']['nodes'][0]['fill'] = '#426577'
        self.assertEqual(check(doc, capture(doc)), [])

    def test_content_color_exception_needs_a_real_reason(self):
        doc = document(); lock = capture(doc)
        product = dict(id='phone', type='group', contentColorReason='手机产品外观与屏幕真实内容颜色', children=[dict(id='screen', type='rect', fill='#6a9b7e')])
        doc['sceneGraph']['nodes'].append(product)
        self.assertEqual(check(doc, lock), [])
        product['contentColorReason'] = True
        self.assertTrue(check(doc, lock))

    def test_new_green_hidden_outside_pilot_is_not_approved(self):
        doc = document(); doc['sceneGraph']['nodes'].append(dict(id='unseen', type='rect', sceneId='B', fill='#eef1ed'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'pilot.json').write_text(json.dumps(dict(range=dict(firstFrame=0, lastFrame=30))))
            lock = capture(doc, [dict(path='pilot.mp4', sha256='fixture')], root)
        self.assertEqual(lock['scope'], 'exported pilot source intervals')
        self.assertTrue(any('unseen.fill' in e for e in check(doc, lock)))

    def test_gradient_and_navigation_are_checked(self):
        doc = document(); lock = capture(doc)
        doc['navigation'] = dict(progress=dict(background='#eef1ed', track='#eeeeee', color='#b12b3e'))
        self.assertTrue(any('navigation.progress.background' in e for e in check(doc, lock)))
        doc.pop('navigation'); doc['sceneGraph']['nodes'][0]['fill'] = dict(type='linear', stops=[[0, '#ffffff'], [1, '#eef1ed']])
        self.assertTrue(check(doc, lock))

    def test_new_colored_highlight_is_checked(self):
        doc = document(); lock = capture(doc)
        doc['sceneGraph']['nodes'][0]['effects'] = [dict(type='marker', color='#eef1ed')]
        self.assertTrue(any('.effects.' in e for e in check(doc, lock)))

    def test_lock_changes_are_visible_and_historical_documents_are_untouched(self):
        doc = document(); lock = capture(doc); changed = copy.deepcopy(lock)
        changed['palette']['canvas'] = ['#edf3ed']
        self.assertNotEqual(digest(lock), digest(changed))
        self.assertEqual(check(doc, None), [])


if __name__ == '__main__':
    unittest.main()
