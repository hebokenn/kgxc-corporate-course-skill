"""Deterministic edit persistence, timeline and validation regressions; no media downloads."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from backend import Workspace, atomic, display_frame, source_frame, duration, validate, safe


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.project=self.root/'project';self.project.mkdir()
        for name in ['sound.wav','intro.mp4','outro.mp4','image.png','replacement.png']:(self.project/name).write_bytes(b'fixture')
        self.doc=dict(schema='course-workbench/1',revision=0,title='测试课程',fps=30,width=1920,height=1080,adapter='national-world-v1',sourceDurationFrames=300,
                      introFrames=30,bodyEndFrame=270,media=dict(audio='sound.wav',intro='intro.mp4',outro='outro.mp4'),holds=[],
                      audio=dict(gain=1,speed=1,voice='original'),captionStyle=dict(fontSize=42,y=990,fill='#fff',stroke='#000',strokeWidth=8),
                      captions=[dict(id='c1',sceneId='s1',text='核对SN 2026',startFrame=30,endFrame=90),dict(id='c2',sceneId='s2',text='确认材料',startFrame=100,endFrame=160)],
                      scenes=[dict(id='s1',title='核对',chapter='练习',sourceStartFrame=30,sourceEndFrame=100)],
                      fields=[dict(id='f1',objectId='s1',property='label',text='核对',dx=0,dy=0)],
                      assets=[dict(id='a1',path='image.png',originalPath='image.png')])
        atomic(self.project/'workbench.json',self.doc)

    def tearDown(self):self.temp.cleanup()

    def test_edit_save_reopen_history_conflict(self):
        space=Workspace(self.root);changed=copy.deepcopy(self.doc)
        changed['captions'][0]['text']='核对 SN 2026';changed['captions'][0]['startFrame']=31
        changed['fields'][0].update(text='核对资料',dx=8);changed['assets'][0]['path']='replacement.png'
        saved=space.save(changed,0);self.assertEqual(saved['revision'],1)
        reopened=Workspace(self.root);self.assertEqual(saved['assets'][0]['path'],'replacement.png')
        import json
        self.assertEqual(json.loads(reopened.file.read_text()),saved)
        self.assertEqual(json.loads((self.project/'workbench-history/000000.json').read_text()),self.doc)
        with self.assertRaises(FileExistsError):space.save(changed,0)
        self.assertEqual(json.loads(reopened.file.read_text()),saved)

    def test_freeze_and_retime_multiple_holds(self):
        holds=[dict(sourceFrame=100,frames=45),dict(sourceFrame=200,frames=30)]
        for f in [0,99,100,101,199,200,299]:self.assertEqual(source_frame(display_frame(f,holds),holds),f)
        self.assertEqual([source_frame(f,holds) for f in [99,100,144,145,244,245,274,275]],[99,99,99,100,199,199,199,200])
        changed=copy.deepcopy(self.doc);changed['holds']=holds
        for c in changed['captions'][1:]:c['startFrame']+=45;c['endFrame']+=45
        self.assertEqual(duration(changed),375);validate(changed,self.project)

    def test_reject_invalid_edits_and_path_escape(self):
        elevated=copy.deepcopy(self.doc);elevated['captionStyle']['y']=850;validate(elevated,self.project)
        mutations=[lambda d:d['captions'][0].update(text='有标点，不能保存'),lambda d:d['captions'][0].update(startFrame=-1),
                   lambda d:d['captions'][1].update(startFrame=80),lambda d:d['captions'][0].update(endFrame=301),
                   lambda d:d['assets'][0].update(path='../outside.png'),lambda d:d['audio'].update(speed=.8),
                   lambda d:d['fields'][0].update(dx=float('nan')),lambda d:d['holds'].append(dict(sourceFrame=301,frames=5))]
        for mutation in mutations:
            changed=copy.deepcopy(self.doc);mutation(changed)
            with self.assertRaises(ValueError):validate(changed,self.project)
        with self.assertRaises(ValueError):safe(self.project,'../outside')
        outside=self.root/'external';outside.write_text('preserve');(self.project/'linked').symlink_to(outside)
        with self.assertRaises(ValueError):safe(self.project,'linked')
        self.assertEqual(outside.read_text(),'preserve')

    def test_save_protects_original_structure(self):
        changed=copy.deepcopy(self.doc);changed['sourceDurationFrames']=301
        with self.assertRaises(ValueError):Workspace(self.root).save(changed,0)
        changed=copy.deepcopy(self.doc);changed['assets'][0]['originalPath']='replacement.png'
        with self.assertRaises(ValueError):Workspace(self.root).save(changed,0)


if __name__=='__main__':unittest.main()
