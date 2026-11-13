#!/usr/bin/env python3
"""Regressions for isolated 'continuous' slides, missing source figures and spoken closing."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from check_course_completeness import CLOSING, closing_errors, map_errors, image_errors, check
from scaffold import create
from validate import validate


def run():
    project = {'deliverable': 'full', 'source_pages': 2, 'content_contract_version': 1}
    segments = [{'text': '回顾操作主线。'}, {'text': CLOSING + '。'}]
    assert not closing_errors(project, segments)
    assert closing_errors(project, segments[:-1])
    assert closing_errors(project, segments + [{'text': '再见。'}])
    assert closing_errors(project, segments + segments[-1:])
    assert not closing_errors({'deliverable': 'pilot'}, segments[:-1])
    scenes = [dict(id=sid, unit_id='U1', canvas_id='main', map_id='M1',
                   map_node_ids=['collect', 'submit'], knowledge_relation='process',
                   view_mode=mode, source_image_ids=['I1'] if mode == 'local' else [])
              for sid, mode in [('B1', 'overview'), ('B2', 'local'), ('B3', 'return')]]
    maps = {'maps': [dict(id='M1', canvas_id='main', diagram_type='flowchart',
                         nodes=[dict(id='collect', label='采集'), dict(id='submit', label='提交')],
                         edges=[dict(type='sequence', **{'from': 'collect', 'to': 'submit'}, label='采集完成后提交')],
                         overview_scene_id='B1', return_scene_ids=['B3'])]}
    assert not map_errors(maps, scenes)
    assert any('MAP_ORDER' in e for e in map_errors(maps, [scenes[1], scenes[0], scenes[2]]))
    bad = copy.deepcopy(maps); bad['maps'].append(copy.deepcopy(bad['maps'][0]))
    bad['maps'][1].update(id='M2', overview_scene_id='B4', return_scene_ids=['B6'])
    more = copy.deepcopy(scenes)
    for index, scene in enumerate(more, start=4):
        scene.update(id=f'B{index}', map_id='M2')
    assert not map_errors(bad, scenes + more)  # two independently coherent maps may serve one unit
    bad = copy.deepcopy(scenes); bad[1]['canvas_id'] = 'new-slide'
    assert any('MAP_CANVAS' in e for e in map_errors(maps, bad))
    bad = copy.deepcopy(scenes); bad[1]['map_node_ids'] = ['imaginary']
    assert any('MAP_FOCUS' in e for e in map_errors(maps, bad))
    bad = copy.deepcopy(maps); bad['maps'][0]['edges'] = []
    assert any('MAP_EDGES' in e for e in map_errors(bad, scenes))
    bad = copy.deepcopy(maps); bad['maps'][0]['edges'][0]['type'] = 'contains'
    assert any('MAP_RELATION' in e for e in map_errors(bad, scenes))
    bad = copy.deepcopy(scenes)
    for scene in bad:
        scene['canvas_mode'] = 'continuous'; scene['visual_strategy']='diagram'; scene.pop('map_id');scene['map_mode']=True
    assert any('MAP_BINDING' in e for e in map_errors({'maps': []}, bad))
    for scene in bad:scene['map_mode']=False
    assert not map_errors({'maps': []}, bad)  # a process can be a local diagram or a demonstration
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        figure = root/'figure.png'; figure.write_bytes(b'local fixture standing in for an extracted asset')
        inventory = dict(review_status='reviewed', page_reviews=[
            dict(page=1, image_ids=['I1'], note='实拍示例及图内注释已查看'),
            dict(page=2, image_ids=[], note='纯文字，无图')], images=[
                dict(id='I1', source_page=1, source_region='左侧实拍', kind='photo',
                     information_value='instructional', decision='include',
                     asset_path='figure.png', sha256=hashlib.sha256(figure.read_bytes()).hexdigest(), scene_ids=['B2'])])
        assert not image_errors(root, project, inventory, scenes)
        bad = copy.deepcopy(inventory); bad['images'][0].update(decision='exclude', exclusion_reason='已经用图标概括')
        assert any('IMAGE_OMISSION' in e for e in image_errors(root, project, bad, scenes))
        bad = copy.deepcopy(inventory); bad['page_reviews'].pop()
        assert any('IMAGE_COVERAGE' in e for e in image_errors(root, project, bad, scenes))
        bad = copy.deepcopy(inventory); bad['images'][0]['scene_ids'] = []
        assert any('IMAGE_UNUSED' in e for e in image_errors(root, project, bad, scenes))
        bad = copy.deepcopy(inventory); bad['images'][0]['sha256'] = 'stale'
        assert any('IMAGE_ASSET' in e for e in image_errors(root, project, bad, scenes))
        bad = copy.deepcopy(inventory); bad['images'][0]['asset_path'] = '../outside.png'
        assert any('IMAGE_ASSET' in e for e in image_errors(root, project, bad, scenes))
        # A genuinely text-only source needs page reviews, not invented pictures/maps.
        assert not image_errors(root, {'source_pages': 1}, dict(review_status='reviewed',
            page_reviews=[dict(page=1, image_ids=[], note='全页文字已查看，无图')], images=[]), [])
        assert not map_errors({'maps': []}, [dict(id='D1', knowledge_relation='definition')])
        for name, value in [('project.json', project), ('script_segments.json', segments),
                            ('storyboard.json', scenes), ('knowledge_maps.json', maps), ('source_images.json', inventory)]:
            (root/name).write_text(json.dumps(value, ensure_ascii=False))
        assert not check(root)
        (root/'source_images.json').write_text('{')
        assert any('COURSE_CONTRACT_FILE' in e for e in check(root))
        create(root/'course')
        starter = root/'course/project'
        assert json.loads((starter/'project.json').read_text())['content_contract_version'] == 2
        assert (starter/'knowledge_maps.json').is_file() and (starter/'source_images.json').is_file()
        # KGXC's dedicated starter has a required closing; an empty draft cannot pass script review.
        assert any('COURSE_CLOSING' in e for e in check(starter, 'script'))
        assert check(starter)  # pending/empty plans cannot masquerade as completed production
    # Exercise the real stage validator: old frozen examples remain supported, opt-in catches missing ending.
    sample = Path(__file__).resolve().parents[1]/'examples/synthetic-review'
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for item in sample.iterdir():
            if item.is_file(): (root/item.name).write_bytes(item.read_bytes())
        assert not validate(root, 'script').errors
        config = json.loads((root/'project.json').read_text())
        config.update(deliverable='full', content_contract_version=1, brand={'closing': CLOSING})
        (root/'project.json').write_text(json.dumps(config))
        assert any('COURSE_CLOSING' in e for e in validate(root, 'script').errors)
    print('PASS: closing, map semantics/bindings, figure omissions/files, text-only source, scaffold and stage integration')


if __name__ == '__main__':
    run()
