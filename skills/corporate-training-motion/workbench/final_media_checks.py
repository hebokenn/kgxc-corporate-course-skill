"""Actual final bytes and honestly scoped AV evidence. Candidate checks never imply listening."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import re
import subprocess
from execution_requirements import error,read
from evidence_versions import sha

MEDIA={'pilot','final','delivery'}


def run(args):
    return subprocess.run(args,check=True,capture_output=True).stdout


def probe(path, count=False):
    args=['ffprobe','-v','error']+(['-count_frames'] if count else [])
    return json.loads(run(args+['-show_streams','-show_format','-show_chapters','-of','json',str(path)]))


def main_video(meta):
    streams=[s for s in meta.get('streams',[]) if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
    if len(streams)!=1:raise ValueError('Exactly one non-attached main video stream required')
    return streams[0]


def ref_path(project,ref,allow_delivery=False):
    p=Path(project).resolve()
    if not isinstance(ref,dict) or not ref.get('path') or not ref.get('sha256'):raise ValueError('Current path/SHA required')
    q=(p/ref['path']).resolve()
    if not q.is_relative_to(p.parent if allow_delivery else p) or not q.is_file() or sha(q)!=ref['sha256']:
        raise ValueError('Missing or changed media reference: '+str(q))
    return q


def packets(path):
    d=json.loads(run(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256',
        '-show_entries','packet=data_hash,duration_time,pts_time,side_data_list','-of','json',str(path)]))
    return d.get('packets',[])


def rgb_frame(path,index,stream_index,width,height):
    return run(['ffmpeg','-v','error','-i',str(path),'-map','0:'+str(stream_index),'-vf',
        'select=eq(n\\,%d),scale=%d:%d,format=rgb24'%(index,width,height),'-frames:v','1','-f','rawvideo','-'])


def _near(a,b,tolerance):
    return bool(a and len(a)==len(b) and sum(abs(x-y)for x,y in zip(a,b))/len(a)<=tolerance)


def _srt(path):
    result=[]
    def seconds(s):
        h,m,t,ms=map(int,re.split('[:,]',s));return h*3600+m*60+t+ms/1000
    for block in re.split(r'\n\s*\n',Path(path).read_text(encoding='utf-8-sig').strip()):
        lines=block.splitlines()
        if len(lines)<3 or ' --> 'not in lines[1]:raise ValueError('Invalid SRT')
        a,z=lines[1].split(' --> ')
        result.append(dict(start=seconds(a),end=seconds(z),text='\n'.join(lines[2:])))
    return result


def _observation_record(project,record,video_sha,doc_sha,kind,needed_frames=()):
    errors=[]
    if isinstance(record,str):record=read(Path(project)/record)
    if not isinstance(record,dict):record={}
    if (record.get('status')!='verified' or not record.get('actor') or not record.get('scope') or
            not record.get('method') or record.get('video_sha256')!=video_sha or record.get('document_sha256')!=doc_sha):
        return [error('AUDIO_REVIEW_UNVERIFIED' if kind in {'tail_listening','full_av'}else 'MEDIA_REVIEW_UNVERIFIED',
            'Current actually observed scope is missing/unverified.',item=kind)]
    if kind in {'tail_listening','full_av'}:
        if record.get('method') not in {'actual-audio-listening','actual-continuous-av','user-actual-media-review'}:
            errors.append(error('AUDIO_REVIEW_UNVERIFIED','ASR/signal/frames do not prove actual listening.',item=kind))
        if record.get('listening_performed')is not True or kind=='full_av' and record.get('continuous_playback')is not True:
            errors.append(error('AUDIO_REVIEW_UNVERIFIED','Actual listening/continuous playback was not performed.',item=kind))
        if not record.get('range_seconds') or not record.get('observations'):
            errors.append(error('AUDIO_REVIEW_UNVERIFIED','Actual listening needs time range and observations.',item=kind))
        try:
            if record.get('method')=='user-actual-media-review':
                event=read(ref_path(project,record.get('source_event_ref')))
                if (event.get('actor_type')!='user' or not event.get('original_quote') or event.get('video_sha256')!=video_sha or
                        event.get('listening_performed')is not True):raise ValueError('No actual current user media-listening declaration')
            else:
                capability=read(ref_path(project,record.get('capability_ref')))
                needed={'audio_listening'}|({'continuous_video'}if kind=='full_av'else set())
                if (capability.get('schema')!='review-runner-probe/1' or not capability.get('tool') or not capability.get('route') or
                        not needed<=set(capability.get('capabilities',[])) or not capability.get('probes') or
                        not any(p.get('ok')is True for p in capability['probes'])):
                    raise ValueError('Actual runner probe does not establish the listening/video capability')
        except (ValueError,TypeError)as exc:
            errors.append(error('AUDIO_REVIEW_UNVERIFIED',str(exc),item=kind))
    elif kind=='thumbnail_review' and record.get('method')not in {'native-thumbnail','native-finder-quicklook','native-file-browser'}:
        errors.append(error('MEDIA_REVIEW_UNVERIFIED','Web poster is not a native external thumbnail.'))
    rows=record.get('observations',[])
    if not isinstance(rows,list) or not rows:
        errors.append(error('MEDIA_REVIEW_UNVERIFIED','Actual observations are required.',item=kind))
        rows=[]
    if kind=='thumbnail_review' and not any(isinstance(r,dict) and r.get('path') and r.get('sha256')for r in rows):
        errors.append(error('MEDIA_REVIEW_UNVERIFIED','Native external thumbnail needs an actual retained image reference.'))
    if needed_frames and not set(needed_frames)<={r.get('frame') for r in rows if isinstance(r,dict)}:
        errors.append(error('MEDIA_REVIEW_UNVERIFIED','Required current boundary frames have not been observed.',item=kind))
    for r in rows:
        if isinstance(r,dict) and r.get('path'):
            try:ref_path(project,r)
            except ValueError as exc:errors.append(error('EVIDENCE_STALE',str(exc),item=kind))
    if record.get('critical_unknown') or record.get('unverified'):
        errors.append(error('MEDIA_REVIEW_UNVERIFIED','Critical observation scope remains unknown.',item=kind))
    return errors


def inspect(project,context):
    p=Path(project).resolve();purpose=context['purpose'];errors=[];checks={};evidence=[]
    # Existing review-cycle and human-audio requirements remain authoritative.
    try:
        from workflow import Course
        from ai_review import gate_errors,approved,enabled
        course=Course(p.parent)
        review_errors=gate_errors(course, 'final' if purpose=='delivery' else purpose)
        errors.extend(error('REVIEW_NOT_READY',str(x)) for x in review_errors)
        if purpose in {'script','storyboard','pilot','final','delivery'} and read(p/'production-contract.json').get('execution_policy')=='required' and not enabled(course):
            errors.append(error('REVIEW_NOT_READY','A current execution contract cannot treat an unconfigured review runner as a completed review.'))
        if purpose=='delivery' and not approved(course,'final'):
            errors.append(error('HUMAN_CONFIRMATION_REQUIRED','Applicable actual final human confirmation is not current.'))
    except Exception as exc:
        errors.append(error('REVIEW_NOT_READY','Existing review state cannot be verified: '+str(exc)))
    if purpose not in MEDIA:
        return dict(ready=not errors,errors=errors,checks=dict(future_media='not_applicable_at_current_stage'),evidence_refs=[])
    try:
        doc_path=(p/context['current_document']).resolve();doc=read(doc_path)
        video=(p/context['current_video']).resolve()
        if not video.is_relative_to(p.parent) or not video.is_file():raise ValueError('Current encoded video is outside course')
        vs,ds=sha(video),sha(doc_path)
        contract=read(p/'production-contract.json');plan=contract.get('final_media',{})
        if isinstance(plan,str):plan=read(p/plan)
        expected=plan.get('expected',{})
        if not all(k in expected for k in ['frames','fps','width','height']):raise ValueError('Master contract final_media.expected missing')
        source=ref_path(p,plan.get('source_video'),True)
        narration=ref_path(p,plan.get('narration'))
        srt=ref_path(p,plan.get('subtitles'))
        cover=ref_path(p,plan.get('cover')) if purpose in {'final','delivery'} or plan.get('cover') else None
        fps=Fraction(str(expected['fps']));count=expected['frames']
        if type(count)is not int or count<2 or fps<=0:raise ValueError('Invalid expected frame clock')
        meta=probe(video,True);main=main_video(meta);source_main=main_video(probe(source))
        actual_frames=int(main.get('nb_read_frames',main.get('nb_frames',0)))
        actual_fps=Fraction(main.get('avg_frame_rate','0/1'))
        if (actual_frames!=count or actual_fps!=fps or main['width']!=expected['width'] or main['height']!=expected['height']):
            errors.append(error('FINAL_VIDEO_CLOCK_MISMATCH','Actual main stream differs from the current expected clock.'))
        frame_clock=json.loads(run(['ffprobe','-v','error','-select_streams',str(main['index']),'-show_frames',
            '-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)])).get('frames',[])
        if len(frame_clock)!=count or any(abs(float(row.get('best_effort_timestamp_time',-999))-i/float(fps))>.000002 for i,row in enumerate(frame_clock)):
            errors.append(error('FINAL_VIDEO_CLOCK_MISMATCH','Actual decoded timestamps are not the declared zero-based frame clock.'))
        run(['ffmpeg','-v','error','-err_detect','explode','-i',str(video),'-map','0:'+str(main['index']),'-map','0:a:0','-f','null','-'])
        checks['decode']=dict(ready=True,frames=actual_frames,fps=str(actual_fps),width=main['width'],height=main['height'],main_stream_index=main['index'],attached_pic_excluded=True)
        w,h=expected['width'],expected['height']
        first=rgb_frame(video,0,main['index'],w,h);second=rgb_frame(video,1,main['index'],w,h)
        if cover:
            cover_meta=probe(cover);cover_stream=next(s for s in cover_meta['streams']if s['codec_type']=='video')
            cover_rgb=run(['ffmpeg','-v','error','-i',str(cover),'-map','0:'+str(cover_stream['index']),'-vf',
                'scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,format=rgb24'%(w,h,w,h),'-frames:v','1','-f','rawvideo','-'])
        source_second=rgb_frame(source,1,source_main['index'],w,h)
        tolerance=plan.get('pixel_tolerance',12)
        if not isinstance(tolerance,(int,float)) or not 0<=tolerance<=12:raise ValueError('Cover comparison tolerance cannot be loosened beyond12 RGB levels')
        if cover and (not _near(first,cover_rgb,tolerance) or not _near(second,source_second,tolerance)):
            errors.append(error('COVER_FRAME_MISMATCH','Cover must occupy only frame0; frame1 must match original source frame1.'))
        checks['first_frames']=dict(frame0_rgb_sha256=hashlib.sha256(first).hexdigest(),frame1_rgb_sha256=hashlib.sha256(second).hexdigest(),source_frame1_rgb_sha256=hashlib.sha256(source_second).hexdigest())
        audio=plan.get('audio',{});mode=audio.get('mode');audio_source=ref_path(p,audio.get('source'),True)
        if mode=='copy':
            before,after=packets(audio_source),packets(video)
            if not before or [x.get('data_hash')for x in before]!=[x.get('data_hash')for x in after]:
                errors.append(error('AAC_PAYLOAD_MISMATCH','Copied audio packet payload/order changed or tail packets were lost.'))
            if len(before)==len(after):
                offset=audio.get('expected_offset_seconds',0)
                if (any(abs(float(a.get('pts_time',-999))-float(b.get('pts_time',-999))-offset)>.000002 or
                        abs(float(a.get('duration_time',-999))-float(b.get('duration_time',-999)))>.000002
                        for a,b in zip(after,before))):
                    errors.append(error('AUDIO_SAMPLE_CLOCK_MISMATCH','Copied packet timing/duration differs from its declared source alignment.'))
            checks['audio']=dict(mode=mode,source_packets=len(before),current_packets=len(after),packet_payloads_equal=bool(before)and [x.get('data_hash')for x in before]==[x.get('data_hash')for x in after])
        elif mode=='reencode':
            ameta=probe(video);stream=next(s for s in ameta['streams']if s['codec_type']=='audio');rate=int(stream['sample_rate'])
            pcm=run(['ffmpeg','-v','error','-i',str(video),'-map','0:a:0','-ac','1','-ar',str(rate),'-f','s16le','-'])
            wanted=audio.get('expected_samples');tolerance=audio.get('calibrated_sample_tolerance')
            if type(wanted)is not int or type(tolerance)is not int or tolerance<0 or not audio.get('tolerance_basis') or abs(len(pcm)//2-wanted)>tolerance:
                errors.append(error('AUDIO_SAMPLE_CLOCK_MISMATCH','Reencoded audio needs current expected samples and calibrated codec-padding tolerance.'))
            checks['audio']=dict(mode=mode,decoded_samples=len(pcm)//2,sample_rate=rate,expected_samples=wanted)
        else:errors.append(error('AUDIO_MODE_UNDECLARED','Copy and intentional reencoding require different checks.'))
        cues=_srt(srt);duration=count/float(fps)
        for i,c in enumerate(cues):
            if not 0<=c['start']<c['end']<=duration+.001 or i and cues[i-1]['end']>c['start']+.001:
                errors.append(error('SRT_TIME_MISMATCH','Illegal/overlapping/out-of-range current caption.',item=i+1))
        expected_cues=doc.get('captions',[])
        clip=plan.get('source_range',[0,count] if count==doc.get('sourceDurationFrames') else None)
        if purpose=='pilot':
            display_end=doc.get('sourceDurationFrames',count)-sum(c['endFrame']-c['startFrame']for c in doc.get('cuts',[]))+sum(h['frames']for h in doc.get('holds',[]))
            if not isinstance(clip,list) or len(clip)!=2 or any(type(x)is not int for x in clip)or clip[0]<0 or clip[1]>display_end or clip[1]-clip[0]!=count:
                errors.append(error('SAMPLE_SEMANTIC_BOUNDARY','Pilot needs its explicit current display-frame range.'));clip=[0,count]
            if any(c.get('startFrame',0)<f<c.get('endFrame',0)for c in expected_cues for f in clip):
                errors.append(error('SAMPLE_SEMANTIC_BOUNDARY','Sample cut crosses an actual caption/phrase; next partial sentence must not leak.'))
            expected_cues=[dict(c,startFrame=c['startFrame']-clip[0],endFrame=c['endFrame']-clip[0])for c in expected_cues if clip[0]<=c['startFrame']<c['endFrame']<=clip[1]]
            checks['sample_boundary']=dict(source_range=clip,scope='Structural complete-cue boundaries only; whole-task semantic completeness still requires current learner/AV review.')
        if expected_cues and (len(cues)!=len(expected_cues) or any(c['text']!=d.get('text') or abs(c['start']-d.get('startFrame',-1)/float(fps))>.001 or abs(c['end']-d.get('endFrame',-1)/float(fps))>.001 for c,d in zip(cues,expected_cues))):
            errors.append(error('SRT_TIME_MISMATCH','Current subtitles do not match the current display timeline.'))
        table=contract.get('requirements',{}).get('chapters',{}).get('chapter_table',[])
        if isinstance(table,str):table=read(p/table,[])
        actual_chapters=meta.get('chapters',[])
        if purpose=='pilot' and not actual_chapters:
            checks['chapter_metadata']=dict(status='not_applicable-to-unpackaged-pilot',scope='Final MP4 chapter metadata remains required at final/delivery; current navigation/table is checked by production_validation.')
        elif not table or len(table)!=len(actual_chapters) or any(x.get('label')!=y.get('tags',{}).get('title') or
            abs(x.get('display_start',-100)/float(fps)-float(y.get('start_time',-999)))>.001 or
            abs(x.get('display_end',-100)/float(fps)-float(y.get('end_time',-999)))>.001 for x,y in zip(table,actual_chapters)):
            errors.append(error('CHAPTER_TABLE_STALE','MP4 chapters differ from the one current chapter table.'))
        boundaries=sorted({0,1,*[f for k in (['introFrames','bodyEndFrame'] if purpose in {'final','delivery'} else [])if type(doc.get(k))is int for f in [max(0,doc[k]-1),doc[k]]if f<count]})
        errors.extend(_observation_record(p,plan.get('visual_review'),vs,ds,'visual_review',boundaries))
        if purpose in {'final','delivery'}:errors.extend(_observation_record(p,plan.get('thumbnail_review'),vs,ds,'thumbnail_review'))
        errors.extend(_observation_record(p,plan.get('tail_listening'),vs,ds,'tail_listening'))
        errors.extend(_observation_record(p,plan.get('full_av'),vs,ds,'full_av'))
        for key in ['tail_listening','full_av']:
            record=plan.get(key,{})
            if isinstance(record,str):record=read(p/record)
            span=record.get('range_seconds',[]) if isinstance(record,dict)else []
            start_limit=0 if key=='full_av' else max(0,(doc.get('bodyEndFrame',count)if purpose in {'final','delivery'}else count)/float(fps)-8)
            if len(span)!=2 or span[0]>start_limit or span[1]<duration-1/float(fps):
                errors.append(error('AUDIO_REVIEW_UNVERIFIED','Actual recorded range does not cover the required end/full video.',item=key))
        # Image files must come from this exact decoded frame, not merely carry a claimed parent SHA.
        visual=plan.get('visual_review',{})
        if isinstance(visual,str):visual=read(p/visual)
        for row in visual.get('observations',[]) if isinstance(visual,dict)else []:
            if row.get('frame') not in boundaries:continue
            try:
                image=ref_path(p,row);image_main=next(s for s in probe(image)['streams']if s['codec_type']=='video')
                pixels=rgb_frame(image,0,image_main['index'],w,h)
                actual_pixels=first if row['frame']==0 else second if row['frame']==1 else rgb_frame(video,row['frame'],main['index'],w,h)
                if pixels!=actual_pixels:raise ValueError('Image pixels do not match current decoded boundary frame')
            except Exception as exc:errors.append(error('EVIDENCE_STALE',str(exc),item='boundary-frame'))
        evidence=[dict(path=str(video),sha256=vs),dict(path=str(doc_path),sha256=ds),dict(path=str(narration),sha256=sha(narration)),dict(path=str(srt),sha256=sha(srt))]+([dict(path=str(cover),sha256=sha(cover))]if cover else [])
    except Exception as exc:
        errors.append(error('FINAL_MEDIA_NOT_READY',type(exc).__name__+': '+str(exc)))
    return dict(ready=not errors,errors=errors,checks=checks,evidence_refs=evidence,
        scope='Computed current media facts and attributed review scope; neither ASR nor packet identity proves actual listening/user acceptance.')
