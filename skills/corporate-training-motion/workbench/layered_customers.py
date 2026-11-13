"""Distinct customer presets for the same controllable figure family as M1/S01."""
import copy
import hashlib

PRESETS={
    'V01':dict(label='短侧分发顾客',description='眼镜、灰色便装外套',appearance=dict(
        identity='V01',characterRole='customer',age=32,hair='side-part',hairColor='#513b31',
        skin='#edb18d',glasses=True,outfit='jacket',shirtColor='#a8a6a3',innerColor='#344759',pantsColor='#424753')),
    'V02':dict(label='齐肩短发顾客',description='棕红短发、浅紫圆领上衣',appearance=dict(
        identity='V02',characterRole='customer',age=29,hair='bob',hairColor='#69413a',
        skin='#efba9b',glasses=False,outfit='tee',shirtColor='#b8a9c8',pantsColor='#444557')),
    'V03':dict(label='成熟短发顾客',description='灰鬓短发、米色衬衫',appearance=dict(
        identity='V03',characterRole='customer',age=48,hair='mature',hairColor='#57524d',
        skin='#dfa784',glasses=False,outfit='shirt',shirtColor='#c9b18e',pantsColor='#4c5b73')),
}


def catalog():
    return [dict(id=key,label=item['label'],description=item['description'],preview='/ui-customers/'+key+'.png',
        representation='solid-vector-acting/1',design=copy.deepcopy(item['appearance'])) for key,item in PRESETS.items()]


def design_for_course(course_id,identity,appearance=None):
    """A reproducible starting design; save it in the course and review the actual figure."""
    if not isinstance(course_id,str) or not course_id or not isinstance(identity,str) or not identity:
        raise ValueError('人物设计需要当前课程ID和独立人物ID')
    seed=hashlib.sha256((course_id+'\0'+identity).encode()).digest()
    hair=['side-part','bob','mature','pony','spiky','short'][seed[0]%6]
    clothes=[('jacket','#a8a6a3','#344759'),('tee','#b8a9c8','#eee8dc'),
             ('shirt','#c9b18e','#eee8dc'),('jacket','#716b91','#eee8dc'),
             ('tee','#c58972','#eee8dc'),('shirt','#8796ad','#eee8dc')][seed[1]%6]
    result=dict(identity=identity,characterRole='customer',age=48 if hair=='mature' else 25+seed[2]%20,
        hair=hair,hairColor=['#513b31','#69413a','#373237','#6c5a43'][seed[3]%4],
        skin=['#edb18d','#efba9b','#dfa784'][seed[4]%3],glasses=bool(seed[5]%2),
        outfit=clothes[0],shirtColor=clothes[1],innerColor=clothes[2],pantsColor=['#424753','#4c5b73','#675852'][seed[6]%3])
    for key,value in (appearance or {}).items():
        if key in ['hair','hairColor','skin','age','glasses','outfit','shirtColor','innerColor','pantsColor','faceShape']:result[key]=value
    return result


def stage(preset,placement,project,skill_root,appearance=None):
    from acting import stage as stage_actor
    if preset not in PRESETS:raise ValueError('请选择已有可动顾客或提供新的角色设计')
    design=copy.deepcopy(PRESETS[preset]['appearance'])
    for key,value in (appearance or {}).items():
        if key in ['identity','hair','hairColor','skin','age','glasses','outfit','shirtColor','innerColor','pantsColor','faceShape']:design[key]=value
    design.update(placement);design['characterRole']='customer'
    return stage_actor(design,project,skill_root)
