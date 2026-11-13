"""Course-selected packaging budgets; whole intro, static hold and time dependencies."""
import math
import re
import subprocess
from production_validation import Check, digest, resolve_current_video, ENCODED
from timeline import display_frame


def timing_bindings(doc, contract=None, project=None):
    contract=contract or {}
    sound=contract.get('requirements',{}).get('sfx',{})
    def actual_file(value):
        from production_validation import path_in,sha
        return sha(path_in(project,value)) if project is not None and isinstance(value,str) else None
    return {key:digest(value) for key,value in {
        'timeline':{k:doc.get(k) for k in ['fps','sourceDurationFrames','introFrames','bodyEndFrame','cuts','holds']},
        'captions':doc.get('captions',[]),'chapters':doc.get('chapterTable',[]),
        'audio':dict(media=doc.get('media',{}),parameters=doc.get('audio',{}),current_audio_sha256=actual_file(doc.get('media',{}).get('audio'))),
        'sfx':dict(document=doc.get('sfxPlan',doc.get('sfxEvents',[])),events=sound.get('events',[]),plan_path=sound.get('plan_path'),plan_sha256=actual_file(sound.get('plan_path')))}.items()}


def frozen_intervals(video,end_frame,fps):
    """Measure exact main-stream frames after the independent first-frame cover."""
    from media_frames import main_video
    stream=main_video(video)
    cmd=['ffmpeg','-nostdin','-v','info','-reinit_filter','0','-i',str(video),'-map','0:'+str(stream['index']),
         '-vf',f'trim=start_frame=1:end_frame={end_frame},setpts=PTS-STARTPTS,freezedetect=n=-50dB:d=0.1',
         '-an','-frames:v',str(max(0,end_frame-1)),'-f','null','-']
    run=subprocess.run(cmd,capture_output=True,text=True,timeout=180,check=True)
    starts=[float(x) for x in re.findall(r'freeze_start: ([0-9.]+)',run.stderr)]
    ends=[float(x) for x in re.findall(r'freeze_end: ([0-9.]+)',run.stderr)]
    duration=max(0,(end_frame-1)/fps)
    return [dict(start_seconds=s+1/fps,end_seconds=(next((e for e in ends if e>=s),duration)+1/fps),
                 duration_seconds=max(0,next((e for e in ends if e>=s),duration)-s)) for s in starts]


def inspect(project,doc,video,purpose,contract):
    c=Check('intro_pacing');policy=doc.get('introPolicy')
    if not policy or purpose not in {'storyboard',*ENCODED}:
        c.details['applicability']='No course-specific intro budget selected; no global hard duration imposed'
        return c.result()
    fps=doc.get('fps',30);intro=doc.get('introFrames',0)
    if (type(fps) not in (int,float) or not math.isfinite(fps) or fps<=0 or type(intro)is not int or intro<0):
        c.error('INTRO_POLICY_INVALID','Valid actual frame rate and intro boundary required');return c.result()
    values=[policy.get(k) for k in ['max_seconds','max_static_seconds']]
    if (not policy.get('source_ref') or not policy.get('reason') or
            any(type(x)not in(int,float)or not math.isfinite(x)or x<=0 for x in values)):
        c.error('INTRO_POLICY_INVALID','Selected whole-intro and static-hold budgets need source and reason');return c.result()
    end=round(display_frame(intro,doc.get('holds',[]),doc.get('cuts',[])))
    if end/fps>policy['max_seconds']+1/fps:
        c.error('INTRO_TOO_LONG','Entire packaging exceeds this course choice, including holds/cuts',actual_seconds=end/fps)
    speech=policy.get('first_speech_source_frame')
    if speech is not None:
        gap=policy.get('max_speech_gap_seconds')
        if type(speech)is not int or speech<intro or type(gap)not in(int,float)or not math.isfinite(gap)or gap<0:
            c.error('INTRO_SPEECH_BINDING_INVALID','Explicit valid first-speech boundary and allowed gap required')
        elif (display_frame(speech,doc.get('holds',[]),doc.get('cuts',[]))-end)/fps>gap+1/fps:
            c.error('INTRO_SPEECH_DELAY','Long wait remains after the shortened title card')
    if (purpose in ENCODED or policy.get('timing_bindings') is not None) and policy.get('timing_bindings')!=timing_bindings(doc,contract,project):
        c.error('INTRO_TIMELINE_STALE','Rebind current captions, chapters, audio/speed, SFX and total timeline after editing packaging')
    if purpose in ENCODED:
        try:
            from fractions import Fraction
            from media_frames import main_video
            stream=main_video(resolve_current_video(project,video))
            if abs(float(Fraction(stream['avg_frame_rate']))-fps)>.001:raise ValueError('Actual encoded frame rate differs from the intro time axis')
            if stream.get('nb_frames') and end>int(stream['nb_frames']):raise ValueError('Selected intro boundary is outside the actual encoded video')
            spans=frozen_intervals(resolve_current_video(project,video),end,fps) if end>1 else []
            c.details['actual_static_intervals']=spans
            if any(s['duration_seconds']>policy['max_static_seconds']+1/fps for s in spans):
                c.error('INTRO_STATIC_HOLD_LONG','Actual encoded intro/title still contains a long static hold')
        except (ValueError,OSError,subprocess.SubprocessError) as exc:c.error('INTRO_MEDIA_UNVERIFIED',str(exc))
    c.details.update(display_intro_end_frame=end,actual_seconds=end/fps,
        scope='Selected packaging timing and bounded encoded frozen-image measurement, not audio naturalness or continuous review')
    return c.result()
