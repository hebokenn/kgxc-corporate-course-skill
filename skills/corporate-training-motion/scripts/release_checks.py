#!/usr/bin/env python3
"""Check an explicitly bound local release; never fill human review or authorize it.
Plan paths are relative to its parent. Final readiness is separate from technical_ok.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
from single_line_subtitles import validate

def check(plan_path):
    p=Path(plan_path).resolve();root=p.parent;plan=json.loads(p.read_text());errors=[];pending=[]
    def asset(a):
        name=a.get('path','');f=(root/name).resolve()
        if not name or Path(name).is_absolute() or not f.is_file():errors.append('Missing/nonrelative asset: '+name);return None
        if hashlib.sha256(f.read_bytes()).hexdigest()!=a.get('sha256'):errors.append('Stale asset: '+name)
        return f
    video=asset(plan['video'])
    for folder in [root,*root.parents]:
        config=folder/'project.json'
        if config.is_file():
            from check_workbench import check as editable_check, required as requires_workbench
            if requires_workbench(json.loads(config.read_text())):
                errors+=editable_check(folder,require_runtime=True,video=video)['errors']
            break
    for a in plan.get('assets',[]):asset(a)
    cue_file=asset(plan['captions']);metrics_file=asset(plan['caption_metrics'])
    if cue_file and metrics_file:
        errors+=validate(json.loads(cue_file.read_text()),json.loads(metrics_file.read_text()),plan['caption_safe'])
    if video:
        r=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],capture_output=True)
        if r.returncode or r.stderr.strip():errors.append('Actual final full decode failed')
        q=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
        vs=[s for s in q['streams'] if s.get('codec_type')=='video'];aud=[s for s in q['streams'] if s.get('codec_type')=='audio']
        if not vs or vs[0].get('codec_name')!='h264' or vs[0].get('pix_fmt')!='yuv420p' or not aud:errors.append('Final video/audio format')
        if abs(float(q['format']['duration'])-plan['duration'])>.05:errors.append('Duration mismatch')
    if plan.get('brand_required') and not plan.get('actual_brand_comparison'):errors.append('Actual brand comparison missing')
    for name in ['visual_review','normal_speed_playback','human_audio_review']:
        review=plan.get(name,{})
        if review.get('status')!='reviewed' or review.get('video_sha256')!=plan['video']['sha256'] or not review.get('scope'):pending.append(name)
    return {'technical_ok':not errors,'release_ready':not errors and not pending,'errors':errors,'pending_reviews':pending,'limits':'Technical checks do not certify beauty, natural motion, listening or user acceptance'}

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('plan');a.add_argument('--out',type=Path);args=a.parse_args();r=check(args.plan)
    if args.out:args.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(not r['technical_ok'])
