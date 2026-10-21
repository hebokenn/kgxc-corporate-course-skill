/* Editable scene composition: no course-specific layout or WORLD dependency. */
(()=>{
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');let doc,images={},nodes=[],activeScene,transformCalls=[];
 const clamp=x=>Math.max(0,Math.min(1,x));
 function state(node,frame){const n={...node},initialized=new Set();for(const a of [...(node.motion||[])].sort((a,b)=>a.startFrame-b.startFrame)){if(frame<a.startFrame){if(!initialized.has(a.property))n[a.property]=a.from;}else{let u=clamp((frame-a.startFrame)/Math.max(1,a.endFrame-a.startFrame));if(window.CourseMotion)u=CourseMotion.ease(a.ease,u);else if(a.ease!=='linear')u=u*u*(3-2*u);n[a.property]=a.from+(a.to-a.from)*u;}initialized.add(a.property)}return n}
 function draw(n,frame){if(n.sceneId&&n.sceneId!==activeScene)return;if(frame<(n.startFrame??0)||frame>=(n.endFrame??doc.sourceDurationFrames))return;
  const fx=window.CourseMotion;n=state(n,frame);ctx.save();ctx.translate((n.x||0)+(n.editDx||0),(n.y||0)+(n.editDy||0));ctx.rotate((n.rotation||0)*Math.PI/180);ctx.scale(n.scaleX??1,n.scaleY??1);ctx.globalAlpha*=n.opacity??1;ctx.fillStyle=fx?fx.paint(ctx,n.fill||'#23463c'):n.fill||'#23463c';ctx.strokeStyle=fx?fx.paint(ctx,n.stroke||'#547c70'):n.stroke||'#547c70';ctx.lineWidth=n.lineWidth||3;
  if(n.matrix)ctx.transform(...n.matrix);
  if(n.clip){ctx.beginPath();ctx.rect(...n.clip);ctx.clip()}
  if(n.motion)for(const a of n.motion)if(a.from!==a.to&&a.startFrame<=frame&&frame<a.endFrame)transformCalls.push({nodeId:n.id,type:'transform-'+a.property,frame,startFrame:a.startFrame,endFrame:a.endFrame,progress:(frame-a.startFrame)/(a.endFrame-a.startFrame),role:n.role||'subject'});
  if(fx)fx.before(ctx,n,frame);
  const w=n.width??100,h=n.height??100,custom=fx&&fx.shape(ctx,n,frame);
  if(n.type==='rect'&&!custom){ctx.beginPath();ctx.roundRect(0,0,w,h,n.radius||0);if(n.fill!==null)ctx.fill();if(n.stroke)ctx.stroke()}
  if(n.type==='ellipse'&&!custom){ctx.beginPath();ctx.ellipse(0,0,w/2,h/2,0,0,Math.PI*2);if(n.fill!==null)ctx.fill();if(n.stroke)ctx.stroke()}
  if(n.type==='line'){if(!fx||!fx.path(ctx,n,frame)){ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(n.x2??w,n.y2??h);ctx.stroke()}}
  if(n.type==='path'){if(!fx||!fx.path(ctx,n,frame)){const p=new Path2D(n.path);if(n.fill!==null)ctx.fill(p);if(n.stroke)ctx.stroke(p)}}
  if(n.type==='text'){ctx.font=`${n.fontSize||48}px ${n.fontFamily||'CourseHan'}`;ctx.textBaseline='top';ctx.textAlign=n.align||'left';if(!fx||!fx.text(ctx,n,frame,doc.fps))String(n.text||'').split('\n').forEach((line,i)=>ctx.fillText(line,0,i*(n.lineHeight||1.4)*(n.fontSize||48)))}
  if(n.type==='image'){if(fx&&fx.image(ctx,n,frame,images)){}else{const im=images[n.assetId];if(!im)throw Error('未绑定图片 '+n.assetId);const box=n.crop||[0,0,1,1],sx=box[0]*im.width,sy=box[1]*im.height,cw=box[2]*im.width,ch=box[3]*im.height;if(n.fit==='cover'){const scale=Math.max(w/cw,h/ch),sw=w/scale,sh=h/scale;ctx.drawImage(im,sx+(cw-sw)/2,sy+(ch-sh)/2,sw,sh,0,0,w,h)}else{const scale=Math.min(w/cw,h/ch),iw=cw*scale,ih=ch*scale;ctx.drawImage(im,sx,sy,cw,ch,(w-iw)/2,(h-ih)/2,iw,ih)}}}
  for(const child of fx?fx.children(n,frame):n.children||[])draw(child,frame);if(fx)fx.after(ctx,n,frame);ctx.restore();
 }
 function walk(items,fn){for(const n of items){fn(n);walk(n.children||[],fn)}}
 window.courseWorkbench={version:1,
  async apply(value){doc=structuredClone(value);nodes=doc.sceneGraph?.nodes||[];images={};if(window.CourseMotion)CourseMotion.resetAssets();const byId=new Map();walk(nodes,n=>byId.set(n.id,n));const fields=[];
   for(const f of doc.fields){const node=byId.get(f.objectId);if(!node)throw Error('未绑定画面字段 '+f.id);if(f.property==='text')node.text=f.text;node.editDx=(node.editDx||0)+f.dx;node.editDy=(node.editDy||0)+f.dy;fields.push(f.id)}
   for(const a of doc.assets){const im=new Image();im.src='/project/'+a.path;await im.decode();images[a.id]=im}
   if(doc.rendering?.route==='motion-canvas'&&!window.CourseMotion)throw Error('动效画布尚未接入，不得使用简易画布忽略动效');
   await document.fonts.load('42px CourseHan');const families=new Set();walk(nodes,n=>{if(n.fontFamily)families.add(n.fontFamily)});for(const family of families)await document.fonts.load('48px '+family);await document.fonts.ready;
   return {fields,assets:doc.assets.map(a=>a.id)};
  },
  async seek(seconds){const f=Math.round(seconds*doc.fps);transformCalls=[];if(window.CourseMotion)CourseMotion.beginFrame(f);activeScene=doc.scenes.find(s=>s.sourceStartFrame<=f&&f<s.sourceEndFrame)?.id;ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.clearRect(0,0,1920,1080);if(!window.CourseMotion||!CourseMotion.background(ctx,doc.sceneGraph||{},f,doc.fps)){ctx.fillStyle=doc.sceneGraph?.background||'#f3f2ec';ctx.fillRect(0,0,1920,1080)}
   if(doc.status==='draft'&&!nodes.length){ctx.fillStyle='#718278';ctx.font='42px CourseHan';ctx.fillText('课程工程已建立  等待内容与配音',220,480)}
   for(const s of doc.scenes){if(s.sourceStartFrame<=f&&f<s.sourceEndFrame){ctx.save();if(window.CourseMotion)CourseMotion.camera(ctx,state(doc.sceneGraph?.camera||{},f));for(const n of nodes.filter(n=>!n.sceneId||n.sceneId===s.id))draw(n,f);ctx.restore();return}}
   for(const n of nodes.filter(n=>!n.sceneId))draw(n,f);
  },
  motionReceipt(){return [...(window.CourseMotion?CourseMotion.calls:[]),...transformCalls]},
  frameKey(seconds){return 'frame-'+Math.round(seconds*doc.fps)}
 };
 window.ready=true;
})();
