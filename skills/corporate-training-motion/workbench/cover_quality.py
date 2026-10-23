"""Check an evidence-bound course cover; never infer beauty from file presence."""
import hashlib
import io
import json
from pathlib import Path
import subprocess

CRITERIA=('titleLegibility','courseConsistency','brandIntegrity','composition','thumbnailObservation')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_file(project,name):
    path=(project/name).resolve()
    if not name or Path(name).is_absolute() or not path.is_relative_to(project) or not path.is_file():
        raise ValueError('封面证据文件缺失或越界')
    return path


def review(project,doc,video,verify_pixels=True):
    p=Path(project).resolve();video=Path(video).resolve()
    marker=p/'craft-contract.json'
    try:marked=json.loads(marker.read_text()).get('coverRequired') if marker.is_file() else False
    except (OSError,ValueError):return dict(status='pending',errors=['封面契约不是有效JSON'])
    if not (doc.get('qualityPolicy',{}).get('coverRequired') or marked):
        return dict(status='legacy-not-opted-in',errors=[])
    path=p/'qa/cover-review.json';errors=[]
    if marked and not doc.get('qualityPolicy',{}).get('coverRequired'):
        errors.append('本工程要求封面复核，不能删除 coverRequired')
    try:
        data=json.loads(path.read_text())
        if data.get('schema')!='course-cover-review/1' or data.get('status')!='reviewed':
            errors.append('封面尚未复核')
        if data.get('videoSha256')!=sha(video):errors.append('封面记录未绑定当前视频')
        if data.get('title')!=doc.get('title'):errors.append('封面标题与当前课程名不一致')
        if not data.get('reviewer') or not data.get('scope'):errors.append('缺少封面复核者和实际范围')
        if data.get('unresolvedIssues'):errors.append('封面仍有未解决问题')
        for key in CRITERIA:
            if not isinstance(data.get(key),str) or not data[key].strip():errors.append('缺少封面观察 '+key)
        cover=local_file(p,data.get('coverPath',''))
        if data.get('coverSha256')!=sha(cover):errors.append('封面图已变化')
        from PIL import Image
        with Image.open(cover) as im:
            width,height=im.size;reference=im.convert('RGB')
        if width<1280 or height<720 or abs(width/height-16/9)>.015:
            errors.append('封面须为清晰的16:9横图，至少1280×720')
        thumb=local_file(p,data.get('thumbnailPath',''))
        if data.get('thumbnailSha256')!=sha(thumb):errors.append('缩略图证据已变化')
        with Image.open(thumb) as im:
            if im.size!=(320,180):errors.append('缩略图证据须按320×180实际查看')
        mode=data.get('mode')
        if mode=='first-frame':
            if verify_pixels:
                import numpy as np
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-map','0:v:0','-frames:v','1','-vf','scale=320:180','-f','image2pipe','-vcodec','png','-'])
                actual=Image.open(io.BytesIO(raw)).convert('RGB')
                # Match the first-frame cover's aspect-fill behavior before comparison.
                scale=max(320/reference.width,180/reference.height)
                reference=reference.resize((round(reference.width*scale),round(reference.height*scale)),Image.Resampling.LANCZOS)
                x=(reference.width-320)//2;y=(reference.height-180)//2
                reference=reference.crop((x,y,x+320,y+180))
                mse=float(np.mean((np.asarray(reference,dtype=float)-np.asarray(actual,dtype=float))**2))
                psnr=float(20*np.log10(255/max(mse,1e-12)**.5))
                if psnr<28:errors.append('视频首帧与交付封面不一致')
        elif mode=='player-poster':
            from html.parser import HTMLParser
            from urllib.parse import unquote
            page=local_file(p,data.get('pagePath',''))
            class Videos(HTMLParser):
                def __init__(self):super().__init__();self.items=[]
                def handle_starttag(self,tag,attrs):
                    if tag=='video':self.items.append(dict(attrs))
            parser=Videos();parser.feed(page.read_text())
            matches=[]
            for item in parser.items:
                poster=(page.parent/unquote(item.get('poster',''))).resolve()
                src=(page.parent/unquote(item.get('src',''))).resolve()
                if poster==cover and src.is_file() and sha(src)==sha(video):matches.append(item)
            if not matches:errors.append('当前视频播放器未实际接入该封面')
        else:errors.append('须核实首帧封面或播放器poster，不能只交一张图片')
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        errors.append('封面复核无法完成：'+str(exc))
    return dict(status='pending' if errors else 'pass',errors=errors,
        scope='Current cover bytes, thumbnail evidence and encoded first frame or wired player; text accuracy and aesthetics require actual visual review, user acceptance separate.')
