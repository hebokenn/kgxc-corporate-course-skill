#!/usr/bin/env python3
"""Create a real voiced KGXC technical sample; optionally verify full MP4 export."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import http.server

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate
activate()
from scaffold import create
from authoring import configure,walk
from backend import Workspace, Handler, atomic, duration
from workflow import Course,open_course


def demo_director(course):
    """Three visible proposals for the installation fixture, not a business template."""
    folder=course.project/'director';folder.mkdir(exist_ok=True);styles=[]
    for i,(title,color,caption) in enumerate([('清晰业务图解','#205c46','订单  →  SN编码  →  外包装'),('深色信息演示','#293553','逐项聚焦与字段对应'),('暖色情境演示','#a85b39','以收货动作解释核对顺序')]):
        p=folder/f'fixture-style-{i+1}.svg'
        p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="{color}"/><text x="90" y="150" fill="white" font-size="36">收货核对</text><rect x="90" y="230" width="1100" height="280" rx="20" fill="white" opacity=".95"/><text x="140" y="380" fill="{color}" font-size="40">{caption}</text></svg>')
        styles.append(dict(id=f'S{i+1}',title=title,rationale='用同一段核对内容检验风格选择',motion=caption,production_impact='技术夹具使用可编辑矢量画布',preview_file=str(p.relative_to(course.project))))
    text=course.script()['text'].strip()
    return dict(basis='approved-transcript',script_sha256=course.script_sha(),script_excerpt=text,
        inputs=[dict(role='transcript',path=course.script()['path']),dict(role='original',path='../inputs/技术样例口播.txt')],
        recommended='S1',styles=styles,beats=[dict(id='B1',unit_id='U1',script_excerpt=text,picture='订单、编码与外包装',action='三项信息依次聚焦对应',assessment_ids=['A1'])])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    create(a.destination);root=a.destination.resolve();project=root/'project';example=ROOT/'examples/quickstart'
    for name in ['assets','audio']:shutil.copytree(example/name,project/name,dirs_exist_ok=True)
    shutil.copy2(example/'course-composition.json',project/'source/course-composition.json');shutil.copy2(example/'narration.txt',root/'inputs/技术样例口播.txt')
    cfg=json.loads((project/'project.json').read_text());cfg['deliverable']='pilot';atomic(project/'project.json',cfg)
    course=Course(root);state=course.status();plan=state['plan']
    plan.update(title='收货核对 · 技术验收样例',audience='技能验收操作者',performance_task='验证课程设计与可编辑视频导出闭环')
    plan['sources']=[dict(id='SRC1',title='技术样例口播',kind='file',location='../inputs/技术样例口播.txt')]
    plan['objectives']=[dict(id='O1',statement='检查订单与编码的可编辑呈现',evidence='改字后导出并核对',criterion='保存版本与导出一致')]
    plan['units']=[dict(id='U1',title='收货信息核对',objective_ids=['O1'],source_refs=[dict(source_id='SRC1',locator='完整样例口播')],disposition='core',media='图形演示',media_reason='观察字段对应',activity='核对订单与编码',teaching_method='逐项示范后核对',teaching_reason='将字段对应关系变成可观察动作')]
    plan['assessments']=[dict(id='A1',objective_ids=['O1'],task='指出需对应的三项信息',criteria='与样例一致',feedback='回看订单、编码与外包装')]
    course.save_plan(plan,state['revision'])
    print('已创建酷果星创收货核对技术样例：真实预生成Aiden录音、3个场景、可编辑字幕和图片。不是完整课程业务验收。')
    if a.verify:
        course.confirm('outline',course.status()['revision'],'技术样例结构夹具，非用户业务批准',actor='qa-demo')
        course.save_script((example/'narration.txt').read_text(),course.status()['revision'])
        course.confirm('script',course.status()['revision'],'技术样例逐字稿夹具，非用户业务批准',actor='qa-demo')
        course.select_branch('video',course.status()['revision'],'技术验收要求视频分支',actor='qa-demo')
        course.save_director(demo_director(course),course.status()['revision'])
        course.select_style('S1',course.status()['revision'],'技术样例风格夹具，非用户业务批准',actor='qa-demo')
        full=json.loads((project/'source/course-composition.json').read_text());pilot=copy.deepcopy(full)
        short=project/'audio/installation-pilot.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(project/full['media']['audio']),'-t','2',str(short)],check=True)
        pilot.update(sourceDurationFrames=60,bodyEndFrame=60)
        pilot['media']['audio']=str(short.relative_to(project));scene_id=full['scenes'][0]['id']
        pilot['scenes']=[dict(full['scenes'][0],sourceEndFrame=60)]
        pilot['captions']=[dict(c,endFrame=min(60,c['endFrame'])) for c in full['captions'] if c['startFrame']<60]
        pilot['sceneGraph']['nodes']=[n for n in full['sceneGraph']['nodes'] if n.get('sceneId') in [None,'',scene_id]]
        atomic(project/'source/installation-pilot.json',pilot)
        doc=configure(root,project/'source/installation-pilot.json')
        http.server.ThreadingHTTPServer.request_queue_size=128
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(root)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            pilot=server.workspace.start_export(doc['revision'],0,2,'http://127.0.0.1:'+str(server.server_address[1]),purpose='pilot');until=time.monotonic()+300
            while pilot['status'] not in ['complete','failed'] and time.monotonic()<until:time.sleep(.2)
            if pilot['status']!='complete':raise ValueError(pilot.get('error','样段导出超时'))
            course.confirm('pilot',course.status()['revision'],'技术样例导出夹具，非用户试听批准',actor='qa-demo')
            # Full production is developed only after the short prototype review.
            atomic(project/'workbench-history/000000.json',doc);expanded=copy.deepcopy(doc)
            for key in ['title','sourceDurationFrames','scenes','captions','media','sceneGraph']:expanded[key]=copy.deepcopy(full[key])
            expanded.update(bodyEndFrame=full.get('bodyEndFrame',full['sourceDurationFrames']),revision=doc['revision']+1)
            old_fields={f['objectId']:f for f in doc['fields']};expanded['fields']=[]
            for n in walk(full['sceneGraph']['nodes']):
                prop='text' if n['type']=='text' else 'position'
                expanded['fields'].append(old_fields.get(n['id'],dict(id=n['id']+':'+prop,target='node',objectId=n['id'],sceneId=n.get('sceneId',''),property=prop,label=n['id'],text=n.get('text',''),dx=0,dy=0)))
            atomic(project/'workbench.json',expanded);doc=expanded;course.require_video('pilot')
            job=server.workspace.start_export(doc['revision'],0,duration(doc)/30,'http://127.0.0.1:'+str(server.server_address[1]),purpose='final');until=time.monotonic()+300
            while job['status'] not in ['complete','failed'] and time.monotonic()<until:time.sleep(.2)
            if job['status']!='complete':raise ValueError(job.get('error','样例导出超时'))
            atomic(project/'qa/installation-example.json',job);print('技术样例完整导出检查通过：'+job['video'])
        finally:server.shutdown();server.server_close()
    if not a.verify:open_course(root)
    print('打开编辑：kgxc-course resume '+str(root))


if __name__=='__main__':main()
