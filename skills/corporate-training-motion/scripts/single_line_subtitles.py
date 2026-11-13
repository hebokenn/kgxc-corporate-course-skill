#!/usr/bin/env python3
"""Local semantic subtitle splitting. Does not align phonemes or certify listening.
Input: JSON caption array (or {captions: [...]}); optional {cue_id: [phrases]}.
Never shrink type or split an overlong word automatically: request explicit phrases.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path


def clean(text):
    # Keep numeric meanings before removing visible punctuation.
    text = re.sub(r'(?<=\d)\s*[–—~～-]\s*(?=\d)', '至', text)
    text = re.sub(r'(\d{1,2})[:：](\d{2})', lambda m: m[1]+'点'+('' if m[2]=='00' else str(int(m[2]))+'分'), text)
    text = re.sub(r'(?<![\w\d])[-−](?=\d)', '负', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*[%％]', r'百分之\1', text)
    text = re.sub(r'(?<=\d)[.．](?=\d)', '点', text)
    # Unknown slash/date/fraction formats must be resolved explicitly, not erased.
    if re.search(r'\d\s*[/／]\s*\d', text):
        raise ValueError('Ambiguous numeric slash: provide an explicit meaning-preserving source phrase')
    return re.sub(r'\s+', ' ', ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in text)).strip()


def identity(text):
    return re.sub(r'\s+', '', clean(text))


def em_width(text):
    return sum(1 if unicodedata.east_asian_width(c) in 'WF' else .55 for c in text)


def stamp(t):
    n=round(t*1000)
    return f'{n//3600000:02d}:{n//60000%60:02d}:{n//1000%60:02d},{n%1000:03d}'


def prepare(captions, phrases=None, max_em=28, fps=30):
    phrases=phrases or {};out=[];old_end=-1
    for i,c in enumerate(captions):
        if c['start']<old_end-1e-6 or c['end']<=c['start']:raise ValueError('Unordered/overlapping source cues')
        old_end=c['end'];source=c['text'];cid=c.get('id',str(i+1));whole=clean(source)
        if cid in phrases:
            parts=[clean(p) for p in phrases[cid]]
        elif em_width(whole)<=max_em:
            parts=[whole]
        else:
            units=[clean(p) for p in re.split(r'[\n，。；！？、,;!?]+',source) if clean(p)]
            parts=[]
            for p in units:
                if em_width(p)>max_em:raise ValueError(f'{cid}: overlong semantic unit; supply explicit phrase boundaries')
                if parts and em_width(parts[-1]+' '+p)<=max_em:parts[-1]+=' '+p
                else:parts.append(p)
        if not parts or any(not p or em_width(p)>max_em for p in parts):raise ValueError(f'{cid}: empty/overlong phrase')
        if identity(''.join(parts))!=identity(source):raise ValueError(f'{cid}: phrase content changed')
        weights=[max(1,len(identity(p))) for p in parts];total=sum(weights);elapsed=0;boundaries=[c['start']]
        # Frame-aligned internal transitions, exact original outer span. These are
        # proportional estimates, to be reviewed against the unchanged narration.
        for w in weights[:-1]:
            elapsed+=w;boundaries.append(round((c['start']+(c['end']-c['start'])*elapsed/total)*fps)/fps)
        boundaries.append(c['end'])
        for j,p in enumerate(parts):
            start,end=boundaries[j:j+2]
            if end-start<.5:raise ValueError(f'{cid}: phrase too short; regroup or supply real alignment')
            out.append(dict(id=cid+f'-{j+1:02d}',source_id=cid,start=start,end=end,text=p,lines=[p],timing_method='original_span' if len(parts)==1 else 'proportional_frame_aligned_estimate'))
    return out


def validate(captions, metrics=None, safe=None):
    errors=[];previous=-1
    if not captions:errors.append('Empty caption set')
    for c in captions:
        text=c['text']
        if '\n' in text or '\r' in text or len(c.get('lines',[text]))!=1:errors.append(c['id']+': multiline')
        if any(unicodedata.category(x).startswith('P') for x in text):errors.append(c['id']+': punctuation')
        if c['start']<previous-1e-6 or c['end']<=c['start']:errors.append(c['id']+': timing')
        previous=c['end']
    if metrics is not None:
        by_id={m['id']:m for m in metrics}
        if len(by_id)!=len(captions):errors.append('Rendered metrics must cover every unique cue')
        for c in captions:
            m=by_id.get(c['id'],{})
            if m.get('text')!=c['text'] or m.get('line_count')!=1:errors.append(c['id']+': actual renderer multiline/mismatched')
            b=m.get('bounds')
            if not b or not safe or b[0]<safe[0] or b[1]<safe[1] or b[2]>safe[2] or b[3]>safe[3]:errors.append(c['id']+': actual glyph+stroke outside safe area')
    return errors


def write(cues, json_path, srt_path):
    Path(json_path).write_text(json.dumps(cues,ensure_ascii=False,indent=2)+'\n')
    Path(srt_path).write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('input',type=Path);ap.add_argument('--phrases',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--srt',type=Path,required=True);ap.add_argument('--max-em',type=float,default=28);ap.add_argument('--fps',type=int,default=30);a=ap.parse_args()
    data=json.loads(a.input.read_text());cues=prepare(data.get('captions',[]) if isinstance(data,dict) else data,json.loads(a.phrases.read_text()) if a.phrases else {},a.max_em,a.fps)
    errors=validate(cues)
    if errors:raise SystemExit('\n'.join(errors))
    write(cues,a.out,a.srt);print(json.dumps({'cues':len(cues),'single_line':True,'timing':'split boundaries estimated; inspect actual audio','actual_width_check':'required in final renderer'},ensure_ascii=False))
