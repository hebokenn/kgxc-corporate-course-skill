#!/usr/bin/env python3
"""Regression checks: positive draft and safety failures."""
from __future__ import annotations
import copy
import json
import tempfile
from pathlib import Path
from validate import validate

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=ROOT/'examples/synthetic-review'

def test():
    assert not validate(SAMPLE,'analyze').errors
    assert not validate(SAMPLE,'script').errors
    assert not validate(SAMPLE,'storyboard').errors
    assert any('GATE_CONTENT' in e for e in validate(SAMPLE,'preview').errors)
    assert any('GATE_SCOPE' in e for e in validate(SAMPLE,'final').errors)
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)
        for f in SAMPLE.glob('*'):
            if f.is_file():(path/f.name).write_bytes(f.read_bytes())
        # hallucinated rule ref must be stopped
        board=json.loads((path/'storyboard.json').read_text(encoding='utf8'))
        board[0]['on_screen_facts'][0]['rule_id']='R999'
        (path/'storyboard.json').write_text(json.dumps(board,ensure_ascii=False),encoding='utf8')
        assert any('FACT_SOURCE' in e for e in validate(path,'storyboard').errors)
        # Returning false promise of approval does not remove pending source issues from final gate
        board[0]['on_screen_facts'][0]['rule_id']='R004'
        (path/'storyboard.json').write_text(json.dumps(board,ensure_ascii=False),encoding='utf8')
        proj=json.loads((path/'project.json').read_text(encoding='utf8'))
        proj['deliverable']='full';proj['approvals']={'content':True,'visual':True,'pilot':True,'final':True}
        (path/'project.json').write_text(json.dumps(proj,ensure_ascii=False),encoding='utf8')
        assert any('GATE_PENDING' in e for e in validate(path,'final').errors)
    print('PASS: 正常样例与阻断条件共7项回归检查')

if __name__=='__main__':test()
