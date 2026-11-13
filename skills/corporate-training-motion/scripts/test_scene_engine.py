"""Zero-valued drawing coordinates are geometry, not absent defaults."""
import json
from pathlib import Path
import subprocess
import unittest


class GeometryTests(unittest.TestCase):
    def test_horizontal_vertical_and_zero_width_geometry(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),calls=[];
const ctx=new Proxy({globalAlpha:1},{get:(o,k)=>k in o?o[k]:(...a)=>{calls.push([k,...a])},set:(o,k,v)=>(o[k]=v,true)});
const sandbox={window:{},structuredClone,document:{querySelector:()=>({getContext:()=>ctx}),fonts:{load:async()=>{},ready:Promise.resolve()}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
(async()=>{const api=sandbox.window.courseWorkbench;await api.apply({fps:30,sourceDurationFrames:30,fields:[],assets:[],scenes:[{id:'S',sourceStartFrame:0,sourceEndFrame:30}],sceneGraph:{nodes:[
 {id:'horizontal',type:'line',x2:120,y2:0},
 {id:'vertical',type:'line',x2:0,y2:80},
 {id:'zero-width',type:'rect',width:0,height:30}
]}});await api.seek(0);console.log(JSON.stringify(calls));})();
'''
        engine=Path(__file__).resolve().parents[1]/'workbench/starter/scene-engine.js'
        calls=json.loads(subprocess.check_output(['node','-e',script,str(engine)],text=True))
        self.assertEqual([c[1:] for c in calls if c[0]=='lineTo'],[[120,0],[0,80]])
        self.assertEqual([c[3:5] for c in calls if c[0]=='roundRect'],[[0,30]])
    def test_future_animation_phase_does_not_override_current_or_initial_phase(self):
        script=r'''
const fs=require('fs'),vm=require('vm');let width;
const ctx=new Proxy({globalAlpha:1,roundRect:(x,y,w)=>{width=w}},{get:(o,k)=>k in o?o[k]:()=>{},set:(o,k,v)=>(o[k]=v,true)});
const sandbox={window:{},structuredClone,document:{querySelector:()=>({getContext:()=>ctx}),fonts:{load:async()=>{},ready:Promise.resolve()}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
(async()=>{const api=sandbox.window.courseWorkbench;await api.apply({fps:30,sourceDurationFrames:60,fields:[],assets:[],scenes:[{id:'S',sourceStartFrame:0,sourceEndFrame:60}],sceneGraph:{nodes:[{id:'phase',type:'rect',width:0,height:5,motion:[
 {property:'width',from:0,to:100,startFrame:10,endFrame:20,ease:'linear'},
 {property:'width',from:100,to:0,startFrame:30,endFrame:40,ease:'linear'}
]}]}});const values=[];for(const f of [0,15,25,35,45]){await api.seek(f/30);values.push(width)}console.log(JSON.stringify(values))})();
'''
        engine=Path(__file__).resolve().parents[1]/'workbench/starter/scene-engine.js'
        values=json.loads(subprocess.check_output(['node','-e',script,str(engine)],text=True))
        self.assertEqual(values,[0,50,100,50,0])


if __name__=='__main__':unittest.main()
