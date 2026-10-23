/* Pure absolute-time actions used by previews, the gallery and full-course export.
 * Children stay ordinary editable nodes; no screenshots or private course data. */
(()=>{
 const C=window.CourseMotion,clamp=x=>Math.max(0,Math.min(1,x)),mix=(a,b,p)=>a+(b-a)*p;
 const raw=(e,f)=>clamp((f-e.startFrame)/(e.endFrame-e.startFrame)),pof=(e,f)=>MO.smooth(raw(e,f));
 const baseBefore=C.before,baseText=C.text,basePath=C.path;
 const baseKinds=['chars-in','text-rise','blur-in','typewriter','draw-on','mask-reveal','marker','underline'];
 const registry=C.actions={};let meshes=new Map();
 const register=(id,stage,fn)=>{if(registry[id])throw Error('重复动效 '+id);registry[id]={stage,fn}};
 const length=pts=>DG.cum(pts),point=(pts,p)=>{const d=length(pts);return DG.pointAt(pts,d,d.at(-1)*clamp(p))};
 const trace=(n,e,f)=>{C.calls.push({nodeId:n.id,type:e.type,frame:f,startFrame:e.startFrame,endFrame:e.endFrame,progress:raw(e,f),role:n.role||'subject',moduleId:n.moduleId||null})};
 C.beginFrame=f=>{C.calls=[];C.currentFrame=f};
 C.before=(c,n,f)=>{
  for(const e of n.effects||[]){if(!baseKinds.includes(e.type)&&!registry[e.type])throw Error('未实现动效 '+e.type);trace(n,e,f)}
  baseBefore(c,n,f);for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='before')a.fn(c,n,e,pof(e,f),raw(e,f),f)}
 };
 C.text=(c,n,f,fps)=>{for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='text'){a.fn(c,n,e,pof(e,f),raw(e,f),f);return true}}return baseText(c,n,f,fps)};
 C.path=(c,n,f)=>{if(typeof n.drawProgress==='number'){partial(c,n,n.drawProgress);return true}for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='path'){a.fn(c,n,e,pof(e,f),raw(e,f),f);return true}}return basePath(c,n,f)};
 C.shape=(c,n,f)=>{for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='shape'){a.fn(c,n,e,pof(e,f),raw(e,f),f);return true}}return false};
 C.image=(c,n,f,images)=>{for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='image'){a.fn(c,n,e,pof(e,f),raw(e,f),f,images);return true}}return false};
 C.children=(n,f)=>{let children=n.children||[];for(const e of n.effects||[]){const a=registry[e.type];if(a?.stage==='children')children=a.fn(children,n,e,pof(e,f),raw(e,f),f)}return children};
 const partial=(c,n,p,pts=n.points)=>{if(!pts||pts.length<2)throw Error('动效缺少路径 '+n.id);DG.drawPartial(c,pts,length(pts),length(pts).at(-1)*p)};
 const reveal=(child,q)=>({...child,opacity:(child.opacity??1)*clamp(q)});
 const ordered=(items,e,p,fn)=>items.map((n,i)=>fn(n,MO.smooth(clamp((p*(1+(items.length-1)*(e.stagger??.16))-i*(e.stagger??.16)))) ,i));
 const drawNumber=(c,n,text)=>{c.fillText(text,0,0)};
 register('assemble','children',(items,n,e,p)=>ordered(items,e,p,(o,q,i)=>({...reveal(o,q),x:(o.x||0)+(1-q)*(e.offsetX??(i%2?90:-90)),y:(o.y||0)+(1-q)*(e.offsetY??80)})));
 register('explode','children',(items,n,e,p)=>items.map((o,i)=>({...o,x:(o.x||0)+p*(o.explodeX??(i-(items.length-1)/2)*(e.dx??80)),y:(o.y||0)+p*(o.explodeY??-i*(e.dy??110))})));
 register('paper-fold','before',(c,n,e,p)=>{const a=(1-p)*Math.PI/2;c.transform(1,0,Math.sin(a)*(e.skew??.14),Math.max(.001,Math.cos(a)),0,0);c.globalAlpha*=Math.min(1,p*5);c.shadowColor='rgba(33,43,25,.16)';c.shadowBlur=12+24*(1-p);c.shadowOffsetY=10+16*(1-p)});
 register('scan','shape',(c,n,e,p,q)=>{if(q<=0||q>=1)return;const w=n.width||100,h=n.height||100,y=p*h;c.save();c.fillStyle=e.color||'#5ca3b0';c.globalAlpha*=.14;c.fillRect(0,y-18,w,36);c.globalAlpha*=7;c.fillRect(0,y-2,w,4);c.restore()});
 register('spotlight','shape',(c,n,e,p)=>{const w=n.width||1920,h=n.height||1080,x=mix(e.fromX??e.cx??w/2,e.cx??w/2,p),y=mix(e.fromY??e.cy??h/2,e.cy??h/2,p),r=mix(e.fromRadius??Math.max(w,h),e.radius??150,p);c.save();c.fillStyle=e.color||'rgba(17,35,34,.54)';c.beginPath();c.rect(0,0,w,h);c.arc(x,y,r,0,Math.PI*2,true);c.fill('evenodd');c.restore()});
 register('magnify','image',(c,n,e,p,q,f,images)=>{const im=images[n.assetId];if(!im)throw Error('放大镜素材未绑定');const w=n.width,h=n.height,z=mix(1,e.zoom??2.2,p),cx=(e.cx??.5)*im.width,cy=(e.cy??.5)*im.height,sw=im.width/z,sh=im.height/z;c.save();c.beginPath();c.roundRect(0,0,w,h,e.radius??20);c.clip();c.drawImage(im,cx-sw/2,cy-sh/2,sw,sh,0,0,w,h);c.restore()});
 register('path-follow','before',(c,n,e,p)=>{const a=point(e.points,p);c.translate(a[0]-e.points[0][0],a[1]-e.points[0][1]);if(e.orient&&p<1){const b=point(e.points,Math.min(1,p+.002));c.rotate(Math.atan2(b[1]-a[1],b[0]-a[0]))}});
 register('handoff','before',(c,n,e,p)=>{const w=n.width||100,h=n.height||100;c.translate((e.dx??500)*p,(e.dy??0)*p-Math.sin(p*Math.PI)*(e.lift??55));c.translate(w/2,h/2);c.rotate(Math.sin(p*Math.PI)*(e.tilt??.1));c.translate(-w/2,-h/2)});
 const targets=(items,e,p)=>ordered(items,e,p,(o,q,i)=>{const a=e.from?.[i]||[o.x||0,(o.y||0)+180],b=e.to?.[i]||[o.x||0,o.y||0];return {...o,x:mix(a[0],b[0],q),y:mix(a[1],b[1],q)}});
 register('sort','children',(items,n,e,p)=>targets(items,e,p));
 register('group-collect','children',(items,n,e,p)=>items.map((o,i)=>{const q=MO.smooth(clamp(p*(1+items.length*.09)-i*.09)),a=e.from[i],b=e.to[i];return {...o,x:mix(a[0],b[0],q),y:mix(a[1],b[1],q),scaleX:mix(1,e.scale??1,q),scaleY:mix(1,e.scale??1,q)}}));
 register('branch-grow','children',(items,n,e,p)=>ordered(items,e,p,(o,v)=>({...reveal(o,v),...(o.type==='path'?{drawProgress:v}:{})})));
 register('compare-wipe','before',(c,n,e,p)=>{c.beginPath();c.rect(0,0,(n.width||100)*p,n.height||100);c.clip();c.strokeStyle=e.color||'#ad7846';c.lineWidth=3;c.beginPath();c.moveTo((n.width||100)*p,0);c.lineTo((n.width||100)*p,n.height||100);c.stroke()});
 register('correct-replace','text',(c,n,e,p)=>{const h=(n.fontSize||48)*1.5;c.save();c.beginPath();c.rect(-4,-4,n.width||800,h);c.clip();c.fillText(e.fromText,0,-h*p);c.fillText(n.text,0,h*(1-p));c.restore()});
 register('count-up','text',(c,n,e,p)=>{const value=Number.parseFloat(String(n.text).replace(/,/g,''));if(!Number.isFinite(value))throw Error('累计终值须为数字 '+n.id);const k=e.decimals??0;drawNumber(c,n,mix(e.from??0,value,p).toFixed(k)+(e.suffix||''))});
 register('odometer','text',(c,n,e,p)=>{const target=String(n.text),size=n.fontSize||48,h=size*1.35;let x=0;c.save();c.beginPath();c.rect(0,-2,n.width||800,h);c.clip();for(const ch of target){const w=c.measureText(ch).width;if(/\d/.test(ch)){const digit=Number(ch),v=p*(10+digit),base=Math.floor(v);for(let j=0;j<2;j++)c.fillText(String((base+j)%10),x,(j-(v-base))*h)}else c.fillText(ch,x,0);x+=w}c.restore()});
 register('bar-grow','before',(c,n,e,p)=>{if(e.axis==='y'){c.translate(0,(n.height||100)*(1-p));c.scale(1,Math.max(.0001,p))}else c.scale(Math.max(.0001,p),1)});
 register('ring-progress','shape',(c,n,e,p)=>{c.beginPath();c.arc(0,0,(n.width||180)/2,-Math.PI/2,-Math.PI/2+Math.PI*2*p*(e.fraction??1));c.strokeStyle=e.color||n.stroke||'#327967';c.lineWidth=e.lineWidth??18;c.lineCap='round';c.stroke()});
 register('area-fill','shape',(c,n,e,p)=>{const w=n.width||100,h=n.height||100;c.save();c.beginPath();c.roundRect(0,0,w,h,n.radius||0);c.clip();c.globalAlpha*=.15;c.fillRect(0,0,w,h);c.globalAlpha*=1/.15;const v=h*p*(e.fraction??1);c.fillRect(0,h-v,w,v);c.restore()});
 register('record-filter','children',(items,n,e,p)=>items.map((o,i)=>{const keep=e.keep.includes(i),rank=e.keep.indexOf(i);return {...o,opacity:(o.opacity??1)*(keep?1:1-p),x:(o.x||0)+(keep?0:(e.exitX??150)*p),y:keep?mix(o.y||0,rank*(e.gap??100),p):o.y}}));
 register('dot-aggregate','children',(items,n,e,p)=>items.map((o,i)=>{const a=e.from?.[i]||[o.x||0,o.y||0],b=e.to?.[i]||[(i%(e.columns??10))*(e.gap??28),Math.floor(i/(e.columns??10))*(e.gap??28)];const q=MO.smooth(clamp(p*1.5-i/items.length*.5));return {...o,x:mix(a[0],b[0],q),y:mix(a[1],b[1],q)}}));
 register('timeline-reflow','children',(items,n,e,p)=>items.map((o,i)=>({...o,x:mix(o.x||0,e.to[i][0],p),width:mix(o.width||100,e.to[i][1],p)})));
 register('route-progress','path',(c,n,e,p)=>{c.save();c.globalAlpha*=.22;partial(c,n,1);c.restore();partial(c,n,p);if(e.marker!==false&&p>0&&(p<1||e.retainMarker===true)){const a=point(n.points,p);c.beginPath();c.arc(...a,e.radius??8,0,Math.PI*2);c.fillStyle=e.color||n.stroke;c.fill()}});
 register('dialogue','before',(c,n,e,p)=>{c.globalAlpha*=p;c.translate(0,(1-p)*32);const w=n.width||500,h=n.height||160;c.fillStyle=n.fill||'#fff';c.beginPath();if(e.side==='right'){c.moveTo(w-65,h-3);c.lineTo(w-20,h+28);c.lineTo(w-30,h-3)}else{c.moveTo(25,h-3);c.lineTo(14,h+28);c.lineTo(70,h-3)}c.closePath();c.fill()});
 register('quiz-feedback','children',(items,n,e,p)=>items.map((o,i)=>({...o,opacity:(o.opacity??1)*(i===e.selected?1:.3+.7*(1-p)),fill:i===e.selected&&p>.5?(e.correct?'#d8ecdd':'#f2dace'):o.fill,editDy:(o.editDy||0)+(i===e.selected?-8*Math.sin(p*Math.PI):0)})));
 for(const kind of ['check-draw','cross-draw','brace-draw'])register(kind,'path',(c,n,e,p)=>partial(c,n,p));
 register('callout','children',(items,n,e,p)=>items.map((o,i)=>reveal(o,items[0]?.type==='path'&&i?clamp((p-.5)*2):p)));
 register('flow-token','path',(c,n,e,p)=>{c.save();c.globalAlpha*=.35;partial(c,n,1);c.restore();if(e.marker!==false&&p>0&&(p<1||e.retainMarker===true)){const a=point(n.points,p);c.fillStyle=e.color||n.stroke;c.beginPath();c.arc(...a,e.radius??13,0,Math.PI*2);c.fill()}});
 register('presenter-gesture','image',(c,n,e,p,q,f,images)=>{const key=[n.assetId,e.kgAsset,e.openAsset,e.blinkAsset].join('|');let mesh=meshes.get(key);if(!mesh){if(typeof createM1Mesh!=='function')throw Error('品牌人物网格未接入');mesh=createM1Mesh(()=>({lift:0,upper:0,tilt:0,nod:0,breath:0,aperture:0,rounding:0,blink:0}));for(const id of [n.assetId,e.kgAsset,e.openAsset,e.blinkAsset])if(!images[id])throw Error('品牌人物缺少真实素材 '+id);mesh.init(images[n.assetId],images[e.kgAsset],images[e.openAsset],images[e.blinkAsset]);meshes.set(key,mesh)}mesh.poseAt=()=>({lift:Math.sin(p*Math.PI),upper:Math.sin(p*Math.PI),tilt:0,nod:0,breath:0,aperture:0,rounding:0,blink:Math.max(0,1-Math.abs(q-.65)/.035)});const im=mesh.draw(q*6);c.drawImage(im,0,0,n.width,n.height)});
 register('pixel-walk','before',(c,n,e,p)=>{const steps=e.steps??18;c.translate(Math.round(p*steps)/steps*(e.dx??650),Math.round(Math.sin(p*Math.PI*steps)*2)*(e.pixelSize??4))});
 register('split-merge','children',(items,n,e,p)=>{const v=Math.sin(p*Math.PI);return items.map((o,i)=>({...o,x:(o.x||0)+v*(i-(items.length-1)/2)*(e.distance??180)}))});
 register('balance','children',(items,n,e,p)=>items.map((o,i)=>{const h=(e.values[i]/Math.max(...e.values))*(e.height??400)*p;return {...o,y:(e.baseline??400)-h,height:h}}));
 register('rotate-inspect','before',(c,n,e,p)=>{const w=n.width||400,h=n.height||300;c.translate(w/2,h/2);c.rotate((e.angle??Math.PI/7)*Math.sin(p*Math.PI));c.scale(Math.max(.18,Math.abs(Math.cos(p*Math.PI*(e.turns??1)))),1);c.translate(-w/2,-h/2)});
 register('gauge-sweep','before',(c,n,e,p)=>{c.rotate(mix(e.fromAngle??-1.2,e.toAngle??1.1,p))});
 register('threshold-cross','shape',(c,n,e,p)=>{const w=n.width||500,h=n.height||60,v=p*(e.value??1),threshold=e.threshold??.65;c.save();c.fillStyle=v>=threshold?(e.afterColor||'#b84e43'):(n.fill||'#327967');c.fillRect(0,0,w*v,h);c.strokeStyle=e.color||'#ab773e';c.lineWidth=4;c.beginPath();c.moveTo(w*threshold,-15);c.lineTo(w*threshold,h+15);c.stroke();c.restore()});
 register('venn-intersect','children',(items,n,e,p)=>items.map((o,i)=>({...o,x:(o.x||0)+(i===0?1:-1)*p*(e.distance??120),opacity:i>1?p:(o.opacity??1)})));
 register('swimlane-transfer','before',(c,n,e,p)=>{const split=e.split??.5;if(p<split)c.translate(0,(e.dy??180)*p/split);else c.translate((e.dx??600)*(p-split)/(1-split),e.dy??180)});
 register('parallel-sync','children',(items,n,e,p)=>items.map((o,i)=>{const q=clamp((p-(e.delays?.[i]??i*.12))/(1-(e.delays?.[i]??i*.12)));return {...o,x:mix(o.x||0,e.to?.[i]?.[0]??500,q),y:mix(o.y||0,e.to?.[i]?.[1]??200,q)}}));
 register('evidence-attach','children',(items,n,e,p)=>ordered(items,e,p,(o,q,i)=>({...o,x:(o.x||0)+(1-q)*(e.dx??-160),opacity:(o.opacity??1)*q})));
 C.runtimeCatalog=()=>[...baseKinds,...Object.keys(registry)].sort();
 C.resetAssets=()=>{meshes=new Map()};
})();
