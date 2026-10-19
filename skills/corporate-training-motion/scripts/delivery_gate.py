#!/usr/bin/env python3
"""Inspect approved brand inventory and actual first/last frames before full delivery.
No rendering, no uploads. Template or approval metadata alone cannot certify a final film.
"""
import argparse,json,hashlib,subprocess,io
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
def frame(p,t):
 from PIL import Image
 return Image.open(io.BytesIO(subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-f','image2pipe','-vcodec','png','-']))).convert('RGB')
def check(plan_path,assets_only=False,video_override=None):
 plan_path=Path(plan_path).resolve();root=plan_path.parent;plan=json.loads(plan_path.read_text());errors=[];evidence={};resolve=lambda s:(root/s).resolve()
 brand=plan.get('brand',{})
 if brand.get('required'):
  registry=resolve(brand['registry']);reg=json.loads(registry.read_text());evidence['registry_version']=reg['version']
  if reg.get('status')!='approved':errors.append('Brand registry is not approved')
  for n,a in reg['assets'].items():
   f=(registry.parent/reg.get('asset_root','..')/a['path']).resolve()
   if not f.exists() or sha(f)!=a['sha256']:errors.append('Approved mother asset changed/missing: '+n)
  for name in ['intro','outro']:
   a=brand.get('assets',{}).get(name)
   if not a:errors.append('Missing required brand asset '+name);continue
   f=resolve(a['path'])
   if not f.exists():errors.append('Missing file '+str(f));continue
   if sha(f)!=a['sha256']:errors.append('Asset fingerprint mismatch '+name)
   q=probe(f);duration=float(q['format']['duration']);evidence[name]={'sha256':sha(f),'duration':duration}
   if abs(duration-a['duration'])>.05:errors.append('Actual duration mismatch '+name)
   if duration<a.get('minimum_duration',0)-.01:errors.append('Brand segment too short '+name)
 if not assets_only:
  approvals=json.loads(resolve(plan['approvals']).read_text())
  if plan.get('requires_design_approval'):
   for key in ['character_design','representative_animation']:
    a=approvals.get(key,{})
    if a.get('status')!='approved' or not a.get('approved_sha256') or a.get('approved_sha256')!=(a.get('artifact_sha256') or a.get('current_design_sha256')) or not a.get('source_message_id'):errors.append('Matching explicit approved artifact missing: '+key)
    elif not a.get('artifact_path') or not resolve(a['artifact_path']).exists() or sha(resolve(a['artifact_path']))!=a['approved_sha256']:errors.append('Approved artifact bytes missing/changed: '+key)
  if plan.get('requires_pronunciation_review'):
   review=approvals.get('voice_pronunciation',{});audio=plan.get('narration_audio')
   if review.get('status')!='auditorily_verified':errors.append('Pronunciation listening check pending; text/SSML/ASR is insufficient')
   elif not audio or not resolve(audio).exists() or review.get('audio_sha256')!=sha(resolve(audio)) or not review.get('reviewer'):errors.append('Pronunciation listening record not bound to current narration bytes and reviewer')
  v=Path(video_override).resolve() if video_override else resolve(plan['full_video'])
  if not v.exists():errors.append('Final video missing')
  elif brand.get('required'):
   import numpy as np
   duration=float(probe(v)['format']['duration']);checks=[]
   for name in ['intro','outro']:
    a=brand['assets'].get(name);span=brand.get('final_ranges',{}).get(name,[None,None]);start,end=(span+[None,None])[:2]
    if a is None or start is None or end is None:errors.append('Actual final segment range absent: '+name);continue
    if abs(end-start-a['duration'])>.05:errors.append('Final segment range does not match prepared asset duration: '+name)
    if name=='intro' and abs(start)>.05:errors.append('Required intro is not at start of final video')
    if name=='outro' and abs(end-duration)>.05:errors.append('Required outro is not at end of final video')
    if start<0 or start+a['duration']>duration+.05:errors.append('Brand range outside final video: '+name);continue
    for sample in a['samples']:
     ref=frame(resolve(a['path']),sample['time']);actual=frame(v,start+sample['time']);ref=ref.resize(actual.size)
     l,t,r,b=sample.get('region',[0,.02,1,.88]);rect=tuple(round(x*s) for x,s in zip([l,t,r,b],[actual.width,actual.height,actual.width,actual.height]));x=np.asarray(ref.crop(rect),float);y=np.asarray(actual.crop(rect),float);mse=np.mean((x-y)**2);psnr=float(20*np.log10(255/np.sqrt(mse))) if mse else 100;checks.append({'segment':name,'time':start+sample['time'],'region':rect,'psnr_db':psnr})
     if psnr<sample.get('min_psnr',28):errors.append('Actual encoded brand picture mismatch: '+name)
   evidence['actual_first_last_frame_comparisons']=checks;evidence['video_sha256']=sha(v)
   review=plan.get('brand_audio_review',{})
   if review.get('status')!='reviewed' or review.get('video_sha256')!=sha(v):errors.append('Actual first/last audio and greeting review not bound to final video')
 return {'ok':not errors,'mode':'assets_only' if assets_only else 'final_release','errors':errors,'evidence':evidence,'limits':'selected actual brand frames and explicit review records; not whole-film aesthetic or listening certification'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--assets-only',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=check(a.plan,a.assets_only)
 if a.out:a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(not r['ok'])
