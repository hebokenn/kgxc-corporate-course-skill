/* Source-registered 2D performance. Facial animation is drawn at runtime; master art stays intact. */
(()=>{
 const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),smooth=v=>v*v*(3-2*v),mix=(a,b,u)=>a+(b-a)*u;
 const defaults={head:0,nod:0,left:0,right:0,leftFore:0,fore:0,leftHand:0,hand:0,gazeX:0,gazeY:0,concern:0,relief:0,blink:0};
 const imageCache=new WeakMap();
 function sample(keys,frame){
  let previous={frame:0,values:{...defaults}};if(!keys?.length)return previous.values;
  const merged=keys.map(k=>{previous={frame:k.frame,values:{...previous.values,...k.values}};return previous});
  if(frame<=merged[0].frame)return{...merged[0].values};
  for(let i=1;i<merged.length;i++)if(frame<=merged[i].frame){const a=merged[i-1],b=merged[i],u=smooth(clamp((frame-a.frame)/(b.frame-a.frame))),out={};for(const k of Object.keys(defaults))out[k]=mix(a.values[k],b.values[k],u);return out}
  return{...merged.at(-1).values};
 }
 function state(spec,frame){const s=sample(spec.keys,frame);for(const [a,m,z]of spec.blinks||[]){const v=frame<m?smooth(clamp((frame-a)/(m-a))):1-smooth(clamp((frame-m)/(z-m)));if(frame>=a&&frame<=z)s.blink=Math.max(s.blink,v)}return s}
 function registered(im,p){let cache=imageCache.get(im);if(!cache){cache=new Map();imageCache.set(im,cache)}const key=JSON.stringify([p.size,p.sourceCrop,p.face]);if(cache.has(key))return cache.get(key);
  const v=document.createElement('canvas');[v.width,v.height]=p.size;const g=v.getContext('2d',{willReadFrequently:true});if(p.sourceCrop){const [x,y,w,h]=p.sourceCrop;g.drawImage(im,x*im.width,y*im.height,w*im.width,h*im.height,0,0,v.width,v.height)}else g.drawImage(im,0,0,v.width,v.height);
  const color=(x,y)=>{const a=g.getImageData(Math.round(x),Math.round(y),1,1).data;return `rgb(${a[0]},${a[1]},${a[2]})`};
  const data={image:v,color};cache.set(key,data);return data;
 }
 const path=(c,ps)=>{c.beginPath();ps.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath()};
 function texture(c,im,ps){c.save();path(c,ps);c.clip();c.drawImage(im,0,0);c.restore()}
 function joint(c,im,x,y,r){c.save();c.beginPath();c.arc(x,y,r,0,2*Math.PI);c.clip();c.drawImage(im,0,0);c.restore()}
 function around(c,pt,angle,fn){c.save();c.translate(...pt);c.rotate(angle*Math.PI/180);c.translate(-pt[0],-pt[1]);fn();c.restore()}
 function skin(c,source,feature){const {x,y,rx,ry}=feature;const color=source.color(feature.skin?.[0]??x,feature.skin?.[1]??(y+ry+9));c.save();c.fillStyle=color;c.beginPath();c.ellipse(x,y,rx,ry,0,0,2*Math.PI);c.fill();c.restore()}
 function triangle(c,im,src,dst){
  const [p0,p1,p2]=src,[q0,q1,q2]=dst,det=(p1[0]-p0[0])*(p2[1]-p0[1])-(p2[0]-p0[0])*(p1[1]-p0[1]);
  const a=((q1[0]-q0[0])*(p2[1]-p0[1])-(q2[0]-q0[0])*(p1[1]-p0[1]))/det,b=((q1[1]-q0[1])*(p2[1]-p0[1])-(q2[1]-q0[1])*(p1[1]-p0[1]))/det;
  const d=((p1[0]-p0[0])*(q2[1]-q0[1])-(p2[0]-p0[0])*(q1[1]-q0[1]))/det,cc=((p1[0]-p0[0])*(q2[0]-q0[0])-(p2[0]-p0[0])*(q1[0]-q0[0]))/det;
  c.save();const center=[(q0[0]+q1[0]+q2[0])/3,(q0[1]+q1[1]+q2[1])/3];path(c,dst.map(p=>[p[0]+Math.sign(p[0]-center[0])*.18,p[1]+Math.sign(p[1]-center[1])*.18]));c.clip();c.transform(a,b,cc,d,q0[0]-a*p0[0]-cc*p0[1],q0[1]-b*p0[0]-d*p0[1]);c.drawImage(im,0,0);c.restore();
 }
 function deform(c,im,x,y,rx,ry,field){
  const cols=8,rows=8,points=[];for(let j=0;j<=rows;j++){const row=[];for(let i=0;i<=cols;i++){const u=-1+2*i/cols,v=-1+2*j/rows,source=[x+u*rx,y+v*ry],w=(1-u*u)*(1-v*v),delta=field(u,v,w);row.push({source,dest:[source[0]+delta[0],source[1]+delta[1]]})}points.push(row)}
  for(let j=0;j<rows;j++)for(let i=0;i<cols;i++){const a=points[j][i],b=points[j][i+1],d=points[j+1][i],e=points[j+1][i+1];triangle(c,im,[a.source,b.source,e.source],[a.dest,b.dest,e.dest]);triangle(c,im,[a.source,e.source,d.source],[a.dest,e.dest,d.dest])}
 }
 function face(c,source,p,s){
  const f=p.face,im=source.image;if(!f)return;
  skin(c,source,f.mouth.erase);
  const [mx,my,mw]=f.mouth.line,emotion=clamp(s.concern),relief=clamp(s.relief),bend=mix(1,-4,emotion)+relief*6;
  c.save();c.strokeStyle=f.mouth.stroke||'#875340';c.lineWidth=f.mouth.width||2.6;c.lineCap='round';c.beginPath();c.moveTo(mx-mw/2,my);c.quadraticCurveTo(mx,my+bend*2,mx+mw/2,my);c.stroke();c.restore();
  for(let i=0;i<f.brows.length;i++){const b=f.brows[i],inner=i===0?1:-1;deform(c,im,...b.center,b.rx+4,b.ry+4,(u,v,w)=>[0,-emotion*(3.5+inner*u*3)*w+relief*.7*w])}
  for(const e of f.eyes){const [x,y,rx,ry]=e.region;deform(c,im,x,y,rx,ry,(u,v,w)=>[clamp(s.gazeX,-1,1)*e.travel[0]*w,clamp(s.gazeY,-1,1)*e.travel[1]*w-v*ry*.98*clamp(s.blink)*Math.pow(1-u*u,.35)*Math.pow(1-v*v,.3)])}
 }
 function paint(c,im,p,spec,frame){
  const s=state(spec,frame),source=registered(im,p),original=source.image;
  const visibility={},viewport=spec.viewport||[0,0,1920,1080];
  const region=(name,ps)=>{const m=c.getTransform(),pts=ps.map(([x,y])=>[m.a*x+m.c*y+m.e,m.b*x+m.d*y+m.f]),xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),box=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)],area=Math.max(1,(box[2]-box[0])*(box[3]-box[1])),visible=Math.max(0,Math.min(box[2],viewport[0]+viewport[2])-Math.max(box[0],viewport[0]))*Math.max(0,Math.min(box[3],viewport[1]+viewport[3])-Math.max(box[1],viewport[1]));visibility[name]={fraction:clamp(visible/area),bounds:box}};
  texture(c,original,p.body);for(const ps of p.underlayPolygons||[])texture(c,original,ps);
  for(const side of ['left','right']){
   const a=p[side],up=side==='left'?s.left:s.right,fore=side==='left'?s.leftFore:s.fore,hand=side==='left'?s.leftHand:s.hand;
   joint(c,original,...a.S,p.jointRadius?.shoulder??20);
   around(c,a.S,up,()=>{texture(c,original,a.upper);around(c,a.E,fore,()=>{joint(c,original,...a.E,p.jointRadius?.elbow??22);texture(c,original,a.fore);around(c,a.W,hand,()=>{region(side+'Hand',a.hand);texture(c,original,a.hand)})})});
  }
  for(const ps of p.staticArmPolygons||[])texture(c,original,ps);
  around(c,p.neck,s.head,()=>{c.save();c.translate(...p.neck);c.scale(1,1-.028*clamp(s.nod));c.translate(-p.neck[0],-p.neck[1]+3*clamp(s.nod));region('face',p.face.eyes.flatMap(e=>{const[x,y,rx,ry]=e.region;return[[x-rx,y-ry-22],[x+rx,y+ry+65]]}));texture(c,original,p.head);c.save();path(c,p.head);c.clip();face(c,source,p,s);c.restore();c.restore()});
  const target=(spec.targets||[]).filter(x=>x.frame<=frame).at(-1)?.id||null;
  return{...s,visibility,gazeTarget:target,identity:p.identity,sourceSize:p.size,scope:'calibrated frontal source-texture performance; no natural walk, profile turn, contact or phoneme lip sync'};
 }
 window.CoursePerformance={paint,state,sample,defaults};
})();
