"""Explicit creative choices and evidence that the selected features reached the video."""
from pathlib import Path
import copy
import hashlib
import json
import re
import wave

from workflow import atomic, read, now, sha

FILENAME = 'production-preferences.json'
OPTIONS = {
    'customer': ['V01', 'V02', 'V03', 'new', 'none'],
    'flower_text': ['key-points', 'minimal', 'off'],
    'sound_effects': ['native', 'off'],
}
from layered_customers import catalog
CUSTOMERS = catalog()


def load(project):
    path = Path(project) / FILENAME
    value = read(path, dict(schema='course-production-preferences/1', choices={}))
    choices = value.get('choices', {})
    pending = [key for key, values in OPTIONS.items() if choices.get(key) not in values]
    request=value.get('new_customer', {})
    profile=(Path(project)/request.get('profile_path','')).resolve()
    approved=request.get('design_approval', {})
    customer_ready=bool(request.get('profile_path') and profile.is_relative_to(Path(project).resolve()) and profile.is_file() and approved.get('status')=='confirmed' and approved.get('actor') and approved.get('evidence'))
    # A verified older delivery can display its actual choices without changing
    # the approval basis of media produced before this contract existed.
    existing=value.get('recorded_existing_production',{})
    state=read(Path(project)/'course-state.json',{})
    target=(Path(project)/str(existing.get('video_path',''))).resolve()
    registered=set(state.get('artifacts',{}).get('final',[]))
    registered.update(item.get('path') for delivery in state.get('deliveries',[]) for item in delivery.get('files',[]))
    historical=bool(str(state.get('version','')).startswith(('6.4.','6.3.','6.2.')) and
        existing.get('video_path') in registered and target.is_relative_to(Path(project).resolve().parent) and target.is_file() and
        existing.get('video_sha256')==sha(target) and existing.get('actor') and existing.get('evidence'))
    return dict(value, required=path.is_file() and not historical, ready=not pending, pending=pending, customers=CUSTOMERS,new_customer_ready=customer_ready)


def ensure(project):
    path = Path(project) / FILENAME
    if not path.exists():
        atomic(path, dict(schema='course-production-preferences/1', choices={}, answers={}))
    return load(project)


def creative_basis(project):
    if not (Path(project) / FILENAME).is_file():
        return None
    value = load(project)
    if not value['required']:return None
    result = dict(choices=value['choices'])
    if value['choices'].get('customer') == 'new':
        result['new_customer'] = copy.deepcopy(value.get('new_customer', {}))
        profile=(Path(project)/str(result['new_customer'].get('profile_path',''))).resolve()
        if profile.is_relative_to(Path(project).resolve()) and profile.is_file():result['new_customer']['profile_sha256']=sha(profile)
    return result


def choice_digest(project):
    value = creative_basis(project)
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def storyboard_current(project):
    value=load(project)
    if not value['required']:return True
    from storyboard import basis
    receipt=read(Path(project)/'production-preferences-storyboard.json',{})
    return receipt.get('choices_sha256')==choice_digest(project) and receipt.get('storyboard_sha256')==basis(read(Path(project)/'storyboard.json',{}))


def record_storyboard(project,actor,evidence):
    """Bind the reviewed creative choices without rewriting stable storyboard identities."""
    if not load(project)['required']:return
    if not str(actor).strip() or not str(evidence).strip():raise ValueError('请记录制作偏好与分镜衔接的实际依据')
    from storyboard import basis
    path=Path(project)/'production-preferences-storyboard.json'
    if path.is_file():
        old=path.read_bytes();history=Path(project)/'work/production-preferences-history'/(hashlib.sha256(old).hexdigest()[:16]+'.json')
        if not history.exists():history.parent.mkdir(parents=True,exist_ok=True);history.write_bytes(old)
    atomic(path,dict(choices_sha256=choice_digest(project),storyboard_sha256=basis(read(Path(project)/'storyboard.json',{})),actor=actor,evidence=evidence,at=now()))


def update(project, key, choice, actor, brief='', reference_path=''):
    if key not in OPTIONS or choice not in OPTIONS[key]:
        raise ValueError('制作偏好选项无效')
    value = copy.deepcopy(load(project))
    for name in ['required', 'ready', 'pending', 'customers','new_customer_ready']:
        value.pop(name, None)
    value.pop('recorded_existing_production',None)
    value.setdefault('choices', {})[key] = choice
    value.setdefault('answers', {})[key] = dict(value=choice, actor=actor, at=now(),
        evidence='在课程工作台明确选择制作偏好：' + key + ' / ' + choice)
    if key == 'customer' and choice == 'new':
        if not isinstance(brief, str) or len(brief) > 2000:
            raise ValueError('请用2000字以内描述顾客设计方向')
        request = dict(brief=brief.strip() or '根据本课情境设计，与当前课程人物风格协调')
        if reference_path:
            path = (Path(project) / reference_path).resolve()
            allowed = (Path(project) / 'media/uploads').resolve()
            if not path.is_relative_to(allowed) or not path.is_file() or path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                raise ValueError('顾客参考图必须来自本课上传的图片')
            request['reference'] = dict(path=str(path.relative_to(Path(project).resolve())), sha256=sha(path))
        value['new_customer'] = request
    value['updated_at'] = now()
    atomic(Path(project) / FILENAME, value)
    return load(project)


def selection_errors(project):
    value = load(project)
    if not value['required']:
        return []  # Existing frozen courses are not silently migrated.
    labels = dict(customer='顾客形象', flower_text='重点花字', sound_effects='提示音效')
    errors=['待选择制作偏好：' + labels[key] for key in value['pending']]
    if value['choices'].get('customer')=='new' and not value['new_customer_ready']:errors.append('新增顾客尚未提供已采用的实际设计，请先在分镜阶段完成')
    reference=value.get('new_customer',{}).get('reference') if value['choices'].get('customer')=='new' else None
    if reference:
        path=(Path(project)/reference.get('path','')).resolve()
        if not path.is_relative_to((Path(project)/'media/uploads').resolve()) or not path.is_file() or sha(path)!=reference.get('sha256'):errors.append('新增顾客参考图已变化，请重新核对设计依据')
    return errors


def review_errors(project, gate, video):
    errors = selection_errors(project)
    value = load(project)
    if not value['required'] or errors:
        return errors
    proof = read(Path(project) / ('qa/production-preferences-' + gate + '-review.json'), {})
    if proof.get('choices_sha256') != choice_digest(project) or proof.get('video_sha256') != sha(video):
        return ['缺少绑定当前选择与当前视频的制作偏好实物复核']
    observations = proof.get('observations', {})
    for key in OPTIONS:
        if not isinstance(observations.get(key), str) or not observations[key].strip():
            errors.append('制作偏好复核缺少实际观察：' + key)
    implemented = proof.get('implemented', {})
    for key, count_key in [('flower_text', 'flower_count'), ('sound_effects', 'sfx_count')]:
        count = implemented.get(count_key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append('制作偏好复核缺少真实事件数量：' + key)
            continue
        enabled = value['choices'][key] != 'off'
        if enabled and not count and (gate == 'final' or not proof.get('deferred_features', {}).get(key)):
            errors.append(('花字' if key == 'flower_text' else '音效') + '已启用，但当前视频尚未接入')
        if not enabled and count:
            errors.append(('花字' if key == 'flower_text' else '音效') + '已选择关闭，但当前视频仍有启用事件')
    if value['choices']['sound_effects'] == 'native' and implemented.get('sfx_count', 0) and implemented.get('sfx_palette') != 'teaching-native-v1':
        errors.append('当前音效没有沿用已确定的原库音源')
    customers = implemented.get('customer_ids', [])
    choice = value['choices']['customer']
    if gate == 'final' and choice in ['V01', 'V02', 'V03'] and choice not in customers:
        errors.append('当前整课未展示所选顾客形象')
    if choice == 'none' and customers:
        errors.append('已选择无顾客出镜，当前视频仍展示顾客')
    if choice == 'new' and gate == 'final':
        profile=(Path(project)/str(implemented.get('new_customer_profile',''))).resolve()
        if not implemented.get('new_customer_profile') or not profile.is_relative_to(Path(project).resolve()) or not profile.is_file():errors.append('新增顾客还没有实际形象与设计确认记录')
    if gate=='final':errors.extend(material_errors(project,video,value['choices'],implemented))
    return errors


def material_errors(project,video,choices,implemented):
    """Check immutable export objects and the real mixer output, not checkbox counts."""
    project=Path(project).resolve();match=re.search(r'-([a-f0-9]{12})\.mp4$',Path(video).name)
    path=project/'work/workbench/exports'/(match[1] if match else 'missing')/'document.json'
    if not path.is_file():return ['缺少当前成片对应的真实导出文档，无法核对制作偏好实物']
    doc=read(path,{})
    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.get('children',[]))
    nodes={node['id']:node for node in walk(doc.get('sceneGraph',{}).get('nodes',[]))}
    errors=[]
    if choices['flower_text']!='off':
        ids=implemented.get('flower_nodes',[])
        if not isinstance(ids,list) or not ids or any(not isinstance(identifier,str) or identifier not in nodes or nodes[identifier].get('type')!='text' or not nodes[identifier].get('text') for identifier in ids):
            errors.append('花字未绑定当前导出文档中的真实文字对象')
    if choices['customer'] in ['V01','V02','V03','new']:
        ids=implemented.get('customer_nodes',[])
        if not isinstance(ids,list) or not ids or any(not isinstance(identifier,str) or identifier not in nodes or not nodes[identifier].get('vectorActor') or nodes[identifier]['vectorActor'].get('characterRole')!='customer' for identifier in ids):errors.append('顾客必须绑定同风格多部件可动人物，不能使用整张静态贴图')
    if choices['sound_effects']=='native':
        audio=(project/doc.get('media',{}).get('audio','')).resolve()
        receipt=read(audio.with_suffix('.json'),{}) if audio.is_file() and audio.is_relative_to(project) else {}
        stem=(project/str(receipt.get('sfxStem',''))).resolve()
        valid=bool(receipt.get('palette')=='teaching-native-v1' and receipt.get('mix_sha256')==sha(audio) and receipt.get('events',0)>0 and receipt.get('appliedGains')) if audio.is_file() else False
        if not valid or not stem.is_relative_to(project) or not stem.is_file():
            errors.append('音效尚未接入当前导出的实际混音，或缺少原库混音回执')
        else:
            try:
                with wave.open(str(stem),'rb') as stream:
                    nonzero=False
                    while chunk:=stream.readframes(65536):
                        if any(chunk):nonzero=True;break
                if not nonzero:errors.append('当前音效分轨完全静音')
            except (wave.Error,EOFError):errors.append('当前音效分轨无法解码')
    elif choices['sound_effects']=='off':
        audio=(project/doc.get('media',{}).get('audio','')).resolve()
        receipt=read(audio.with_suffix('.json'),{}) if audio.is_relative_to(project) and audio.is_file() else {}
        if receipt.get('events',0)>0 and receipt.get('mix_sha256')==sha(audio):errors.append('已关闭提示音，但当前导出仍绑定含提示音的混音')
    return errors
