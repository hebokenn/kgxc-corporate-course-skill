/* Editable workbench bindings for the existing TY / DG / UI / CAM / MO libraries. */
(()=>{
 const C=window.CourseMotion={};
 C.ease=(name,u)=>{if(name==='linear'||u<=0||u>=1)return u;const fn=MO[name||'smooth'];if(!fn)throw Error('未知缓动 '+name);return fn(u)};
 const progress=(e,f)=>U.clamp((f-e.startFrame)/(e.endFrame-e.startFrame));
 C.paint=(c,paint)=>{
  if(!paint||typeof paint==='string')return paint;
  let g;if(paint.type==='linear-gradient')g=c.createLinearGradient(...paint.from,...paint.to);
  else if(paint.type==='radial-gradient')g=c.createRadialGradient(...paint.inner,...paint.outer);
  else throw Error('未实现的填色 '+paint.type);
  for(const [at,color]of paint.stops)g.addColorStop(at,color);return g;
 };
 C.background=(c,g,frame,fps)=>{
  if(g.background?.type==='mesh-gradient'){UI.mesh(c,frame/fps,{...g.background,key:'course-background'});return true}
  if(typeof g.background==='object'){c.fillStyle=C.paint(c,g.background);c.fillRect(0,0,1920,1080);return true}return false;
 };
 C.camera=(c,camera)=>{if(camera)CAM.apply(c,{x:camera.x??960,y:camera.y??540,z:camera.zoom??1,r:(camera.rotation||0)*Math.PI/180})};
 C.clipRect=(c,box)=>{c.beginPath();c.rect(...box);c.clip();C.onReadingClip?.(c,box)};
 C.before=(c,n,f)=>{
  for(const e of n.effects||[]){const p=progress(e,f),w=n.width??100,h=n.height??100;
   if(e.type==='mask-reveal'){const box=e.direction==='left'?[w*(1-p),0,w*p,h]:e.direction==='up'?[0,h*(1-p),w,h*p]:e.direction==='down'?[0,0,w,h*p]:[0,0,w*p,h];C.clipRect(c,box)}
   if(e.type==='marker')TY.marker(c,0,0,w,h,p,e.color||'#ffe14d',e.skew??.18);
  }
 };
 C.after=(c,n,f)=>{for(const e of n.effects||[])if(e.type==='underline')TY.underline(c,0,n.height??(n.fontSize||48)*1.2,n.width??100,progress(e,f),e.color||n.fill||'#23463c',e.lineWidth??5)};
 C.text=(c,n,f,fps)=>{
  const e=(n.effects||[]).find(e=>['chars-in','text-rise','blur-in','typewriter'].includes(e.type));if(!e)return false;
  const p=progress(e,f);if(p<=0)return true;
  const size=n.fontSize||48,lines=String(n.text||'').split('\n');
  // Convert the Canvas top baseline to the libraries' alphabetic baseline.
  // Measuring ascent while baseline is still "top" alone shifts titles upwards.
  const top=c.measureText('国Hg').actualBoundingBoxAscent;
  c.textBaseline='alphabetic';const ascent=c.measureText('国Hg').actualBoundingBoxAscent-top;
  lines.forEach((line,i)=>{const y=ascent+i*(n.lineHeight||1.4)*size;c.textBaseline='alphabetic';
   if(e.type==='chars-in'){const span=(e.endFrame-e.startFrame)/fps,stagger=Math.min(e.stagger??.04,span/Math.max(1,[...line].length)),dur=Math.max(1/fps,span-stagger*Math.max(0,[...line].length-1));TY.charsIn(c,line,0,y,(f-e.startFrame)/fps,{font:`${size}px ${n.fontFamily||'CourseHan'}`,color:c.fillStyle,align:n.align||'left',dur,stagger,dy:e.dy??24,scale0:e.scale0??1})}
   else if(e.type==='text-rise')TY.rise(c,line,0,y,p,{size,fam:n.fontFamily||'CourseHan',color:c.fillStyle,align:n.align||'left'});
   else if(e.type==='blur-in')TY.blurIn(c,line,0,y,p,{blur:e.blur??18,dy:e.dy??28});
   else c.fillText(TY.typed(line,p),0,y);
  });return true;
 };
 C.path=(c,n,f)=>{
  const e=(n.effects||[]).find(e=>e.type==='draw-on');if(!e)return false;
  const cum=DG.cum(n.points);DG.drawPartial(c,n.points,cum,cum.at(-1)*MO.smooth(progress(e,f)));return true;
 };
})();
