#!/usr/bin/env python3
"""Apply a declared delivery tempo, speech pitch, cover and synchronized captions.

The input is an approved render, not a replacement for its editable source.
Speech and music/SFX must be separate, already aligned stems. Original files
are never overwritten; all times in the plan refer to the input timeline.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))


def stamp(value):
    ms=round(value*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def seconds(text):
    h,m,s,ms=map(int,re.split('[:,]',text))
    return h*3600+m*60+s+ms/1000


def read_srt(path):
    result=[]
    for block in re.split(r'\n\s*\n',Path(path).read_text(encoding='utf-8-sig').strip()):
        lines=block.splitlines()
        if len(lines)<3 or ' --> ' not in lines[1]:
            raise ValueError('Invalid SRT block')
        a,b=lines[1].split(' --> ')
        result.append(dict(start=seconds(a),end=seconds(b),text='\n'.join(lines[2:])))
    return result


def retime(cues,rate,additions=()):
    if not math.isfinite(rate) or not .5<=rate<=2:
        raise ValueError('rate must be between 0.5 and 2')
    result=sorted([dict(start=c['start']/rate,end=c['end']/rate,text=c['text']) for c in [*cues,*additions]],key=lambda c:c['start'])
    for i,c in enumerate(result):
        if c['start']<0 or c['end']<=c['start'] or not c['text'].strip():
            raise ValueError('Invalid caption span or empty text')
        if i and result[i-1]['end']>c['start']+.001:
            raise ValueError('Caption spans overlap; resolve on the source timeline')
    return result


def pitch_filter(rate,semitones,sample_rate=48000):
    if not math.isfinite(semitones) or not -4<=semitones<=4:
        raise ValueError('pitch_semitones must be between -4 and 4')
    shifted=round(sample_rate*2**(semitones/12))
    return f'aresample={sample_rate},asetrate={shifted},aresample={sample_rate},atempo={rate/(shifted/sample_rate):.12f}'


def closing_warnings(cues,additions,duration):
    """Surface likely duplicate farewells for content review, never delete words."""
    pattern=re.compile(r'(?:本[节门次]课(?:程)?|这[节门]课).{0,8}(?:结束|到这里)|谢谢大家|感谢大家观看|下[次节]再见')
    existing=[c for c in cues if c['end']>=duration-30 and pattern.search(c['text'])]
    added=[c for c in additions if c['end']>=duration-30 and pattern.search(c['text'])]
    return ['正文已有收尾，又新增了结束语；请按实际语义整合为一次，不能机械追加。'] if existing and added else []


def finish(plan_path):
    plan_path=Path(plan_path).resolve();root=plan_path.parent
    plan=json.loads(plan_path.read_text());resolve=lambda name:(root/plan[name]).resolve()
    required=['video','srt','speech','bed','cover','output_video','output_srt']
    for name in required:
        if not plan.get(name):raise ValueError('Missing '+name)
    paths={name:resolve(name) for name in required}
    for name in required[:5]:
        if not paths[name].is_file():raise ValueError('Missing input '+name)
    if any(paths[n].exists() for n in ['output_video','output_srt']):
        raise ValueError('Output already exists; choose a new version')
    rate=plan.get('rate',1.0);pitch=plan.get('pitch_semitones',0)
    if type(rate) not in [float,int] or not math.isfinite(rate) or not .5<=rate<=2:raise ValueError('Invalid rate')
    source=probe(paths['video']);v=next(s for s in source['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic'))
    fps=plan.get('fps',30);duration=float(source['format']['duration'])
    if type(fps) is not int or not 1<=fps<=60:raise ValueError('Invalid fps')
    target_frames=round(duration/rate*fps);target=target_frames/fps
    for name in ['speech','bed']:
        if abs(float(probe(paths[name])['format']['duration'])-duration)>.05:
            raise ValueError('Stem is not aligned to the source timeline: '+name)
    additions=plan.get('added_captions',[])
    source_cues=read_srt(paths['srt'])
    content_warnings=closing_warnings(source_cues,additions,duration)
    cues=retime(source_cues,rate,[{k:a[k] for k in ['start','end','text']} for a in additions])
    if cues[-1]['end']>target+.05:raise ValueError('Captions extend beyond video')
    width,height=v['width'],v['height'];hold=plan.get('cover_hold_seconds',.65);fade=plan.get('cover_fade_seconds',.35)
    if hold<0 or fade<=0 or hold+fade>min(5,target):raise ValueError('Invalid cover interval')
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(paths['video']),'-loop','1','-framerate',str(fps),'-i',str(paths['cover']),'-i',str(paths['speech']),'-i',str(paths['bed'])]
    graph=[f'[0:v:0]setpts=(PTS-STARTPTS)/{rate},fps={fps},format=yuv420p[base]',
           f'[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,format=rgba,fade=t=out:st={hold}:d={fade}:alpha=1[cover]',
           '[base][cover]overlay=shortest=1:eof_action=pass[v0]']
    last='v0'
    for i,c in enumerate(additions):
        overlay=(root/c['overlay']).resolve()
        if not overlay.is_file():raise ValueError('Missing caption overlay')
        cmd+=['-loop','1','-framerate',str(fps),'-i',str(overlay)]
        label=f'v{i+1}'
        graph.append(f'[{last}][{i+4}:v]overlay=shortest=1:enable=\'between(t,{c["start"]/rate:.9f},{c["end"]/rate:.9f})\'[{label}]');last=label
    graph += [f'[2:a]{pitch_filter(rate,pitch)},apad,atrim=duration={target:.9f}[speech]',
              f'[3:a]atempo={rate},apad,atrim=duration={target:.9f}[bed]',
              '[speech][bed]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=0:latency=1[a]']
    cmd+=['-filter_complex',';'.join(graph),'-map',f'[{last}]','-map','[a]','-frames:v',str(target_frames),'-t',f'{target:.9f}',
          '-c:v','libx264','-crf',str(plan.get('crf',18)),'-preset','medium','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(paths['output_video'])]
    paths['output_video'].parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(cmd,check=True)
    paths['output_srt'].write_text(''.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}\n\n' for i,c in enumerate(cues)))
    output=probe(paths['output_video']);actual=float(output['format']['duration'])
    if abs(actual-target)>.05:raise ValueError('Encoded duration mismatch')
    subprocess.run(['ffmpeg','-v','error','-i',str(paths['output_video']),'-f','null','-'],check=True)
    receipt=dict(schema='course-media-finish/1',status='technical-pass-awaiting-review',plan_sha256=sha(plan_path),
        inputs={n:dict(path=str(paths[n]),sha256=sha(paths[n])) for n in required[:5]},
        outputs={n:dict(path=str(paths[n]),sha256=sha(paths[n])) for n in required[5:]},
        rate_relative_to_input=rate,speech_pitch_semitones=pitch,music_pitch_semitones=0,
        duration=actual,fps=fps,frames=target_frames,captions=len(cues),cover_first_frame=True,full_decode=True,content_warnings=content_warnings,
        limits='Technical timing and decode proof; thumbnail aesthetics, speech intelligibility and user acceptance remain separate.')
    paths['output_video'].with_suffix('.finish.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);a=p.parse_args()
    print(json.dumps(finish(a.plan),ensure_ascii=False,indent=2))
