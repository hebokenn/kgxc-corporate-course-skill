#!/usr/bin/env python3
"""Behavior checks for content-selected visuals and the one-package toolchain."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from check_visual_plan import check_scenes
from check_course_completeness import map_errors
from single_line_subtitles import prepare, validate, identity
from scaffold import create

ROOT = Path(__file__).resolve().parents[1]


def run():
    # A real handoff can be demonstrated by moving a physical object: no map,
    # zoom-back contract, or invented graph is required.
    scene = dict(id='handoff', learning_goal='看懂钥匙交接', knowledge_relation='handoff',
                 visual_strategy='object_action', visual_action='钥匙从发送人移到接收人手中',
                 camera_reason='同框展示交接前后', camera_plan='固定中景', canvas_id='counter',
                 canvas_mode='separate', focus_object_ids=['key'], map_mode=False)
    assert not check_scenes([scene])
    assert not map_errors({'maps': []}, [scene])
    # Opting into a graph still validates real graph data.
    assert map_errors({'maps': []}, [{**scene, 'map_mode': True}])
    cues = prepare([dict(id='C1', start=0, end=6, text='营业时间：10:00—22:00。')])
    assert not validate(cues)
    assert identity(''.join(c['text'] for c in cues)) == identity('营业时间：10:00—22:00。')
    assert validate([{**cues[0], 'text': '第一行\n第二行'}])
    assert validate([{**cues[0], 'text': '带标点。'}])
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        with patch.dict('os.environ', {'COURSE_CONFIG_DIR': str(base/'clean-config')}):
            create(base/'course')
        cfg = json.loads((base/'course/project/project.json').read_text())
        assert cfg['voice']['voice_id'] == 'didi' and cfg['voice']['speed'] == 1.0
        assert cfg['voice']['mode'] == 'clone' and cfg['voice']['delivery_rate'] == 1.0 and 'instruct' not in cfg['voice'] and not cfg['subtitles']['punctuation']
        assert cfg['subtitles']['single_line'] and not cfg['process_visual_default']['map_required']
        assert cfg['titles']['policy'] == 'choose_by_content'
        dest = base/'web'
        cmd = [sys.executable, str(ROOT/'scripts/course_tools.py'), 'prepare-web', '--destination', str(dest)]
        subprocess.run(cmd, check=True, capture_output=True)
        original = (dest/'composition.html').read_bytes()
        assert subprocess.run(cmd, capture_output=True).returncode != 0
        assert (dest/'composition.html').read_bytes() == original
        result = subprocess.run([sys.executable, str(ROOT/'scripts/course_tools.py'), 'inventory'],
                                check=True, capture_output=True, text=True)
        assert all(item['exists'] for item in json.loads(result.stdout).values())
        # Internal dispatch remains inside the package even without either former Skill.
        result = subprocess.run([sys.executable, str(ROOT/'scripts/course_tools.py'), 'render-illustration',
                                 '--dry-run', '--spec', 'clip.json', '--out', 'clip.mp4'],
                                check=True, capture_output=True, text=True)
        command = json.loads(result.stdout)
        assert (ROOT/'libraries/illustration/scripts/engine/render.py') == Path(command[1])
        assert command[-2:] == ['--fps', '30']
        result = subprocess.run([sys.executable, str(ROOT/'scripts/course_tools.py'), 'render-web',
                                 '--dry-run', 'page.html', '--out', 'render', '--h', '360'],
                                check=True, capture_output=True, text=True)
        assert json.loads(result.stdout)[-2:] == ['--h', '360']
        result = subprocess.run([sys.executable, str(ROOT/'scripts/course_tools.py'), 'workbench',
                                 '--dry-run', 'serve', 'editable-course'],check=True,capture_output=True,text=True)
        assert json.loads(result.stdout)[1:] == [str(ROOT/'scripts/workbench.py'),'serve','editable-course']
    print('PASS: non-map handoff, selected-map validation, single-line punctuation-free subtitles, clean-install didi clone at 1.0 delivery, content titles, overwrite protection and internal dispatch')


if __name__ == '__main__':
    run()
