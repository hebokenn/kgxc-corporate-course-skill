"""Exercise repeated ripple edits, cross-track timing, JS parity and real PCM output."""
import copy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
import wave
import array

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from timeline import duration,display_frame,source_frame,segments,ripple_cut
from backend import Workspace,atomic,validate


def expanded(doc):
    out=[]
    for s in segments(doc):
        out.extend((s['kind'],s['sourceFrame']+i if s['kind']=='source' else s['sourceFrame']) for i in range(s['endFrame']-s['startFrame']))
    return out


class RippleTests(unittest.TestCase):
    def setUp(self):
        self.doc=dict(sourceDurationFrames=180,holds=[dict(sourceFrame=60,frames=30,sceneId='s1'),dict(sourceFrame=130,frames=15,sceneId='s2')],
                      captions=[dict(id='a',text='先核对',startFrame=20,endFrame=55),dict(id='b',text='再检查',startFrame=100,endFrame=140),dict(id='c',text='确认',startFrame=150,endFrame=200)])

    def test_partial_hold_then_cross_source_and_captions(self):
        d=ripple_cut(self.doc,65,80)
        self.assertEqual(d['holds'][0]['frames'],15);self.assertEqual(d.get('cuts'),[])
        self.assertEqual(d['captions'][1]['startFrame'],85)
        old=expanded(d);d=ripple_cut(d,45,105)
        self.assertEqual(expanded(d),old[:45]+old[105:]);self.assertEqual(d['captions'][0]['endFrame'],45)
        self.assertEqual(d['captions'][1]['startFrame'],45);self.assertEqual(d['captions'][1]['endFrame'],65)
        self.assertEqual(self.doc['holds'][0]['frames'],30)

    def test_repeated_random_edits_keep_exact_original_frames(self):
        rng=random.Random(31)
        for _ in range(35):
            d=copy.deepcopy(self.doc);expected=expanded(d)
            for _ in range(8):
                a=rng.randrange(len(expected)-1);b=rng.randrange(a+1,len(expected))
                d=ripple_cut(d,a,b);expected=expected[:a]+expected[b:]
                self.assertEqual(expanded(d),expected);self.assertEqual(duration(d),len(expected))
                for f,(_,s) in enumerate(expected):self.assertEqual(source_frame(f,d['holds'],d['cuts']),s)
                for c in d['captions']:self.assertTrue(0<=c['startFrame']<c['endFrame']<=duration(d))

    def test_js_python_parity_for_cuts_mapping_and_holds(self):
        edits=[[65,80],[45,105],[0,10],[80,90]];d=copy.deepcopy(self.doc);expected=[]
        for a,b in edits:
            d=ripple_cut(d,a,b);expected.append(dict(document=d,frames=[source_frame(f,d['holds'],d['cuts']) for f in range(duration(d))],boundaries=[display_frame(f,d['holds'],d['cuts']) for f in range(181)]))
        script="""import fs from 'node:fs';const mod=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(process.argv[1],'utf8')).toString('base64'));const p=JSON.parse(fs.readFileSync(0,'utf8'));let d=p.doc;const out=[];for(const [a,b] of p.edits){d=mod.rippleCut(d,a,b);out.push({document:d,frames:Array.from({length:mod.totalFrames(d)},(_,f)=>mod.sourceFrame(f,d.holds,d.cuts)),boundaries:Array.from({length:181},(_,f)=>mod.displayFrame(f,d.holds,d.cuts))})}process.stdout.write(JSON.stringify(out));"""
        got=json.loads(subprocess.check_output(['node','--input-type=module','-e',script,str(ROOT/'workbench/timeline.js')],input=json.dumps(dict(doc=self.doc,edits=edits)).encode()))
        self.assertEqual(got,expected)

    def test_reject_empty_all_negative_or_fractional_selection(self):
        for a,b in [(0,duration(self.doc)),(-1,10),(5,5),(0,300),(1.5,3),(True,3)]:
            with self.assertRaises(ValueError):ripple_cut(self.doc,a,b)

    def test_real_audio_pcm_matches_retained_frames_and_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'project';p.mkdir();audio=p/'sound.wav'
            samples=array.array('h')
            for f in range(180):samples.extend([1000+f]*1600)
            with wave.open(str(audio),'wb') as w:w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(samples.tobytes())
            d=copy.deepcopy(self.doc);d.update(schema='course-workbench/1',revision=0,title='裁剪测试',fps=30,width=1920,height=1080,adapter='seek-bridge-v1',introFrames=0,bodyEndFrame=180,media=dict(audio='sound.wav',intro=None,outro=None),audio=dict(gain=1,speed=1,voice='original'),captionStyle=dict(fontSize=42,y=990,fill='#fff',stroke='#000',strokeWidth=8),fields=[],assets=[],scenes=[])
            atomic(p/'workbench.json',d);space=Workspace(root);d=ripple_cut(d,65,80);d=ripple_cut(d,30,45);d=ripple_cut(d,95,120);validate(d,p)
            sound=space.audio(d)
            with wave.open(str(sound),'rb') as w:
                self.assertEqual(w.getframerate(),48000);self.assertEqual(w.getnframes(),duration(d)*1600);actual=array.array('h',w.readframes(w.getnframes()))
            for f,(kind,source) in enumerate(expanded(d)):
                self.assertEqual(actual[f*1600],1000+source if kind=='source' else 0)
                self.assertEqual(actual[(f+1)*1600-1],1000+source if kind=='source' else 0)
            saved=space.save(d,0);self.assertEqual(json.loads(Workspace(root).file.read_text()),saved)
            self.assertEqual(space.audio(saved),sound)
            broken=copy.deepcopy(saved);broken['cuts']=[dict(startFrame=3,endFrame=10),dict(startFrame=9,endFrame=20)]
            with self.assertRaises(ValueError):validate(broken,p)


if __name__=='__main__':unittest.main()
