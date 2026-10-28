"""Separate text exposure from movement; measure retained, stable reading windows.

The estimate is a conservative authoring floor, not a measured reading speed or
proof of comprehension. Render-time receipts and first-view review remain separate.
"""
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA='course-reading-plan/1'
REVEALS={'chars-in','text-rise','blur-in','typewriter','mask-reveal','compare-wipe','dialogue','paper-fold','correct-replace','count-up','odometer','assemble','evidence-attach','callout','branch-grow'}
NON_MOVING={'marker','underline','check-draw','cross-draw','brace-draw'}
TRANSFORMS={'x','y','zoom','rotation','scaleX','scaleY','opacity'}


def policy():
    return dict(schema='course-reading-policy/1',required=True,
                basis='text-length authoring floor plus actual stable exposure; not learner acceptance')


def estimate(texts):
    text='\n'.join(texts)
    han=len(re.findall(r'[\u3400-\u9fff]',text))
    words=len(re.findall(r'[A-Za-z]+(?:[\x27-][A-Za-z]+)*',text))
    numbers=len(re.findall(r'\d+(?:[.,]\d+)*',text))
    lines=max(1,len([s for s in text.splitlines() if s.strip()]))
    return round(max(1.2,.7+han/6+words/3+numbers*.35+(lines-1)*.3),3)


def _merge(items):
    result=[]
    for a,z,key in sorted(items,key=lambda r:r[0]):
        if a>=z:continue
        if result and result[-1][1]==a and result[-1][2]==key:result[-1][1]=z
        else:result.append([a,z,key])
    return result


def _subtract(windows,covered):
    missing=[]
    for a,z in windows:
        pieces=[(a,z)]
        for x,y in covered:
            pieces=[v for left,right in pieces for v in ([(left,right)] if y<=left or x>=right else ([(left,x)] if left<x else [])+([(y,right)] if y<right else []))]
        missing+=pieces
    return missing


def _index(doc):
    nodes={};chains={}
    def walk(items,parents):
        for n in items:
            nodes[n['id']]=dict(n);chains[n['id']]=parents+[n['id']]
            walk(n.get('children',[]),parents+[n['id']])
    walk(doc.get('sceneGraph',{}).get('nodes',[]),[])
    for f in doc.get('fields',[]):
        if f.get('property')=='text' and f.get('objectId') in nodes:nodes[f['objectId']]['text']=f['text']
    return nodes,chains


def _state(n,f):
    value=dict(n);seen=set()
    for m in sorted(n.get('motion',[]),key=lambda x:x['startFrame']):
        k=m['property']
        if f<m['startFrame']:
            if k not in seen:value[k]=m['from']
        else:
            u=max(0,min(1,(f-m['startFrame'])/max(1,m['endFrame']-m['startFrame'])))
            # Only endpoints are used for stable intervals; exact easing is irrelevant there.
            value[k]=m['from']+(m['to']-m['from'])*u
        seen.add(k)
    return value


class Exposure:
    def __init__(self,doc):
        from timeline import segments
        self.doc=doc;self.nodes,self.chains=_index(doc)
        self.scenes={s['id']:s for s in doc.get('scenes',[])}
        self.spans=segments(dict(doc,holds=doc.get('holds',[])))
        self.cache={}

    def at(self,ids,sid,f,frozen=False):
        signature=[];scene=self.scenes[sid]
        if not scene['sourceStartFrame']<=f<scene['sourceEndFrame']:return False,None
        camera=self.doc.get('sceneGraph',{}).get('camera',{})
        # Opacity is inherited down each path, never multiplied across siblings.
        for i in ids:
            alpha=1
            for k in self.chains[i]:alpha*=_state(self.nodes[k],f).get('opacity',1)
            if alpha<.99:return False,None
        items=[self.nodes[k]for k in dict.fromkeys(k for i in ids for k in self.chains[i])]
        if camera:items+=[dict(camera,id='@camera')]
        for n in items:
            if n.get('sceneId') and n['sceneId']!=sid:return False,None
            if not n.get('startFrame',0)<=f<n.get('endFrame',self.doc['sourceDurationFrames']):return False,None
            v=_state(n,f)
            for e in n.get('effects',[]):
                if e['type'] in REVEALS and f<e['endFrame']:return False,None
                if not frozen and e['type'] not in NON_MOVING and e['startFrame']<=f<e['endFrame']:return False,None
            if not frozen and any(m['property'] in TRANSFORMS and m['from']!=m['to'] and m['startFrame']<=f<m['endFrame']for m in n.get('motion',[])):return False,None
            signature.append((n['id'],*[round(v.get(k,1 if k.startswith('scale')or k=='zoom'else 0),5)for k in ['x','y','zoom','rotation','scaleX','scaleY']]))
        return True,repr(signature)

    def source_windows(self,ids,sid,a,z):
        key=(tuple(ids),sid,a,z)
        if key in self.cache:return self.cache[key]
        points={a,z}
        relevant={k for i in ids for k in self.chains[i]}
        items=[self.nodes[k]for k in relevant]+[self.doc.get('sceneGraph',{}).get('camera',{})]
        for n in items:
            points.update(v for k in ['startFrame','endFrame']if type(v:=n.get(k))is int and a<v<z)
            for m in n.get('motion',[])+n.get('effects',[]):points.update(v for k in ['startFrame','endFrame']if type(v:=m.get(k))is int and a<v<z)
        points=sorted(points);windows=[]
        for x,y in zip(points,points[1:]):
            yes,sig=self.at(ids,sid,x);end,last=self.at(ids,sid,y-1)
            if yes and end and sig==last:windows.append([x,y,sig])
        self.cache[key]=_merge(windows);return self.cache[key]

    def map_range(self,a,z):
        result=[]
        for s in self.spans:
            if s['kind']=='hold':
                if a<=s['sourceFrame']<z:result.append([s['startFrame'],s['endFrame']])
            else:
                x=max(a,s['sourceFrame']);y=min(z,s['sourceFrame']+s['endFrame']-s['startFrame'])
                if x<y:result.append([s['startFrame']+x-s['sourceFrame'],s['startFrame']+y-s['sourceFrame']])
        return result

    def windows(self,ids,sid,a,z):
        raw=self.source_windows(ids,sid,a,z);result=[]
        for s in self.spans:
            if s['kind']=='hold':
                f=s['sourceFrame'];yes,sig=self.at(ids,sid,f,frozen=True)
                if a<=f<z and yes:result.append([s['startFrame'],s['endFrame'],sig])
                continue
            for x,y,sig in raw:
                x=max(x,s['sourceFrame']);y=min(y,s['sourceFrame']+s['endFrame']-s['startFrame'])
                if x<y:result.append([s['startFrame']+x-s['sourceFrame'],s['startFrame']+y-s['sourceFrame'],sig])
        return _merge(result)


def inspect(doc,force=False):
    required=bool(doc.get('readingPolicy',{}).get('required'))
    if not required and not force:return dict(status='legacy-not-opted-in',errors=[],groups=[],scope='existing course left unchanged')
    errors=[];warnings=[];fps=doc.get('fps',30);plan=doc.get('readingPlan',{})
    model=Exposure(doc);nodes=model.nodes
    if plan.get('schema')!=SCHEMA:errors.append('缺少独立文字阅读计划 readingPlan；动作间的空档不能自动作为阅读时间')
    text_nodes={i:n for i,n in nodes.items()if n.get('type')=='text'and str(n.get('text','')).strip()and n.get('role')not in ['decoration','navigation','title']}
    groups=plan.get('groups',[]);references=plan.get('referenceTextIds',[])
    if not isinstance(groups,list)or not isinstance(references,list):return dict(status='fail',errors=errors+['阅读组与常驻标签须为数组'],groups=[])
    # Read-only legacy diagnosis still exposes the actual failure, beyond missing metadata.
    if force and not groups:
        groups=[dict(id='inferred-'+i,sceneId=sid,textIds=[i],task='只读诊断实际文字',window=dict(startFrame=s['sourceStartFrame'],endFrame=s['sourceEndFrame']),minimumStableSeconds=estimate([n['text']]),retention=dict(mode='replace',reason='未提供保留设计，须人工核对'))for i,n in text_nodes.items()for sid,s in model.scenes.items()if all(not nodes[k].get('sceneId')or nodes[k]['sceneId']==sid for k in model.chains[i])]
    covered=set(references);ids=set();rows=[];reference_rows=[]
    for i in references:
        if i not in text_nodes:errors.append('常驻标签不存在或不能用标题充当正文 '+str(i));continue
        for sid,s in model.scenes.items():
            if any(nodes[k].get('sceneId')not in [None,sid]for k in model.chains[i]):continue
            actual=model.windows([i],sid,s['sourceStartFrame'],s['sourceEndFrame'])
            expected=model.map_range(s['sourceStartFrame'],s['sourceEndFrame'])
            if _subtract(expected,[(x,y)for x,y,_ in actual]):errors.append('常驻标签实际会移动、消失或被替换，须作为阅读组安排 '+i)
            reference_rows.append(dict(id=i,sceneId=sid,text=nodes[i]['text'],windows=expected))
    for g in groups:
        if not isinstance(g,dict):errors.append('阅读组须为对象');continue
        gid=g.get('id');sid=g.get('sceneId');scene=model.scenes.get(sid);targets=g.get('textIds',[])
        if not isinstance(gid,str)or not gid or gid in ids:errors.append('阅读组ID缺失或重复');continue
        ids.add(gid)
        if not scene or not isinstance(targets,list)or not targets or any(t not in text_nodes for t in targets):errors.append('阅读组未绑定当前实际正文 '+gid);continue
        covered.update(targets);window=g.get('window',{});a=window.get('startFrame');z=window.get('endFrame')
        if type(a)is not int or type(z)is not int or not scene['sourceStartFrame']<=a<z<=scene['sourceEndFrame']:errors.append('阅读组窗口须在实际场景内 '+gid);continue
        minimum=g.get('minimumStableSeconds');floor=estimate([nodes[t]['text']for t in targets])
        if type(minimum)not in [int,float]or not math.isfinite(minimum)or minimum<floor:
            errors.append(f'{gid} 阅读预算少于当前文字估算下限 {floor:.2f}秒；减少文字或增加稳定阅读时间');minimum=floor
        if not str(g.get('task','')).strip():errors.append('阅读组缺少学员要读懂什么 '+gid)
        windows=model.windows(targets,sid,a,z);longest=max((y-x for x,y,_ in windows),default=0)
        needed=math.ceil(minimum*fps);available=longest/fps
        eligible=next(([x,x+needed]for x,y,_ in windows if y-x>=needed),None)
        if longest<needed:errors.append(f'{gid} 完整且停稳的连续阅读仅 {available:.2f}秒，需要至少 {minimum:.2f}秒；运动/淡入/替换/剪切不计入稳定阅读')
        retention=g.get('retention',{});mode=retention.get('mode');retention_windows=[];retained=[]
        if mode not in ['keep','replace']or not str(retention.get('reason','')).strip():errors.append('须说明旧信息保留方式和理由 '+gid)
        if mode=='keep':
            until=retention.get('untilFrame');via=retention.get('viaTextIds',[])
            if type(until)is not int or not a<until<=scene['sourceEndFrame']or not isinstance(via,list)or any(t not in text_nodes for t in via):errors.append('保留结果须绑定实际文字和有效结束帧 '+gid)
            else:
                begin=eligible[1]if eligible else None
                end_ranges=model.map_range(a,until);end=max((v[1]for v in end_ranges),default=0)
                if begin is not None and begin<end:
                    retention_windows=[[begin,end]]
                    retained=[(x,y)for x,y,_ in model.windows(targets,sid,a,until)]
                    if via:retained += [(x,y)for x,y,_ in model.windows(via,sid,a,until)]
                    if _subtract(retention_windows,retained):errors.append('先前信息在后续需要回看时消失；须保留原文字或同屏摘要 '+gid)
        rows.append(dict(id=gid,sceneId=sid,textIds=targets,texts=[nodes[t]['text']for t in targets],task=g.get('task'),sourceWindow=[a,z],minimumStableSeconds=minimum,estimatedFloorSeconds=floor,availableStableSeconds=round(available,3),stableWindows=[[x,y]for x,y,_ in windows],readWindow=eligible,retentionWindows=retention_windows,retainedByTextIds=retention.get('viaTextIds',[]),status='pass'if longest>=needed else'fail'))
    missing=set(text_nodes)-covered
    if missing:errors.append('正文缺少阅读组或真正常驻标签登记：'+', '.join(sorted(missing)))
    for i,left in enumerate(rows):
        if not left['readWindow']:continue
        for right in rows[i+1:]:
            if right['sceneId']!=left['sceneId']or not right['readWindow']:continue
            overlap=min(left['readWindow'][1],right['readWindow'][1])-max(left['readWindow'][0],right['readWindow'][0])
            if overlap>fps/4:errors.append('新信息阅读窗口竞争：'+left['id']+' / '+right['id']+'；顺次安排，需同时比较的文字合成一个阅读组')
    return dict(schema='course-reading-preflight/1',status='fail'if errors else'pass',errors=list(dict.fromkeys(errors)),warnings=warnings,groups=rows,references=reference_rows,
                scope='actual graph timing, ancestor movement, edits, planned focus and retained text; estimate is not a comprehension score',userFinalAcceptance=False)


def require(doc,project=None):
    if project:
        marker=Path(project)/'motion-contract.json'
        contract=json.loads(marker.read_text())if marker.is_file()else{}
        if contract.get('readingRequired')and not doc.get('readingPolicy',{}).get('required'):raise ValueError('本工程要求文字阅读检查，不能删除 readingPolicy 绕过检查')
    report=inspect(doc)
    if report['status']=='fail':raise ValueError('文字阅读节奏未通过：'+'；'.join(report['errors'][:12]))
    return report


def enable(course,evidence):
    """Explicit adoption only; keep previous media and all content approvals."""
    if not str(evidence).strip():raise ValueError('启用旧课阅读契约须保留实际修改依据')
    from backend import atomic
    from workflow import Course,read
    c=Course(course);p=c.project
    with c.locked():
        doc=read(p/'workbench.json');contract=read(p/'motion-contract.json',{})
        if doc.get('readingPolicy',{}).get('required')and contract.get('readingRequired'):
            return dict(status='already-enabled',revision=doc['revision'])
        old=dict(doc);history=p/'workbench-history'/f'{doc["revision"]:06}.json'
        if history.is_file()and read(history)!=old:raise ValueError('历史版本同名且内容不同，保留原件后处理')
        atomic(history,old)
        doc['readingPolicy']=policy();doc['revision']+=1;contract['readingRequired']=True
        atomic(p/'motion-contract.json',contract);atomic(p/'workbench.json',doc)
        atomic(p/'work/reading-policy'/f'r{doc["revision"]:06}.json',dict(evidence=evidence,previousRevision=old['revision'],revision=doc['revision'],scope='technical reading contract only; existing transcript, storyboard and files retained; changed video requires review'))
    return dict(status='enabled',revision=doc['revision'],next='补齐 readingPlan 并检查；本操作不生成或批准视频')


class RuntimeAudit:
    """Receipts come from the same draw used for the encoded MP4, every frame."""
    def __init__(self,doc,first,last):
        self.doc=doc;self.fps=doc.get('fps',30);self.first=first;self.last=last;self.errors=[]
        report=inspect(doc)if doc.get('readingPolicy',{}).get('required')else{}
        self.groups=report.get('groups',[]);self.references=report.get('references',[])
        self.states={g['id']:dict(run=0,longest=0,signature=None,last=None,missingRetentionFrames=0,firstStable=None,lastStable=None)for g in self.groups}
        self.reference_states={(r['id'],r['sceneId']):dict(missingFrames=0,movingFrames=0,signature=None,last=None)for r in self.references}

    def consume(self,display,source,receipts):
        by_id={r['objectId']:r for r in receipts}
        def signature(ids,texts=None):
            values=[]
            for j,i in enumerate(ids):
                r=by_id.get(i)
                if not r or not r.get('complete')or r.get('alpha',0)<.99 or not r.get('inFrame')or r.get('occluded'):return None
                if texts is not None and r.get('text')!=texts[j]:return None
                box=r.get('bounds',[])
                if len(box)!=4:return None
                values.append((i,r.get('text'),*[round(v,2)for v in box]))
            return tuple(values)
        for g in self.groups:
            state=self.states[g['id']];a,z=g['sourceWindow']
            sig=signature(g['textIds'],g['texts'])if a<=source<z else None
            if sig is not None:
                state['run']=state['run']+1 if sig==state['signature']and state['last']==display-1 else 1
                state['longest']=max(state['longest'],state['run']);state['lastStable']=display
                if state['firstStable']is None:state['firstStable']=display
            else:state['run']=0
            state['signature']=sig;state['last']=display
            if any(x<=display<y for x,y in g['retentionWindows']):
                retained=signature(g['textIds'],g['texts'])or (signature(g['retainedByTextIds'])if g['retainedByTextIds']else None)
                if retained is None:state['missingRetentionFrames']+=1
        for r in self.references:
            if not any(x<=display<y for x,y in r['windows']):continue
            s=self.reference_states[(r['id'],r['sceneId'])];sig=signature([r['id']],[r['text']])
            if sig is None:s['missingFrames']+=1
            elif s['last']==display-1 and s['signature']is not None and sig!=s['signature']:s['movingFrames']+=1
            s['signature']=sig;s['last']=display

    def result(self):
        rows=[];errors=[];reference_rows=[];model=Exposure(self.doc)
        for g in self.groups:
            # A cropped sample can contain only retention. It must still retain
            # the information, without inventing a missing earlier reading phase.
            reading=any(max(a,self.first)<min(z,self.last)for a,z in model.map_range(*g['sourceWindow']))
            retention=any(max(a,self.first)<min(z,self.last)for a,z in g['retentionWindows'])
            if not reading and not retention:continue
            s=self.states[g['id']];seconds=s['longest']/self.fps
            if reading and s['longest']<math.ceil(g['minimumStableSeconds']*self.fps):errors.append(f'{g["id"]} 实际渲染文字连续停稳仅 {seconds:.2f}秒')
            if s['missingRetentionFrames']:errors.append(f'{g["id"]} 实际渲染中有 {s["missingRetentionFrames"]}帧丢失应保留的信息')
            rows.append(dict(id=g['id'],actualStableSeconds=round(seconds,3),requiredSeconds=g['minimumStableSeconds']if reading else None,readingPhaseIncluded=reading,firstVisibleFrame=s['firstStable'],lastVisibleFrame=s['lastStable'],missingRetentionFrames=s['missingRetentionFrames']))
        for r in self.references:
            if not any(max(a,self.first)<min(z,self.last)for a,z in r['windows']):continue
            s=self.reference_states[(r['id'],r['sceneId'])]
            if s['missingFrames']or s['movingFrames']:errors.append(f'常驻标签 {r["id"]} 实际缺失、被遮挡或移动：{s["missingFrames"]} / {s["movingFrames"]}帧')
            reference_rows.append(dict(id=r['id'],sceneId=r['sceneId'],missingFrames=s['missingFrames'],movingFrames=s['movingFrames']))
        return dict(schema='course-reading-runtime/1',status='fail'if errors else'pass',errors=errors,groups=rows,references=reference_rows,
                    scope='same render bridge, actual text, opacity, position, clipping and declared opaque covers; not OCR or learner comprehension',userFinalAcceptance=False)


def review(project,doc,video):
    if not doc.get('readingPolicy',{}).get('required'):return dict(status='legacy-not-opted-in',errors=[])
    p=Path(project);f=p/'qa/reading-review.json'
    if not f.is_file():return dict(status='pending',errors=['缺少当前成片正常速度的阅读与理解复核 qa/reading-review.json'])
    r=json.loads(f.read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest();errors=[]
    if r.get('schema')!='course-reading-review/1'or r.get('status')!='reviewed':errors.append('阅读复核未完成')
    if r.get('documentSha256')!=sha(p/'workbench.json')or r.get('videoSha256')!=sha(video):errors.append('阅读复核绑定的是旧文字、时间线或视频')
    playback=r.get('playback',{})
    if playback.get('speed')!=1 or not playback.get('ranges')or not playback.get('method')or not r.get('reviewer'):errors.append('缺少实际正常速度复看的方法、范围与复核者')
    if doc.get('continuityPolicy',{}).get('required') and not str(playback.get('continuityObservation','')).strip():
        errors.append('缺少正常速度连续观看时的讲解衔接、停顿用途及注意力观察')
    rows={g.get('id'):g for g in r.get('groups',[])}
    for g in inspect(doc)['groups']:
        row=rows.get(g['id'],{})
        if not all(str(row.get(k,'')).strip()for k in ['readingTask','observedReadability','retentionObserved','attentionObservation']):errors.append('缺少本组实际阅读、回看与注意力观察 '+g['id'])
    if r.get('unresolvedIssues'):errors.append('仍有未解决的阅读节奏问题')
    return dict(status='pending'if errors else'pass',errors=errors,scope='bound reported first-view review; technical checks and user acceptance separate')
