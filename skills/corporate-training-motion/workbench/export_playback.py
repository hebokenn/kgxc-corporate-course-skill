"""Freeze navigation against the exported timeline, never a later editable document."""
from timeline import display_frame, duration, segments
from pathlib import Path
import json
from performance_cache import sha


def audio_settings(doc,project):
    project=Path(project).resolve();name=doc.get('media',{}).get('audio');unknown={'summary':''}
    if not isinstance(name,str):return unknown
    audio=(project/name).resolve()
    if not audio.is_relative_to(project) or not audio.is_file():return unknown
    digest=sha(audio)
    for file in [audio.with_suffix(audio.suffix+'.voice.json'),audio.with_suffix(audio.suffix+'.json'),project/'audio-settings.json']:
        try:value=json.loads(file.read_text())
        except (OSError,ValueError):continue
        if value.get('audio_sha256',value.get('output_sha256'))!=digest:continue
        voice=value.get('label') or value.get('profile') or value.get('voice_id') or value.get('id');speed=value.get('delivery_rate',value.get('speed'))
        if isinstance(voice,str):return dict(summary='音色 '+voice+('，语速 '+str(speed)+' 倍' if speed is not None else ''),voice=voice,speed=speed)
    return unknown


def playback(doc, first=0, last=None):
    fps=doc['fps'];last=duration(doc) if last is None else last
    holds=doc.get('holds',[]);cuts=doc.get('cuts',[])
    def position(frame):return display_frame(frame,holds,cuts)
    bindings=[]
    for binding in doc.get('storyboardBindings',[]) or []:
        start,end=binding.get('startFrame'),binding.get('endFrame')
        if type(start) is not int or type(end) is not int or start>=end:continue
        a,b=position(start),position(end)
        if min(b,last)<=max(a,first):continue
        kept=[]
        for span in segments(doc):
            x,y=max(first,span['startFrame']),min(last,span['endFrame'])
            if span['kind']=='source' and x<y:
                kept.append((span['sourceFrame']+x-span['startFrame'],span['sourceFrame']+y-span['startFrame']))
        cursor=start
        for x,y in kept:
            if x>cursor:break
            cursor=max(cursor,y)
        bindings.append(dict(binding,playback_start=max(0,(a-first)/fps),
                             playback_end=(min(b,last)-first)/fps,
                             playback_complete=a>=first and b<=last and cursor>=end))
    chapters=[];previous=None
    for scene in doc.get('scenes',[]):
        title=scene.get('chapter') or scene.get('title')
        start,end=position(scene['sourceStartFrame']),position(scene['sourceEndFrame'])
        if not title or min(end,last)<=max(start,first):continue
        if title!=previous:
            chapters.append(dict(id=scene['id'],title=title,start=max(0,(start-first)/fps)))
            previous=title
    return dict(schema='course-export-playback/1',fps=fps,duration_seconds=(last-first)/fps,
                firstFrame=first,lastFrame=last,bindings=bindings,chapters=chapters)
