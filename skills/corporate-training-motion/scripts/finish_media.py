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
from fractions import Fraction
import uuid


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
    source_fps=Fraction(v['avg_frame_rate']);fps=Fraction(str(plan.get('fps',source_fps)))
    if not 1<=fps<=120:raise ValueError('Invalid fps')
    if rate!=1 and not plan.get('tempo_authorization'):raise ValueError('Tempo change requires its actual authorization source')
    counted=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams',str(v['index']),'-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(paths['video'])]))
    source_frames=int(counted['streams'][0]['nb_read_frames']);duration=source_frames/float(source_fps)
    target_frames=round(duration/rate*float(fps));target=target_frames/float(fps)
    for name in ['speech','bed']:
        if abs(float(probe(paths[name])['format']['duration'])-duration)>.05:
            raise ValueError('Stem is not aligned to the source timeline: '+name)
    additions=plan.get('added_captions',[])
    source_cues=read_srt(paths['srt'])
    content_warnings=closing_warnings(source_cues,additions,duration)
    cues=retime(source_cues,rate,[{k:a[k] for k in ['start','end','text']} for a in additions])
    if cues[-1]['end']>target+.05:raise ValueError('Captions extend beyond video')
    # Candidate-only: no mkdir/write in the formal desktop tree, including symlinks.
    project=(root/plan.get('project_dir','.')).resolve();allowed=project.parent if 'project_dir'in plan else root
    for name in ['output_video','output_srt']:
        output=paths[name]
        if (not output.is_relative_to(allowed) or any(output.parts[i:i+2]==('Desktop','ai 制课') for i in range(len(output.parts)-1))):
            raise ValueError('Formal Desktop delivery is forbidden; finish_media only writes a course candidate')
    width,height=v['width'],v['height'];hold=plan.get('cover_hold_seconds',0);fade=plan.get('cover_fade_seconds',0)
    timed=bool(hold or fade)
    if timed and not plan.get('cover_timing_authorization'):raise ValueError('Extended cover requires its actual authorization source')
    if hold<0 or fade<0 or hold+fade>min(5,target):raise ValueError('Invalid cover interval')
    work=project/'work/finish-media'/(sha(plan_path)[:16]+'-'+uuid.uuid4().hex[:8]);work.mkdir(parents=True,exist_ok=True)
    video_only=work/'video-complete.mp4';audio_only=work/'audio-complete.m4a'
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(paths['video']),'-loop','1','-framerate',str(fps),'-i',str(paths['cover'])]
    graph=[f'[0:{v["index"]}]setpts=(PTS-STARTPTS)/{rate},fps={fps},format=yuv420p[base]',
           f'[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,format=rgba'+
             (f',fade=t=out:st={hold}:d={fade}:alpha=1' if timed and fade else '')+'[cover]',
           '[base][cover]overlay=shortest=1:eof_action=pass:'+('enable=\'lt(t,%0.9f)\''%(hold+fade) if timed else "enable='eq(n,0)'")+'[v0]']
    last='v0'
    for i,c in enumerate(additions):
        overlay=(root/c['overlay']).resolve()
        if not overlay.is_file():raise ValueError('Missing caption overlay')
        cmd+=['-loop','1','-framerate',str(fps),'-i',str(overlay)]
        label=f'v{i+1}'
        graph.append(f'[{last}][{i+2}:v]overlay=shortest=1:enable=\'between(t,{c["start"]/rate:.9f},{c["end"]/rate:.9f})\'[{label}]');last=label
    cmd+=['-filter_complex',';'.join(graph),'-map',f'[{last}]','-an','-map_metadata','0','-map_chapters','0','-frames:v',str(target_frames),
          '-c:v','libx264','-crf',str(plan.get('crf',18)),'-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart',str(video_only)]
    paths['output_video'].parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(cmd,check=True)
    # Finish audio independently. No video frame cap, -t, -shortest, implicit pad or trim.
    audio_graph=[f'[0:a]{pitch_filter(rate,pitch)}[speech]',f'[1:a]atempo={rate}[bed]',
        '[speech][bed]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=0:latency=1[a]']
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(paths['speech']),'-i',str(paths['bed']),
        '-filter_complex',';'.join(audio_graph),'-map','[a]','-vn','-c:a','aac','-b:a','192k','-ar','48000',str(audio_only)],check=True)
    # Packet-copy completed tracks. The one-frame attached image has no output cap.
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n','-i',str(video_only),'-i',str(audio_only),'-i',str(paths['cover']),
        '-map','0:v:0','-map','1:a:0','-map','2:v:0','-map_metadata','0','-map_chapters','0','-c','copy',
        '-disposition:v:1','attached_pic','-movflags','+faststart',str(paths['output_video'])],check=True)
    def audio_packets(path):
        value=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=data_hash','-of','json',str(path)]))
        return [row['data_hash']for row in value['packets']]
    before_packets=audio_packets(audio_only);after_packets=audio_packets(paths['output_video'])
    if not before_packets or before_packets!=after_packets:raise ValueError('AAC packet payload/order changed during candidate remux')
    paths['output_srt'].parent.mkdir(parents=True,exist_ok=True)
    paths['output_srt'].write_text(''.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}\n\n' for i,c in enumerate(cues)))
    output=probe(paths['output_video']);actual=float(output['format']['duration'])
    main=next(s for s in output['streams']if s['codec_type']=='video'and not s.get('disposition',{}).get('attached_pic'))
    if abs(float(main['duration'])-target)>.05:raise ValueError('Encoded main video duration mismatch')
    subprocess.run(['ffmpeg','-v','error','-i',str(paths['output_video']),'-f','null','-'],check=True)
    receipt=dict(schema='course-media-finish/2',status='encoded-candidate-awaiting-release-check',plan_sha256=sha(plan_path),
        inputs={n:dict(path=str(paths[n]),sha256=sha(paths[n])) for n in required[:5]},
        outputs={n:dict(path=str(paths[n]),sha256=sha(paths[n])) for n in required[5:]},
        rate_relative_to_input=rate,speech_pitch_semitones=pitch,music_pitch_semitones=0,
        duration=actual,fps=str(fps),frames=target_frames,captions=len(cues),cover_first_frame=not timed,cover_mode='authorized-timed' if timed else 'single-frame',
        audio_complete_path=str(audio_only),audio_complete_sha256=sha(audio_only),audio_packet_count=len(after_packets),audio_packet_payloads_preserved=True,
        video_only_path=str(video_only),video_only_sha256=sha(video_only),full_decode=True,content_warnings=content_warnings,production_released=False,
        limits='Technical timing and decode proof; thumbnail aesthetics, speech intelligibility and user acceptance remain separate.')
    paths['output_video'].with_suffix('.finish.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);a=p.parse_args()
    print(json.dumps(finish(a.plan),ensure_ascii=False,indent=2))
