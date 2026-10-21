import {displayFrame,sourceFrame,totalFrames} from './timeline.js';
export {displayFrame,sourceFrame,totalFrames} from './timeline.js';
export class CourseRenderer{
 constructor(canvas,frame){this.canvas=canvas;this.ctx=canvas.getContext('2d');this.frame=frame;this.videos={};this.lastKey='';this.imagePaths={}}
 async load(d){
  if(!this.native){for(let i=0;i<600&&!this.frame.contentWindow.ready;i++)await new Promise(r=>setTimeout(r,30));if(!this.frame.contentWindow.ready)throw Error('课程引擎未就绪');this.native=this.frame.contentWindow;this.sourceCanvas=this.frame.contentDocument.querySelector('canvas');if(!this.sourceCanvas)throw Error('课程引擎没有画布');
   const font=new FontFace('CourseHan',`url('/project/${d.font||'native/assets/fonts/SourceHanSansCN-Medium.otf'}')`);await font.load();document.fonts.add(font);await document.fonts.ready;
  }
  this.doc=structuredClone(d);
  if(d.adapter==='national-world-v1'){
   if(!this.baseWorld){this.baseWorld=structuredClone(this.native.WORLD);this.baseAssets={...this.native.eval('ASSETS')}}
  const w=this.native.WORLD;for(const g of w.groups){const base=this.baseWorld.groups.find(x=>x.id===g.id);if(base)Object.assign(g,structuredClone(base))}
  const targets=new Map();for(const g of w.groups){targets.set(g.id,g);for(const p of g.points)targets.set(p.id,p)}
  const offsets=new Map();for(const field of d.fields){const obj=targets.get(field.objectId);if(!obj)continue;obj[field.property]=field.text;const old=offsets.get(field.objectId)||[0,0];offsets.set(field.objectId,[old[0]+field.dx,old[1]+field.dy])}
  for(const [id,[dx,dy]]of offsets){const obj=targets.get(id);if(typeof obj.x==='number')obj.x+=dx;if(typeof obj.y==='number')obj.y+=dy}
  const nativeAssets=this.native.eval('ASSETS');
  for(const a of d.assets){if(this.imagePaths[a.id]===a.path)continue;if(a.path===a.originalPath){nativeAssets[a.id]=this.baseAssets[a.id]}else{const image=new Image();image.src='/project/'+a.path;await image.decode();nativeAssets[a.id]=image}this.imagePaths[a.id]=a.path}
   this.bindingReceipt={fields:d.fields.map(f=>f.id),assets:d.assets.map(a=>a.id)};
  }else{
   const bridge=this.native.courseWorkbench;if(!bridge||bridge.version!==1||typeof bridge.apply!=='function'||typeof bridge.seek!=='function')throw Error('课程缺少统一工作台桥接接口');
   this.bindingReceipt=await bridge.apply(structuredClone(d));
   for(const [key,items]of [['fields',d.fields],['assets',d.assets]]){const got=this.bindingReceipt?.[key];if(!Array.isArray(got)||items.some(x=>!got.includes(x.id)))throw Error('课程引擎没有应用全部可编辑'+key)}
  }
  for(const k of ['intro','outro']){if(d.media[k]&&!this.videos[k]){const v=document.createElement('video');v.muted=true;v.preload='auto';v.playsInline=true;v.src='/project/'+d.media[k];await new Promise((resolve,reject)=>{v.onloadedmetadata=resolve;v.onerror=()=>reject(Error('包装视频无法加载'));v.load()});this.videos[k]=v}}
  this.lastKey='';return true;
 }
 async seekVideo(video,t){t=Math.max(0,Math.min(t,video.duration-.04));if(Math.abs(video.currentTime-t)<.00001&&video.readyState>=2)return;await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('包装视频定位超时')),10000);video.onseeked=()=>{clearTimeout(timer);resolve()};video.currentTime=t;})}
 key(frame){const d=this.doc,s=sourceFrame(frame,d.holds,d.cuts),c=d.captions.find(x=>x.startFrame<=frame&&frame<x.endFrame);let key=s<d.introFrames?'intro-'+s:s>=d.bodyEndFrame?'outro-'+s:(d.adapter==='national-world-v1'?this.native.frameKey(s/d.fps):(this.native.courseWorkbench.frameKey?.(s/d.fps)??('frame-'+s)));return key+'|'+(c?.id||'')}
 async drawFrame(frame){
  const d=this.doc;frame=Math.max(0,Math.min(totalFrames(d)-1,Math.round(frame)));const source=sourceFrame(frame,d.holds,d.cuts),t=source/d.fps,c=this.ctx;let kind='native';
  c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,1920,1080);
  if(source<d.introFrames){kind='intro';await this.seekVideo(this.videos.intro,t);c.drawImage(this.videos.intro,0,0,1920,1080)}
  else if(source>=d.bodyEndFrame){kind='outro';await this.seekVideo(this.videos.outro,t-d.bodyEndFrame/d.fps);c.drawImage(this.videos.outro,0,0,1920,1080)}
  else{if(d.adapter==='national-world-v1')await this.native.seek(t);else await this.native.courseWorkbench.seek(t);c.drawImage(this.sourceCanvas,0,0,1920,1080)}
  const cue=d.captions.find(x=>x.startFrame<=frame&&frame<x.endFrame);let metric=null;
  if(cue){const s=d.captionStyle;c.font=`500 ${s.fontSize}px CourseHan`;c.textAlign='center';c.textBaseline='middle';c.lineJoin='round';c.lineWidth=s.strokeWidth;const m=c.measureText(cue.text),bounds=[960-m.actualBoundingBoxLeft-s.strokeWidth/2,s.y-m.actualBoundingBoxAscent-s.strokeWidth/2,960+m.actualBoundingBoxRight+s.strokeWidth/2,s.y+m.actualBoundingBoxDescent+s.strokeWidth/2];if(bounds[0]<112||bounds[2]>1808||bounds[1]<80||bounds[3]>1030)throw Error('字幕超出画面安全区：'+cue.id+'，请调整字号或位置，长句可按语义拆分');c.strokeStyle=s.stroke;c.fillStyle=s.fill;c.strokeText(cue.text,960,s.y);c.fillText(cue.text,960,s.y);metric={id:cue.id,text:cue.text,line_count:1,bounds}}
  let motionReceipt=[];if(kind==='native'&&d.motionPolicy?.required){if(typeof this.native.courseWorkbench.motionReceipt!=='function')throw Error('实际引擎未提供动效运行回执，不得通过改路线绕过检查');motionReceipt=this.native.courseWorkbench.motionReceipt()}
  this.frameNumber=frame;this.lastMetric=metric;return {frame,sourceFrame:source,kind,caption:metric,key:this.key(frame),motionReceipt};
 }
}
