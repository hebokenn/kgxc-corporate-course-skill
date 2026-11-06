"""Apply source trimming before delivery tempo, then measure and freeze the resulting clock."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import uuid


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    return float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))['format']['duration'])


def prepare(source,out,rate=1.0,start=0.0,end=None,profile='',replace=False):
    source=Path(source).resolve();out=Path(out).resolve()
    if source==out:raise ValueError('保留原始配音，处理后的声音使用另一个文件名')
    if not math.isfinite(rate) or not .5<=rate<=2:raise ValueError('交付语速须在0.5至2.0之间')
    duration=probe(source);end=duration if end is None else end
    if not all(math.isfinite(v) for v in [start,end]) or not 0<=start<end<=duration+.001:raise ValueError('截取范围须在实际原始音轨内')
    metadata=out.with_suffix(out.suffix+'.json');source_hash=sha(source)
    if out.exists():
        old=json.loads(metadata.read_text()) if metadata.is_file() else {}
        if all(old.get(k)==v for k,v in {'source_path':str(source),'audio_path':str(out),'source_sha256':source_hash,'source_start_seconds':start,'source_end_seconds':end,'delivery_rate':rate}.items()) and old.get('audio_sha256')==sha(out):return old
        if not replace:raise ValueError('输出已有不同声音；指定新文件名，或明确替换本课候选')
    out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_name('.'+out.stem+'-'+uuid.uuid4().hex+out.suffix)
    try:
        # A trailing -t would trim OUTPUT time after atempo and can cut spoken content.
        filters=f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS,atempo={rate:.9f}'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-af',filters,'-ar','48000','-ac','2','-c:a','pcm_s16le',str(temp)],check=True)
        actual=probe(temp);expected=(end-start)/rate
        if abs(actual-expected)>.08:raise ValueError(f'处理后声音{actual:.3f}秒，与截取/语速计算{expected:.3f}秒不符，未替换原候选')
        temp.replace(out)
    finally:
        if temp.exists():temp.unlink()
    value=dict(schema='course-audio-timing/1',profile=profile,source_path=str(source),audio_path=str(out),source_sha256=source_hash,
               audio_sha256=sha(out),source_start_seconds=start,source_end_seconds=end,delivery_rate=rate,duration_seconds=actual)
    pending=metadata.with_name('.'+metadata.name+'.pending');pending.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');pending.replace(metadata)
    return value


class NarrationClock:
    def __init__(self,record,fps=30):
        self.record=record;self.fps=fps;self.frames=round(record['duration_seconds']*fps)
        if record.get('audio_path') and sha(record['audio_path'])!=record['audio_sha256']:raise ValueError('声音文件已改变，请重新准备并测量时轴')

    def frame(self,source_seconds):
        start=self.record['source_start_seconds'];end=self.record['source_end_seconds']
        if not math.isfinite(source_seconds) or not start<=source_seconds<=end:raise ValueError(f'词句时间{source_seconds}秒超出已保留原音范围{start}—{end}秒')
        frame=round((source_seconds-start)/self.record['delivery_rate']*self.fps)
        if frame>self.frames+1:raise ValueError('换算后词句超出实际交付音轨，不能继续绑定画面')
        return min(self.frames,frame)


def timeline_errors(doc,audio_seconds=None):
    total=doc.get('sourceDurationFrames',0);fps=doc.get('fps',30);errors=[]
    if type(total)is not int or total<1 or type(fps)not in [int,float] or not math.isfinite(fps) or fps<=0:return ['缺少有效的实际时间轴帧数或帧率']
    if audio_seconds is not None and abs(total/fps-audio_seconds)>.08:errors.append(f'时间轴{total/fps:.3f}秒与实际声音{audio_seconds:.3f}秒不一致')
    def check(item,a,z,kind):
        start=item.get(a,0);end=item.get(z,total)
        if type(start)is not int or type(end)is not int or not 0<=start<end<=total:errors.append(f'{kind} {item.get("id","未命名")} 时间范围[{start}, {end}]超出实际时间轴[0, {total}]，请核对源时间、语速与音轨是否被截短')
    for item in doc.get('captions',[]):check(item,'startFrame','endFrame','字幕')
    for item in doc.get('scenes',[]):check(item,'sourceStartFrame','sourceEndFrame','场景')
    def walk(nodes):
        for node in nodes:
            check(node,'startFrame','endFrame','画面对象');walk(node.get('children',[]))
    walk(doc.get('sceneGraph',{}).get('nodes',[]));return errors
