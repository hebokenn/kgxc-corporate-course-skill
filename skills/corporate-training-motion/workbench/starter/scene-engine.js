/* Editable scene composition: no course-specific layout or WORLD dependency. */
(()=>{
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');let doc,images={},nodes=[],activeScene;
 const clamp=x=>Math.max(0,Math.min(1,x));
 function state(node,frame){const n={...node};for(const a of node.motion||[]){let u=clamp((frame-a.startFrame)/Math.max(1,a.endFrame-a.startFrame));if(a.ease!=='linear')u=u*u*(3-2*u);n[a.property]=a.from+(a.to-a.from)*u}return n}
 function draw(n,frame){if(n.sceneId&&n.sceneId!==activeScene)return;if(frame<(n.startFrame??0)||frame>=(n.endFrame??doc.sourceDurationFrames))return;
  n=state(n,frame);ctx.save();ctx.translate((n.x||0)+(n.editDx||0),(n.y||0)+(n.editDy||0));ctx.rotate((n.rotation||0)*Math.PI/180);ctx.scale(n.scaleX??1,n.scaleY??1);ctx.globalAlpha*=n.opacity??1;ctx.fillStyle=n.fill||'#23463c';ctx.strokeStyle=n.stroke||'#547c70';ctx.lineWidth=n.lineWidth||3;
  const w=n.width||100,h=n.height||100;
  if(n.type==='rect'){ctx.beginPath();ctx.roundRect(0,0,w,h,n.radius||0);if(n.fill!==null)ctx.fill();if(n.stroke)ctx.stroke()}
  if(n.type==='ellipse'){ctx.beginPath();ctx.ellipse(0,0,w/2,h/2,0,0,Math.PI*2);if(n.fill!==null)ctx.fill();if(n.stroke)ctx.stroke()}
  if(n.type==='line'){ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(n.x2||w,n.y2||h);ctx.stroke()}
  if(n.type==='path'){const p=new Path2D(n.path);if(n.fill!==null)ctx.fill(p);if(n.stroke)ctx.stroke(p)}
  if(n.type==='text'){ctx.font=`${n.fontSize||48}px CourseHan`;ctx.textBaseline='top';ctx.textAlign=n.align||'left';String(n.text||'').split('\n').forEach((line,i)=>ctx.fillText(line,0,i*(n.lineHeight||1.4)*(n.fontSize||48)))}
  if(n.type==='image'){const im=images[n.assetId];if(!im)throw Error('未绑定图片 '+n.assetId);if(n.fit==='cover'){const scale=Math.max(w/im.width,h/im.height),sw=w/scale,sh=h/scale;ctx.drawImage(im,(im.width-sw)/2,(im.height-sh)/2,sw,sh,0,0,w,h)}else{const scale=Math.min(w/im.width,h/im.height),iw=im.width*scale,ih=im.height*scale;ctx.drawImage(im,(w-iw)/2,(h-ih)/2,iw,ih)}}
  for(const child of n.children||[])draw(child,frame);ctx.restore();
 }
 function walk(items,fn){for(const n of items){fn(n);walk(n.children||[],fn)}}
 window.courseWorkbench={version:1,
  async apply(value){doc=structuredClone(value);nodes=doc.sceneGraph?.nodes||[];images={};const byId=new Map();walk(nodes,n=>byId.set(n.id,n));const fields=[];
   for(const f of doc.fields){const node=byId.get(f.objectId);if(!node)throw Error('未绑定画面字段 '+f.id);if(f.property==='text')node.text=f.text;node.editDx=(node.editDx||0)+f.dx;node.editDy=(node.editDy||0)+f.dy;fields.push(f.id)}
   for(const a of doc.assets){const im=new Image();im.src='/project/'+a.path;await im.decode();images[a.id]=im}
   await document.fonts.load('42px CourseHan');await document.fonts.ready;
   return {fields,assets:doc.assets.map(a=>a.id)};
  },
  async seek(seconds){const f=Math.round(seconds*doc.fps);activeScene=doc.scenes.find(s=>s.sourceStartFrame<=f&&f<s.sourceEndFrame)?.id;ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.clearRect(0,0,1920,1080);ctx.fillStyle=doc.sceneGraph?.background||'#f3f2ec';ctx.fillRect(0,0,1920,1080);
   if(doc.status==='draft'&&!nodes.length){ctx.fillStyle='#718278';ctx.font='42px CourseHan';ctx.fillText('课程工程已建立  等待内容与配音',220,480)}
   for(const s of doc.scenes){if(s.sourceStartFrame<=f&&f<s.sourceEndFrame){ctx.save();for(const n of nodes.filter(n=>!n.sceneId||n.sceneId===s.id))draw(n,f);ctx.restore();return}}
   for(const n of nodes.filter(n=>!n.sceneId))draw(n,f);
  },
  frameKey(seconds){return 'frame-'+Math.round(seconds*doc.fps)}
 };
 window.ready=true;
})();
