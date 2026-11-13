/* Reusable 2D acting: solid depth layers, supported steps and coordinated heading.
 * Appearance and choreography are authored for each course; no course dialogue or media. */
(()=>{
 const C=v=>Math.max(0,Math.min(1,v)),mix=(a,b,u)=>a+(b-a)*u,S=u=>{u=C(u);return u*u*(3-2*u)},tau=Math.PI*2;
 let registry=new Map(),cache=new Map(),drawAudit=null;
 const defaults={gesture:0,concern:0,relief:.1,nod:0,head:0,turn:0,write:0,reach:0,tryEar:0,shrug:0,yield:0,scribble:0,gazeDown:0};
 function sample(keys,frame){const out={},first=keys?.[0]?.frame||0;for(const key of Object.keys(defaults)){let previous={frame:first,value:defaults[key]},next=null;for(const item of keys||[]){if(!Object.prototype.hasOwnProperty.call(item.values,key))continue;if(item.frame<=frame)previous={frame:item.frame,value:item.values[key]};else{next={frame:item.frame,value:item.values[key]};break}}out[key]=next?mix(previous.value,next.value,S((frame-previous.frame)/(next.frame-previous.frame))):previous.value}return out}

 function progress(t){const r=.12;if(t<=0)return 0;if(t>=1)return 1;const den=1-r;if(t<r)return t*t/(2*r*den);if(t>1-r)return 1-(1-t)*(1-t)/(2*r*den);return (t-r/2)/den}
 function rootAt(w,f){return mix(w.fromX,w.toX,progress((f-w.startFrame)/(w.endFrame-w.startFrame)))}
 function heading(keys,f){if(!keys?.length)return 0;let a=keys[0];for(const b of keys){if(b.frame<=f){a=b;continue}return mix(a.yaw,b.yaw,S((f-a.frame)/(b.frame-a.frame)))}return a.yaw}
 function gait(n,f){
  const a=n.vectorActor,scale=n.scaleX||1,walks=a.walks||[];
  let x=n.x||0,floor=n.y||880,dir=Math.sign((walks[0]?.toX||x+1)-(walks[0]?.fromX||x))||1,phase=0,weight=0;
  const flat=(px,yaw)=>({x:px,y:floor,lift:0,stance:true,angle:0,pivot:0,yaw,stage:'flat'});
  let feet=[x-18*scale,x+18*scale].map(px=>flat(px,dir)),turning=false;
  for(const w of walks){
   const nextDir=Math.sign(w.toX-w.fromX)||dir,total=w.endFrame-w.startFrame,N=w.steps,dt=total/N;
   if(f<w.startFrame){
    // Turn each planted shoe through a front view before travel begins. No instantaneous flip.
    if(!a.facing?.length&&nextDir!==dir&&f>=w.startFrame-10){
     const turn=C((f-(w.startFrame-10))/10);turning=true;
     feet=feet.map((foot,i)=>({...foot,yaw:mix(dir,nextDir,S(C((turn-(i?.18:0))/.82))),stage:'pivot'}));
    }
    break;
   }
   dir=nextDir;
   const initial=[w.fromX-18*scale,w.fromX+18*scale],positions=initial.slice(),targets=[];
   const lead=Math.min(27,Math.abs(w.toX-w.fromX)/scale/N*.43)*scale,first=dir>0?0:1;
   for(let i=0;i<N;i++){
    const leg=(first+i)%2,start=w.startFrame+i*dt,end=start+dt,land=start+dt*.88;
    const target=i>=N-2?w.toX+(leg?18:-18)*scale:rootAt(w,land)+dir*lead+(leg?4:-4)*scale;
    targets.push({leg,start,end,land,from:positions[leg],to:target});positions[leg]=target;
   }
   if(f>=w.endFrame){x=w.toX;feet=positions.map(px=>flat(px,dir));continue}
   x=rootAt(w,f);weight=Math.min(S((f-w.startFrame)/8),S((w.endFrame-f)/8));phase=(f-w.startFrame)/dt;
   feet=initial.map(px=>flat(px,dir));
   for(const st of targets){
    if(f>=st.end){feet[st.leg]=flat(st.to,dir);continue}
    if(f<st.start)break;
    const u=C((f-st.start)/dt);let foot;
    if(u<.10)foot={...flat(st.from,dir),angle:dir*.20*S(u/.10),pivot:dir*35,stage:'push'};
    else if(u<.88){
     const q=(u-.10)/.78,lift=Math.sin(Math.PI*q)*(11+Math.min(3,Math.abs(st.to-st.from)/scale*.025))*scale;
     foot={x:mix(st.from,st.to,S(q)),y:floor-lift,lift,stance:false,angle:dir*mix(.20,-.16,S(q)),pivot:dir*mix(35,-22,S(q)),yaw:dir,stage:'swing'};
    }else foot={...flat(st.to,dir),angle:-dir*.16*(1-S((u-.88)/.12)),pivot:-dir*22,stage:'heel'};
    feet[st.leg]=foot;break;
   }
   break;
  }
  const yaw=heading(a.facing,f+1),headYaw=heading(a.facing,f+2),hipYaw=heading(a.facing,f);
  if(a.facing?.length)feet=feet.map((foot,i)=>({...foot,yaw:Math.sin(heading(a.facing,f-(i?1:0)))}));
  let turnShift=0,turnDown=0;
  const pivot=(a.turns||[]).find(t=>t.startFrame<=f&&f<=t.endFrame);
  if(pivot){
   turning=true;const t=C((f-pivot.startFrame)/(pivot.endFrame-pivot.startFrame)),first=Math.sin(pivot.toYaw)>=0?1:0;
   feet=feet.map((foot,i)=>{const order=i===first?0:1,a0=order?.52:.12,z0=order?.83:.43,q=C((t-a0)/(z0-a0)),air=Math.sin(Math.PI*S(q)),moving=t>a0&&t<z0;
    if(moving){turnShift+=(i?-1:1)*air*3.5;turnDown+=air*.6}
    return {...foot,x:foot.x+(moving?Math.sign(pivot.toYaw)*air*3*scale:0),y:floor-air*6*scale,lift:air*6*scale,stance:!moving,angle:0,pivot:0,yaw:Math.sin(mix(pivot.fromYaw,pivot.toYaw,S(q))),stage:moving?'turn-step':'turn-support'};
   });
  }
  return {x,floor,feet,weight,dir,phase,turning,yaw,headYaw,hipYaw,turnShift,turnDown};
 }
 function footPoint(foot,p,x,y){const angle=foot.angle||0,pivot=foot.pivot||0,cs=Math.cos(angle),sn=Math.sin(angle);return[(foot.x-p.g.x)/p.scale+pivot+(x-pivot)*cs-y*sn,(foot.y-p.g.floor)/p.scale+(x-pivot)*sn+y*cs]}
 function ik(P,Q,L1,L2,side=1,phi=0){const dx=Q[0]-P[0],dy=Q[1]-P[1],d=Math.hypot(dx,dy),safe=Math.max(.001,d),along=(L1*L1-L2*L2+d*d)/(2*safe),height=Math.sqrt(Math.max(0,L1*L1-along*along)),ux=dx/safe,uy=dy/safe;const K=[P[0]+ux*along-uy*height*side*Math.cos(phi),P[1]+uy*along+ux*height*side*Math.cos(phi),height*Math.sin(phi)];const error=Math.max(0,d-L1-L2,Math.abs(L1-L2)-d);return {P,K,Q,error,boneError:Math.max(Math.abs(Math.hypot(K[0]-P[0],K[1]-P[1],K[2])-L1),Math.abs(Math.hypot(K[0]-Q[0],K[1]-Q[1],K[2])-L2))}}
 function pose(n,f){if(cache.has(n.id))return cache.get(n.id);const a=n.vectorActor,s=sample(a.keys,f),g=gait(n,f),scale=n.scaleX||1;let blink=0;for(const [b,m,z]of a.blinks||[]){if(b<=f&&f<=z)blink=Math.max(blink,f<m?S((f-b)/(m-b)):1-S((f-m)/(z-m)))}
  let mouth=0;for(const speech of a.speech||[]){const i=f-speech.startFrame;if(i>=0&&i<speech.envelope.length)mouth=Math.max(mouth,speech.envelope[i]||0)}
  const targetId=(a.targets||[]).filter(v=>v.frame<=f).at(-1)?.id||a.targetId,target=registry.get(targetId),targetX=target?(target.vectorActor?gait(target,f).x+(target.editDx||0):(target.x??g.x+300)+(target.editDx||0)):g.x+300;const look=g.weight>.001?g.dir:Math.sign(targetX-g.x)||1;
  const turn=s.turn||look*.45,lean=s.yield*-4+g.dir*g.weight*2.2,bodyYaw=g.yaw,headYaw=g.headYaw,hipYaw=g.hipYaw,front=Math.max(0,Math.cos(bodyYaw)),profile=Math.sin(bodyYaw);
  const reachLean=look*16*s.reach*Math.abs(profile),u=g.phase%1,down=1.4*Math.cos((u-.03)*tau),hipY=-135+g.weight*(2+down)+g.turnDown,hipX=lean*.4+reachLean*.6+g.turnShift;
  const legContext={g,scale};
  const legs=g.feet.map((foot,i)=>{const Q=footPoint(foot,legContext,0,-mix(10,14,g.weight)),P=[hipX+(i?1:-1)*18*Math.max(.10,Math.cos(hipYaw)),hipY],plane=mix(1.35,Math.PI-(foot.stance?1.42:1.05),g.weight);return ik(P,Q,68,70,1,Math.acos(Math.max(-1,Math.min(1,foot.yaw*Math.cos(plane)))))});
  const shoulderY=hipY-108,shoulderX=lean+g.dir*g.weight*5+reachLean+g.turnShift*.85,bodyWidth=(.45+.55*front)*(1-.04*g.weight),headV=Math.abs(Math.sin(headYaw)),headDir=Math.sign(headYaw)||look;
  const earX=shoulderX+turn*5*(1-headV)+headDir*mix(-43,-13,headV);
  const arms=[];
  for(let i=0;i<2;i++){
   const side=i?1:-1,active=i===(look>0?1:0),P=[shoulderX+side*43*front,shoulderY-3*s.shrug+side*profile*1.5];
   const talk=active?C(s.gesture/.8):0,shrug=C(s.shrug/.8);
   const held=Math.max(s.write,active?Math.max(s.reach,s.tryEar,talk):0),swingWeight=g.weight*(1-held),walkSwing=(i?-1:1)*.22*Math.cos(Math.PI*(g.phase-.09))*swingWeight,foreSwing=(i?-1:1)*.18*Math.cos(Math.PI*(g.phase-.15))*swingWeight;
   const upper=side*(mix(.11,.24,talk)+shrug*.16)*front+walkSwing+profile*.035,lower=side*(mix(.07,2.15,talk)+shrug*.92)*front+foreSwing+g.dir*swingWeight*.16+profile*.04;
   const K=[P[0]+Math.sin(upper)*56,P[1]+Math.cos(upper)*56,0],rest=[K[0]+Math.sin(lower)*62,K[1]+Math.cos(lower)*62];
   let Q=rest.slice();
   if(active){Q=Q.map((v,j)=>mix(v,[look*100,hipY-10][j],s.reach));Q=Q.map((v,j)=>mix(v,[earX+4,hipY-160][j],s.tryEar));Q[0]+=look*30*Math.sin(Math.PI*s.tryEar)}
   if(s.write>.001)Q=Q.map((v,j)=>mix(v,(i?[24+Math.sin(f*.37)*1.6*s.scribble+profile*24,hipY-35]:[-30+profile*24,hipY-34])[j],s.write));
   const task=Math.max(s.write,active?s.reach:0,active?s.tryEar:0);
   let arm;
   if(task<.000001)arm={P,K,Q,error:Math.max(0,Math.hypot(Q[0]-P[0],Q[1]-P[1])-118,6-Math.hypot(Q[0]-P[0],Q[1]-P[1])),boneError:Math.max(Math.abs(Math.hypot(K[0]-P[0],K[1]-P[1])-56),Math.abs(Math.hypot(Q[0]-K[0],Q[1]-K[1])-62))};
   else{const dx=Q[0]-P[0],dy=Q[1]-P[1],d=Math.max(.001,Math.hypot(dx,dy)),ux=dx/d,uy=dy/d,along=(56*56-62*62+d*d)/(2*d),base=[P[0]+ux*along,P[1]+uy*along],pole=[mix(K[0],P[0]+side*65,task),mix(K[1],P[1]+65,task)],lateral=(pole[0]-base[0])*(-uy)+(pole[1]-base[1])*ux;arm=ik(P,Q,56,62,1,Math.atan2(14*task,lateral))}
   arms.push({...arm,side,active});
  }
  const result={s,g,scale,hipY,hipX,shoulderX,shoulderY,bodyWidth,legs,arms,blink,mouth,turn,look,lean,bodyYaw,headYaw,hipYaw,front,profile,earX};cache.set(n.id,result);return result;
 }
 function auditPaint(c){if(drawAudit)drawAudit.minimumRelativeOpacity=Math.min(drawAudit.minimumRelativeOpacity,c.globalAlpha/(drawAudit.baseOpacity||1))}
 function path(c,d,fill,stroke='#29303a',width=2){auditPaint(c);c.beginPath();const p=typeof d==='string'?new Path2D(d):d;if(fill){c.fillStyle=fill;c.fill(p)}if(stroke){c.strokeStyle=stroke;c.lineWidth=width;c.lineJoin='round';c.lineCap='round';c.stroke(p)}}
 function ellipse(c,x,y,rx,ry,fill,stroke=null,w=1.6){auditPaint(c);c.beginPath();c.ellipse(x,y,rx,Math.max(.1,ry),0,0,tau);if(fill){c.fillStyle=fill;c.fill()}if(stroke){c.strokeStyle=stroke;c.lineWidth=w;c.stroke()}}
 function ribbon(c,P,Q,r1,r2,color,outline='#30333c'){const dx=Q[0]-P[0],dy=Q[1]-P[1],D=Math.max(.01,Math.hypot(dx,dy)),px=-dy/D,py=dx/D;path(c,`M ${P[0]+px*r1} ${P[1]+py*r1} L ${Q[0]+px*r2} ${Q[1]+py*r2} Q ${Q[0]+dx/D*r2} ${Q[1]+dy/D*r2} ${Q[0]-px*r2} ${Q[1]-py*r2} L ${P[0]-px*r1} ${P[1]-py*r1} Q ${P[0]-dx/D*r1} ${P[1]-dy/D*r1} ${P[0]+px*r1} ${P[1]+py*r1} Z`,color,outline,1.7)}
 function limb(c,b,r1,r2,r3,color){const P=b.P,K=b.K,Q=b.Q,da=[K[0]-P[0],K[1]-P[1]],db=[Q[0]-K[0],Q[1]-K[1]],la=Math.hypot(...da),lb=Math.hypot(...db),na=[-da[1]/la,da[0]/la],nb=[-db[1]/lb,db[0]/lb],nm=[(na[0]+nb[0])/2,(na[1]+nb[1])/2];path(c,`M ${P[0]+na[0]*r1} ${P[1]+na[1]*r1} L ${K[0]+na[0]*r2} ${K[1]+na[1]*r2} Q ${K[0]+nm[0]*r2} ${K[1]+nm[1]*r2} ${K[0]+nb[0]*r2} ${K[1]+nb[1]*r2} L ${Q[0]+nb[0]*r3} ${Q[1]+nb[1]*r3} Q ${Q[0]+db[0]/lb*r3} ${Q[1]+db[1]/lb*r3} ${Q[0]-nb[0]*r3} ${Q[1]-nb[1]*r3} L ${K[0]-nb[0]*r2} ${K[1]-nb[1]*r2} Q ${K[0]-nm[0]*r2} ${K[1]-nm[1]*r2} ${K[0]-na[0]*r2} ${K[1]-na[1]*r2} L ${P[0]-na[0]*r1} ${P[1]-na[1]*r1} Z`,color)}
 function garment(c,p,color){
  const X=v=>p.shoulderX+v*p.bodyWidth,y=p.hipY;
  const pieces=[new Path2D(`M ${X(-18)} ${y-130} Q ${X(-32)} ${y-125} ${X(-43)} ${y-117} Q ${X(-48)} ${y-110} ${X(-46)} ${y-95} L ${X(-42)} ${y-12} Q ${X(-40)} ${y+9} ${X(0)} ${y+10} Q ${X(40)} ${y+9} ${X(42)} ${y-12} L ${X(46)} ${y-95} Q ${X(48)} ${y-110} ${X(43)} ${y-117} Q ${X(32)} ${y-125} ${X(18)} ${y-130} Z`)];
  const cuffs=[];
  for(const arm of p.arms){const P=arm.P,E=[mix(P[0],arm.K[0],.48),mix(P[1],arm.K[1],.48)],dx=E[0]-P[0],dy=E[1]-P[1],d=Math.max(.1,Math.hypot(dx,dy)),nx=-dy/d,ny=dx/d,r1=14.5,r2=12.5;
   const side=arm.side,outer=[P[0]-side*nx*r1,P[1]-side*ny*r1],cuffOuter=[E[0]-side*nx*r2,E[1]-side*ny*r2],cuffInner=[E[0]+side*nx*r2,E[1]+side*ny*r2];pieces.push(new Path2D(`M ${X(side*26)} ${y-126} Q ${outer[0]-side*2} ${y-125} ${outer[0]} ${outer[1]} L ${cuffOuter[0]} ${cuffOuter[1]} Q ${E[0]+dx/d*2} ${E[1]+dy/d*2} ${cuffInner[0]} ${cuffInner[1]} L ${P[0]+side*nx*r1} ${P[1]+side*ny*r1} Z`));cuffs.push({E,nx,ny,r:r2});
  }
  c.save();c.lineWidth=3;c.lineJoin='round';c.lineCap='round';c.strokeStyle='#2d333c';for(const piece of pieces)c.stroke(piece);c.fillStyle=color;for(const piece of pieces)c.fill(piece);
  c.restore();
 }
 function skinArm(c,arm,skin,layer){
  const E=[mix(arm.P[0],arm.K[0],.48),mix(arm.P[1],arm.K[1],.48)];
  if(drawAudit)drawAudit.armLayers.push({side:arm.side,layer,relativeOpacity:c.globalAlpha/(drawAudit.baseOpacity||1)});
  // Union of capped tapered segments: a deep elbow fold cannot self-intersect into a spike.
  const segment=(P,Q,r1,r2)=>{const dx=Q[0]-P[0],dy=Q[1]-P[1],d=Math.max(.001,Math.hypot(dx,dy)),nx=-dy/d,ny=dx/d;return new Path2D(`M ${P[0]+nx*r1} ${P[1]+ny*r1} L ${Q[0]+nx*r2} ${Q[1]+ny*r2} Q ${Q[0]+dx/d*r2} ${Q[1]+dy/d*r2} ${Q[0]-nx*r2} ${Q[1]-ny*r2} L ${P[0]-nx*r1} ${P[1]-ny*r1} Z`)};
  const joint=new Path2D();joint.ellipse(arm.K[0],arm.K[1],9.5,9.5,0,0,tau);const pieces=[segment(E,arm.K,12.3,9.5),segment(arm.K,arm.Q,9.5,6),joint];
  auditPaint(c);c.save();c.lineWidth=1.7;c.lineJoin='round';c.lineCap='round';c.strokeStyle='#29303a';for(const shape of pieces)c.stroke(shape);c.fillStyle=skin;for(const shape of pieces)c.fill(shape);c.restore();
 }
 function shoe(c,foot,p){const x=(foot.x-p.g.x)/p.scale,y=(foot.y-p.g.floor)/p.scale,yaw=foot.yaw??p.g.dir,left=-18-13*C(-yaw),right=18+13*C(yaw),pivot=foot.pivot||0,collar=-yaw*3;
  c.save();c.translate(x+pivot,y);c.rotate(foot.angle||0);c.translate(-pivot,0);
  path(c,`M ${collar-11} -21 Q ${collar} -24 ${collar+11} -20 L ${right} -9 Q ${right+4} -7 ${right+4} -3 Q ${right+4} 0 ${right-2} 0 L ${left+2} 0 Q ${left-4} 0 ${left-4} -5 Q ${left-4} -9 ${left} -12 Z`,'#f5f3ec','#343740',1.7);
  path(c,`M ${left} -4 Q 0 -2 ${right+1} -4`,null,'#b4b6bb',1.8);path(c,`M ${collar-6} -14 L ${collar+7} -13 M ${collar-6} -10 L ${collar+7} -9`,null,'#959ba4',1.2);c.restore()}
 function palm(c,arm,p,skin){const Q=arm.Q;let angle=-Math.atan2(Q[0]-arm.K[0],Q[1]-arm.K[1]);const gesture=Math.max(arm.active?p.s.gesture:0,p.s.shrug*.8);angle=mix(angle,p.look>0?-1.15:1.15,gesture);c.save();c.translate(...Q);c.rotate(angle);
  if(arm.active&&(p.s.tryEar>.3||p.s.reach>.5)){path(c,'M -7 -3 Q -9 -13 -3 -15 Q 3 -17 6 -8 Q 11 -12 14 -7 L 8 6 Q 1 12 -7 5 Z',skin);path(c,'M -1 -6 Q 4 -3 8 -2',null,'#b97c61',1.2)}
  else if(gesture>.3){path(c,'M -7 2 L -8 -8 Q -7 -14 -3 -10 L 0 -3 L 1 -15 Q 3 -19 5 -14 L 6 -3 L 10 -11 Q 13 -15 15 -10 L 14 0 L 18 -5 Q 22 -5 20 1 L 14 12 Q 4 19 -5 11 Z',skin);path(c,'M -3 5 Q 5 2 12 5',null,'#b97c61',1.2)}
  else{path(c,'M -6 -2 Q 0 -5 6 -2 L 8 6 Q 9 12 4 15 Q 0 18 -5 14 L -8 7 Q -11 5 -9 1 Q -8 -2 -6 -2 Z',skin);path(c,'M -5 4 Q -1 3 -1 8 M 1 10 L 2 13',null,'#b97c61',1.1)}c.restore();
 }
 function airpod(c,x,y){c.save();c.translate(x,y);path(c,'M -8 -20 C -13 -30 9 -34 13 -23 C 17 -15 8 -10 3 -13 L 6 4 Q 3 9 -1 5 L -3 -12 Q -9 -14 -8 -20 Z','#fbfcfa','#71838c',1.05);ellipse(c,-4,-22,3.8,2,'#293943');ellipse(c,9,-23,1.3,2.4,'#344650');c.restore()}
 function prop(c,n,p,f,hidden){const a=n.vectorActor,active=p.arms[p.look>0?1:0];for(const prop of a.props||[]){if(f<prop.startFrame||f>=prop.endFrame||hidden?.has(prop.id))continue;let Q=active.Q;
   if(prop.kind==='airpod')airpod(c,...Q);
   if(prop.kind==='clipboard'){Q=p.arms[0].Q;c.save();c.translate(Q[0]-22,Q[1]-8);path(c,'M 0 0 L 70 0 L 70 67 L 0 67 Z','#e8d8bd','#6a6158',1.5);path(c,'M 5 6 L 65 6 L 65 61 L 5 61 Z','#fffdf7',null);path(c,'M 24 -3 L 46 -3 L 46 8 L 24 8 Z','#89939b',null);for(let i=0;i<4;i++)path(c,`M 13 ${20+i*9} L ${44+(i%2)*12} ${20+i*9}`,null,'#a8b1b5',1.5);c.restore();if(p.s.write>.2){const W=p.arms[1].Q;path(c,`M ${W[0]+2} ${W[1]-7} L ${W[0]-11} ${W[1]+10}`,null,'#d6a64e',3);path(c,`M ${W[0]-11} ${W[1]+10} L ${W[0]-14} ${W[1]+14}`,null,'#4b4b52',1.5)}}
   if(prop.kind==='case'){c.save();c.translate(Q[0]-16,Q[1]-42);c.rotate(.12);path(c,'M 0 0 Q 0 -7 7 -7 L 37 -7 Q 44 -7 44 0 L 44 68 Q 44 75 37 75 L 7 75 Q 0 75 0 68 Z','#b6bfd0','#50596b',1.5);path(c,'M 6 -1 L 38 -1 L 38 14 L 6 14 Z','#f8f4ec','#50596b',1.2);c.restore()}
  }}
 function head(c,a,p){
  const skin=a.skin||'#efb38f',hair=a.hairColor||'#40332f',yaw=p.headYaw,v=Math.abs(Math.sin(yaw)),dir=Math.sign(yaw)||1,turn=p.turn*(1-v),angle=p.s.head*.025+p.s.nod*.055+p.s.gazeDown*.035;
  c.save();c.translate(p.shoulderX,p.hipY-142);c.rotate(angle);c.translate(turn*5,-42);
  if(a.hair==='pony'){const pp=(x,y,px,py)=>`${mix(x,-dir*px,v)} ${mix(y,py,v)}`;path(c,`M ${pp(32,-30,28,-32)} C ${pp(71,-47,61,-44)} ${pp(80,-5,69,-7)} ${pp(61,25,50,25)} Q ${pp(51,41,45,40)} ${pp(62,58,47,55)} Q ${pp(38,51,26,48)} ${pp(42,24,35,20)} Z`,hair)}
  if(a.hair==='bob'){c.save();c.translate(-dir*v*8,0);c.scale(1-.20*v,1);path(c,'M -46 -30 Q -40 -68 4 -61 Q 54 -64 53 -15 L 47 53 L -45 53 Z',hair);c.restore()}
  const farEar=C(1-v/.4);if(farEar>.01)ellipse(c,dir*mix(43,22,v),2,9*farEar,14,skin,'#7e5545');
  const pt=(x,y,px,py)=>`${dir*mix(x,px,v)} ${mix(y,py,v)}`;
  const face=new Path2D(a.faceShape==='angular'?`M ${pt(-40,-24,-31,-24)} C ${pt(-43,-44,-33,-44)} ${pt(-24,-55,-18,-55)} ${pt(0,-55,0,-55)} C ${pt(27,-55,22,-55)} ${pt(44,-42,25,-42)} ${pt(42,-19,24,-19)} L ${pt(42,0,25,-2)} Q ${pt(42,8,41,7)} ${pt(42,14,34,13)} L ${pt(38,30,29,28)} L ${pt(22,47,25,43)} L ${pt(-6,50,3,48)} L ${pt(-30,39,-22,38)} Q ${pt(-43,22,-31,18)} ${pt(-41,5,-31,5)} Z`:`M ${pt(-42,-23,-32,-23)} C ${pt(-44,-45,-34,-45)} ${pt(-25,-55,-16,-55)} ${pt(0,-55,0,-55)} C ${pt(27,-55,22,-55)} ${pt(44,-43,25,-42)} ${pt(43,-20,24,-20)} L ${pt(43,0,25,-2)} Q ${pt(43,8,41,7)} ${pt(43,13,34,12)} Q ${pt(43,20,29,16)} ${pt(43,23,27,14)} C ${pt(40,38,29,31)} ${pt(22,47,27,42)} ${pt(0,48,6,45)} C ${pt(-24,47,-19,44)} ${pt(-43,33,-30,29)} ${pt(-43,10,-31,10)} Z`);
  path(c,face,skin,'#634c44',1.8);
  const ear=dir*mix(-43,-13,v);ellipse(c,ear,2,mix(9,7.5,v),mix(14,12,v),skin,'#a56e56',1.2);path(c,`M ${ear-dir*2} -3 Q ${ear+dir*5} -1 ${ear+dir*1} 6`,null,'#ba8166',1.1);
  c.save();c.clip(face);if(drawAudit)drawAudit.faceFeaturesClipped=true;
  ellipse(c,mix(-27,-dir*5,v),17,6.5,3.2,'rgba(218,119,102,.16)');
  const blink=Math.max(.03,1-p.blink),eyes=[];
  for(const sign of[-1,1]){
   const near=sign===-dir,visibility=near?1:C(1-v/.64),alpha=visibility>.02?1:0,ex=mix(sign*18,dir*(near?14:25),v)+turn*5,ew=near?mix(8.5,6.8,v):8.5*visibility;eyes.push({sign,near,alpha,ex,ew});
   if(!alpha)continue;c.save();ellipse(c,ex,-6,ew,9.5*blink,'#fffef8','#4a3933',1.3);
   if(blink>.16){const gaze=mix(p.look,dir,v);ellipse(c,ex+gaze*1.7*visibility,-5+p.s.gazeDown*3.2,mix(4.5,3.6,v)*visibility,6.8*blink,'#45362f');ellipse(c,ex+(gaze*1.7-1.2)*visibility,-8+p.s.gazeDown*3.2,1.6*visibility,2*blink,'#ffffff')}
   const inner=sign<0?1:-1,raise=p.s.concern*4,bw=mix(11,8,v)*visibility;path(c,`M ${ex-bw} ${-24+raise*(1-inner)} Q ${ex} ${-28-raise*inner} ${ex+bw} ${-24+raise*(1+inner)}`,null,hair,a.age>40?3.5:2.6);c.restore();
  }
  path(c,`M ${mix(turn*7,dir*29,v)} ${mix(2,11,v)} Q ${mix(turn*10-3,dir*32,v)} ${mix(12,14,v)} ${mix(turn*8+3,dir*34,v)} ${mix(14,12,v)}`,null,'#bc8064',mix(1.7,1.2,v));
  const my=28,mw=mix(18,9,v),mx=mix(turn*4,dir*22,v);
  if(p.mouth>.1){ellipse(c,mx,my,mw*.44,2+p.mouth*7,'#633d36','#8c5345',1.2);if(p.mouth>.4)path(c,`M ${mx-mw*.36} ${my-4} L ${mx+mw*.36} ${my-4}`,null,'#fff9e8',2)}else path(c,`M ${mx-mw/2} ${my} Q ${mx} ${my+5-10*p.s.concern+3*p.s.relief} ${mx+mw/2} ${my}`,null,'#8c5345',2.2);
  if(a.hair==='mature'){path(c,`M ${mix(-27,-dir*5,v)} 19 L ${mix(-20,dir*2,v)} 21`,null,'#c28b71',1.3);path(c,'M -27 -38 Q 0 -44 25 -37',null,'#c28b71',1.1)}
  c.restore();
  const hd=a.hair==='spiky'?'M -44 -5 Q -52 -23 -44 -31 L -47 -44 Q -34 -47 -24 -42 L -22 -57 Q -12 -58 -5 -49 L 6 -62 Q 20 -58 22 -48 Q 46 -51 43 -32 Q 56 -21 46 -1 L 34 -20 Q 11 -10 -7 -28 Q -25 -22 -38 0 Z':['side-part','sidepart'].includes(a.hair)?'M -43 5 Q -54 -35 -29 -49 Q -9 -69 18 -54 Q 43 -57 47 -31 L 42 4 L 31 -17 Q 18 -18 9 -31 Q -6 -8 -34 -10 L -37 9 Z':a.hair==='mature'?'M -43 2 Q -59 -44 -22 -55 Q 0 -70 28 -52 Q 58 -43 44 4 L 34 -23 Q 11 -34 -10 -25 L -35 -14 Z':'M -44 2 Q -61 -41 -22 -57 Q 12 -75 41 -47 Q 60 -28 45 8 L 34 -21 Q 4 -7 -18 -21 Q -31 -19 -38 8 Z';
  c.save();c.translate(-dir*8*v,0);c.scale(1-.25*v,1);path(c,hd,hair,'#302d30',1.8);path(c,'M -31 -37 Q -7 -58 24 -41',null,'#76615a',2.2);
  if(a.hair==='mature'){path(c,'M -45 -12 L -37 -14 L -36 11 L -43 14 Z','#99918a',null);path(c,'M 36 -15 L 45 -11 L 42 14 L 35 10 Z','#99918a',null)}c.restore();
  if(a.glasses){c.save();c.clip(face);const visible=eyes.filter(e=>e.alpha);for(const eye of visible){c.strokeStyle='#514a47';c.lineWidth=1.9;c.beginPath();c.roundRect(eye.ex-eye.ew-4,-20,eye.ew*2+8,27,5);c.stroke();if(eye.near)path(c,`M ${eye.ex-dir*(eye.ew+4)} -12 L ${dir*mix(-43,-13,v)} -4`,null,'#514a47',1.9)}if(visible.length===2){const left=visible[0],right=visible[1];path(c,`M ${left.ex+left.ew+4} -11 Q ${(left.ex+right.ex)/2} -14 ${right.ex-right.ew-4} -11`,null,'#514a47',1.9)}c.restore()}
  c.restore();
 }
 function torso(c,a,p,images,skin){
  const y=p.hipY,ct=p.front,st=p.profile,F=(x,z=17)=>p.shoulderX+x*ct+z*st,nw=mix(20,11,Math.abs(st)),nx=p.shoulderX+st*4;
  path(c,`M ${nx-nw} ${y-150} L ${nx+nw} ${y-150} L ${nx+nw} ${y-121} Q ${F(0)} ${y-112} ${nx-nw} ${y-121} Z`,skin,null);
  path(c,`M ${nx-nw} ${y-143} L ${nx-nw} ${y-121} M ${nx+nw} ${y-143} L ${nx+nw} ${y-121}`,null,'#7e5545',1.4);
  if(a.shirt==='jacket'){
    const center=F(0),band=Math.max(3,17*ct);path(c,`M ${center-band} ${y-127} Q ${center} ${y-116} ${center+band} ${y-127} L ${center+band} ${y+4} L ${center-band} ${y+4} Z`,a.innerColor||'#ece9e0',null);
    path(c,`M ${F(-22)} ${y-127} L ${F(-31,12)} ${y-96} L ${F(-19,18)} ${y-77} L ${F(-23)} ${y+5} M ${F(22)} ${y-127} L ${F(31,12)} ${y-96} L ${F(19,18)} ${y-77} L ${F(23)} ${y+5}`,null,'#717985',1.8);
    path(c,`M ${F(-36)} ${y-30} L ${F(-23)} ${y-22} M ${F(23)} ${y-22} L ${F(36)} ${y-30}`,null,'#717985',1.6);
  }else if(a.shirt==='tee')path(c,`M ${F(-20)} ${y-131} Q ${F(0)} ${y-105} ${F(20)} ${y-131}`,null,'#6e627c',2.4);
  else{
    const collar=a.shirt==='blue'?'#98b8d9':a.shirt==='shirt'?(a.shirtColor||'#c9b18e'):'#474b55';
    path(c,`M ${F(-24,9)} ${y-130} L ${F(0)} ${y-106} L ${F(-18,20)} ${y-89} L ${F(-37,12)} ${y-116} Z`,collar);
    path(c,`M ${F(24,9)} ${y-130} L ${F(0)} ${y-106} L ${F(17,20)} ${y-89} L ${F(37,12)} ${y-116} Z`,collar);
    path(c,`M ${F(-2)} ${y-105} L ${F(3)} ${y-105} L ${F(3)} ${y-63} L ${F(-2)} ${y-63} Z`,a.shirt==='blue'?'#658ab6':'#222630',null);
    if(ct>.12){ellipse(c,F(.5),y-95,1.8*ct,1.8,'#d5d9da');ellipse(c,F(.5),y-81,1.8*ct,1.8,'#d5d9da')}
  }
  if(a.shirt!=='jacket'&&ct>.12&&images[a.logoAsset]){c.save();c.translate(F(22,12),y-92);c.scale(ct,1);c.drawImage(images[a.logoAsset],0,0,22,22*images[a.logoAsset].height/images[a.logoAsset].width);c.restore()}
  const bw=40*p.bodyWidth;path(c,`M ${p.shoulderX-bw} ${y+1} Q ${p.shoulderX} ${y+12} ${p.shoulderX+bw} ${y+1}`,null,'#222834',5);
  if(ct>.12)path(c,`M ${F(-6,14)} ${y+4} L ${F(6,14)} ${y+4} L ${F(6,14)} ${y+11} L ${F(-6,14)} ${y+11} Z`,'#777e89','#252c36',1.3);
 }
 function paint(c,n,f,images,hidden){const a=n.vectorActor,p=pose(n,f),skin=a.skin||'#efb38f',shirt=a.shirtColor||(a.shirt==='blue'?'#84a9d3':a.shirt==='jacket'?'#557c9f':'#34363e'),pants=a.pantsColor||'#343944';
  drawAudit={baseOpacity:c.globalAlpha,minimumRelativeOpacity:1,armLayers:[],faceFeaturesClipped:false};
  for(const foot of p.g.feet)if(foot.stance)ellipse(c,(foot.x-p.g.x)/p.scale,2,26,3.5,'rgba(0,0,0,.13)');
  const order=p.g.dir>0?[0,1]:[1,0];for(const i of order){limb(c,p.legs[i],19,14,10,pants);shoe(c,p.g.feet[i],p)}
  const foreground=arm=>Math.abs(p.profile)<.12||arm.side===(p.profile>=0?-1:1)||p.s.write>.001||(arm.active&&Math.max(p.s.gesture,p.s.reach,p.s.tryEar,p.s.shrug)>.001);
  for(const arm of p.arms)if(!foreground(arm)){skinArm(c,arm,skin,'behind-torso');palm(c,arm,p,skin)}
  garment(c,p,shirt);
  torso(c,a,p,images,skin);
  for(const arm of p.arms)if(foreground(arm))skinArm(c,arm,skin,'in-front-of-torso');
  head(c,a,p);prop(c,n,p,f,hidden);for(const arm of p.arms)if(foreground(arm))palm(c,arm,p,skin);
  const m=c.getTransform(),world=(x,y)=>({x:m.a*x+m.c*y+m.e,y:m.b*x+m.d*y+m.f});
  const footReceipt={};p.g.feet.forEach((foot,i)=>{const sole=world((foot.x-p.g.x)/p.scale,(foot.y-p.g.floor)/p.scale);footReceipt[i?'right':'left']={soleX:sole.x,soleY:sole.y,stance:foot.stance,lift:foot.lift,yaw:foot.yaw,roll:foot.angle,stage:foot.stage,boneError:p.legs[i].boneError,reachError:p.legs[i].error}});
  const drawing=drawAudit;drawAudit=null;
  return {x:p.g.x,floor:p.g.floor,walking:p.g.weight>0,drawing,turning:p.g.turning,orientation:{torsoYaw:p.bodyYaw,headYaw:p.headYaw,hipYaw:p.hipYaw,frontProjection:p.front,faceProfile:Math.sin(p.headYaw),shoulderSpan:Math.abs(p.arms[1].P[0]-p.arms[0].P[0]),hipSpan:Math.abs(p.legs[1].P[0]-p.legs[0].P[0])},gesture:p.s.gesture,concern:p.s.concern,nod:p.s.nod,reach:p.s.reach,tryEar:p.s.tryEar,write:p.s.write,scribble:p.s.scribble,gazeDown:p.s.gazeDown,shrug:p.s.shrug,turn:p.turn,mouthOpen:p.mouth,feet:footReceipt,hands:{left:world(...p.arms[0].Q),right:world(...p.arms[1].Q)},shoulders:{left:world(...p.arms[0].P),right:world(...p.arms[1].P)},elbows:{left:world(...p.arms[0].K),right:world(...p.arms[1].K)},maxBoneError:Math.max(...p.legs.map(b=>b.boneError),...p.arms.map(b=>b.boneError)),maxReachError:Math.max(...p.legs.map(b=>b.error),...p.arms.map(b=>b.error)),representation:'solid-vector-acting/1'};
 }
 function propState(n,f){const a=n.vectorProp,b=(a.bindings||[]).find(b=>b.startFrame<=f&&f<b.endFrame);if(!b||!b.actorId)return{x:b?.x??n.x,y:b?.y??n.y,attachment:'surface'};const actor=registry.get(b.actorId);if(!actor)throw Error('未绑定道具持有者 '+b.actorId);const p=pose(actor,f),hand=p.arms[p.look>0?1:0].Q;return{x:p.g.x+(actor.editDx||0)+hand[0]*p.scale,y:p.g.floor+(actor.editDy||0)+hand[1]*p.scale,attachment:actor.id,actor,p};}
 function paintProp(c,n,f){const s=propState(n,f);if(n.vectorProp.kind==='airpod'){airpod(c,0,0);if(s.p){const arm=s.p.arms[s.p.look>0?1:0],angle=-Math.atan2(arm.Q[0]-arm.K[0],arm.Q[1]-arm.K[1]);c.save();c.rotate(angle);path(c,'M -7 -3 Q -9 -13 -3 -15 Q 3 -17 6 -8 Q 11 -12 14 -7 L 8 6 Q 1 12 -7 5 Z',s.actor.vectorActor.skin||'#efb38f');c.restore()}}return{x:s.x,y:s.y,attachment:s.attachment,kind:n.vectorProp.kind};}
 function bounds(n,f){const p=pose(n,f),boxes=[],box=(x,y,w,h)=>boxes.push({x,y,width:w,height:h}),bone=(P,Q,r)=>box(Math.min(P[0],Q[0])-r,Math.min(P[1],Q[1])-r,Math.abs(P[0]-Q[0])+2*r,Math.abs(P[1]-Q[1])+2*r);box(p.shoulderX-60*p.bodyWidth,p.hipY-145,120*p.bodyWidth,161);let minX=-58,maxX=58;if(n.vectorActor.hair==='pony'){const v=Math.abs(Math.sin(p.headYaw)),dir=Math.sign(p.headYaw)||1,points=[32,71,80,61,51,62,38,42].map((x,i)=>mix(x,-dir*[28,61,69,50,45,47,26,35][i],v));minX=Math.min(minX,...points);maxX=Math.max(maxX,...points)}box(p.shoulderX+minX,p.hipY-255,maxX-minX,173);for(const b of p.legs){bone(b.P,b.K,20);bone(b.K,b.Q,15)}for(const b of p.arms){bone(b.P,b.K,21);bone(b.K,b.Q,13);box(b.Q[0]-26,b.Q[1]-26,52,52)}for(const foot of p.g.feet)box((foot.x-p.g.x)/p.scale-35,(foot.y-p.g.floor)/p.scale-24,70,26);return boxes}
 function runtimeCalls(n,f){const calls=[],add=(type,a,z)=>{if(a<f&&f<z)calls.push({nodeId:n.id,type,frame:f,startFrame:a,endFrame:z,progress:(f-a)/(z-a),role:n.role||'subject'})};if(n.vectorActor){for(const w of n.vectorActor.walks||[])add('actor-walk',w.startFrame,w.endFrame);let prior=null;for(const key of n.vectorActor.facing||[]){if(prior&&prior.yaw!==key.yaw)add('actor-coordinated-turn',prior.frame-4,key.frame+1);prior=key}for(const key of Object.keys(defaults)){let previous={frame:n.startFrame,value:defaults[key]};for(const item of n.vectorActor.keys||[]){if(!Object.prototype.hasOwnProperty.call(item.values,key))continue;if(previous.value!==item.values[key])add('actor-'+key,previous.frame,item.frame);previous={frame:item.frame,value:item.values[key]}}}}if(n.vectorProp)for(const b of n.vectorProp.bindings||[])if(b.actorId)add('actor-hand-bound-'+n.vectorProp.kind,b.startFrame,b.endFrame);return calls}
 window.CourseActors={bounds,runtimeCalls,prepare(nodes,frame){registry=new Map();cache=new Map();const visit=ns=>{for(const n of ns){registry.set(n.id,n);visit(n.children||[])}};visit(nodes)},motionState(n,frame){if(n.vectorProp)return propState(n,frame);const g=gait(n,frame);return{x:g.x,y:g.floor}},paint,paintProp,pose,gait,ik,rootAt,heading};
})();
