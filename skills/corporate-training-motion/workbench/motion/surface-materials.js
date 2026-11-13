/* Deterministic local surface rendering. Materials are not counted as new actions. */
(()=>{
 const cache=new Map(),cl=x=>Math.max(0,Math.min(255,Math.round(x))),mix=(a,b,p)=>a+(b-a)*p;
 const ids=['vector-clean','cel-paint','neon-emission','ink-paper','chalk-dust','watercolor','cut-paper','newsprint','comic-halftone','wood-grain','cyanotype','brushed-metal','clay-matte','lowpoly-facets','pixel-dither','screen-print','clear-acrylic','polished-glass','photo-real','ceramic-glaze','graphite','letterpress','felt-fabric','plastic-toy'];
 const rgb=s=>{if(typeof s!=='string')return [140,161,148];if(/^#[0-9a-f]{6,8}$/i.test(s))return [1,3,5].map(i=>parseInt(s.slice(i,i+2),16));if(/^#[0-9a-f]{3}$/i.test(s))return [1,2,3].map(i=>parseInt(s[i]+s[i],16));return [140,161,148]};
 const color=(c,q,a=1)=>`rgba(${c.map(v=>cl(v+q)).join(',')},${a})`;
 function texture(id,base){const key=id+'|'+base;if(cache.has(key))return cache.get(key);let seed=2166136261;for(const k of key)seed=Math.imul(seed^k.charCodeAt(0),16777619)>>>0;const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296};const can=document.createElement('canvas');can.width=can.height=256;const c=can.getContext('2d'),v=rgb(base);c.fillStyle=typeof base==='string'?base:'#b6c9bd';c.fillRect(0,0,256,256);
 const noise=(count,amplitude,size=1,alpha=.28)=>{for(let i=0;i<count;i++){c.fillStyle=color(v,(rand()-.5)*amplitude,alpha);c.fillRect(rand()*256,rand()*256,size,size)}};
 if(id==='vector-clean'||id==='photo-real'){}
 else if(id==='cel-paint'){c.fillStyle=color(v,-28);c.fillRect(160,0,96,256);c.fillStyle=color(v,25);c.beginPath();c.moveTo(0,0);c.lineTo(140,0);c.lineTo(0,140);c.fill()}
 else if(id==='ink-paper'){noise(4000,30);c.strokeStyle=color(v,-55,.23);c.lineWidth=.7;for(let i=0;i<95;i++){const x=rand()*256,y=rand()*256;c.beginPath();c.moveTo(x,y);c.lineTo(x+3+rand()*13,y+rand()*4);c.stroke()}}
 else if(id==='chalk-dust'){noise(14000,180,1,.8);for(let i=0;i<70;i++){c.strokeStyle=color(v,65,.16);c.lineWidth=1+rand()*4;c.beginPath();c.moveTo(0,rand()*256);c.lineTo(256,rand()*256);c.stroke()}}
 else if(id==='watercolor'){for(let i=0;i<180;i++){c.fillStyle=color(v,(rand()-.5)*100,.08+rand()*.1);const x=rand()*256,y=rand()*256,r=12+rand()*75;c.beginPath();for(let j=0;j<16;j++){const a=j*Math.PI/8,z=r*(.8+rand()*.3);j?c.lineTo(x+Math.cos(a)*z,y+Math.sin(a)*z):c.moveTo(x+Math.cos(a)*z,y+Math.sin(a)*z)}c.closePath();c.fill()}noise(1700,60,1,.18)}
 else if(id==='cut-paper'){noise(9500,35,1,.55);for(let i=0;i<700;i++){c.strokeStyle=color(v,rand()*30-15,.3);const x=rand()*256,y=rand()*256;c.beginPath();c.moveTo(x,y);c.lineTo(x+rand()*5,y+rand()*2);c.stroke()}}
 else if(id==='newsprint'){const grey=v[0]*.3+v[1]*.6+v[2]*.1;c.fillStyle=color([grey,grey,grey],10);c.fillRect(0,0,256,256);for(let y=0;y<256;y+=7)for(let x=0;x<256;x+=7){c.fillStyle='rgba(20,25,24,.2)';c.beginPath();c.arc(x+(y%14?3.5:0),y,1.25,0,Math.PI*2);c.fill()}noise(6500,60,1,.3)}
 else if(id==='comic-halftone'){for(let y=0;y<256;y+=11)for(let x=0;x<256;x+=11){c.fillStyle=color(v,-80,.45);c.beginPath();c.arc(x+(y%22?5.5:0),y,2.8,0,Math.PI*2);c.fill()}}
 else if(id==='wood-grain'){for(let i=0;i<80;i++){c.strokeStyle=color(v,(i%5-2)*17,.7);c.lineWidth=i%7===0?2.5:.7;const y=i*3.2;c.beginPath();for(let x=0;x<=256;x+=8){const z=y+7*Math.sin(x*.026+i*.16)+3*Math.sin(x*.07+i*.27);x?c.lineTo(x,z):c.moveTo(x,z)}c.stroke()}c.strokeStyle=color(v,-32,.4);c.beginPath();c.ellipse(170,105,35,14,-.1,0,Math.PI*2);c.stroke();noise(2000,30)}
 else if(id==='cyanotype'){c.strokeStyle=color(v,100,.25);c.lineWidth=1;for(let x=0;x<256;x+=16){c.beginPath();c.moveTo(x,0);c.lineTo(x,256);c.moveTo(0,x);c.lineTo(256,x);c.stroke()}noise(6500,60,1,.4)}
 else if(id==='brushed-metal'){const g=c.createLinearGradient(0,0,256,0);for(const [p,q] of [[0,-45],[.25,24],[.43,-15],[.54,65],[.65,0],[1,-35]])g.addColorStop(p,color(v,q));c.fillStyle=g;c.fillRect(0,0,256,256);for(let i=0;i<256;i++){c.strokeStyle=color(v,(rand()-.5)*55,.4);c.beginPath();c.moveTo(0,i);c.lineTo(256,i+.2);c.stroke()}}
 else if(id==='clay-matte'){noise(19000,65,1,.35);for(let i=0;i<40;i++){c.strokeStyle=color(v,-35,.13);c.lineWidth=2;c.beginPath();c.ellipse(rand()*256,rand()*256,12+rand()*25,3+rand()*9,rand(),0,Math.PI*2);c.stroke()}}
 else if(id==='lowpoly-facets'){for(let y=-1;y<5;y++)for(let x=-1;x<5;x++){const z=64;c.fillStyle=color(v,(rand()-.5)*75);c.beginPath();c.moveTo(x*z,y*z);c.lineTo((x+1)*z,y*z);c.lineTo(x*z,(y+1)*z);c.closePath();c.fill();c.fillStyle=color(v,(rand()-.5)*75);c.beginPath();c.moveTo((x+1)*z,y*z);c.lineTo((x+1)*z,(y+1)*z);c.lineTo(x*z,(y+1)*z);c.closePath();c.fill()}}
 else if(id==='pixel-dither'){for(let y=0;y<32;y++)for(let x=0;x<32;x++){c.fillStyle=color(v,((x*3+y*5)%7-3)*8);c.fillRect(x*8,y*8,8,8)}}
 else if(id==='screen-print'){for(let y=0;y<256;y+=4)for(let x=0;x<256;x+=4){c.fillStyle=color(v,(x+y)%8?-30:30,.35);c.fillRect(x,y,2.5,2.5)}noise(3500,85,1,.2)}
 else if(id==='graphite'){const g=v[0]*.3+v[1]*.6+v[2]*.1;c.fillStyle=color([g,g,g],0);c.fillRect(0,0,256,256);for(let i=0;i<2400;i++){const x=rand()*256,y=rand()*256;c.strokeStyle=color([60,62,55],rand()*50,.12);c.lineWidth=.4+rand();c.beginPath();c.moveTo(x,y);c.lineTo(x+25+rand()*50,y-18-rand()*30);c.stroke()}}
 else if(id==='letterpress'){noise(12000,45,1,.7);for(let i=0;i<280;i++){c.fillStyle=color(v,-50,.17);c.fillRect(rand()*256,rand()*256,1+rand()*4,1+rand()*2)}}
 else if(id==='felt-fabric'){for(let y=0;y<256;y+=4){c.strokeStyle=color(v,y%8?26:-30,.7);c.lineWidth=1.3;c.beginPath();c.moveTo(0,y);c.lineTo(256,y);c.stroke()}for(let x=0;x<256;x+=4){c.strokeStyle=color(v,x%8?-25:20,.65);c.lineWidth=1.2;c.beginPath();c.moveTo(x,0);c.lineTo(x,256);c.stroke()}noise(8000,90,1,.3)}
 else if(id==='clear-acrylic'||id==='polished-glass'||id==='ceramic-glaze'||id==='plastic-toy'){const g=c.createLinearGradient(0,0,180,256);g.addColorStop(0,color(v,65,id.includes('glass')||id.includes('acrylic')?.3:1));g.addColorStop(.35,color(v,15,.85));g.addColorStop(.44,color(v,65,.7));g.addColorStop(.51,color(v,20,.7));g.addColorStop(1,color(v,-35,.95));c.clearRect(0,0,256,256);c.fillStyle=g;c.fillRect(0,0,256,256);if(id==='plastic-toy'){c.fillStyle='rgba(255,255,255,.25)';c.fillRect(0,0,256,8)}}
 else if(id==='neon-emission'){c.fillStyle=base;c.fillRect(0,0,256,256)}
 const p=c.createPattern(can,'repeat');cache.set(key,p);return p;}
 function apply(c,n){const id=n.surface?.type||n.surface;if(!ids.includes(id))throw Error('未实现质感 '+id);
 // Lighting belongs to one object. Repeating a highlight tile across a page makes
 // a checkerboard, and printing material into every glyph destroys legibility.
 const ground=n.surfaceRole==='ground',text=n.type==='text',v=rgb(n.fill),w=n.width||256,h=n.height||256;
 if(text){
  if(id==='neon-emission' && !/title$/.test(n.id||'')){c.shadowColor=n.fill;c.shadowBlur=7}
  return;
 }
 if(ground){
  const papers=['ink-paper','watercolor','cut-paper','newsprint','graphite','letterpress','screen-print'];
  if(papers.includes(id))c.fillStyle=texture('ink-paper',n.fill);
  else if(id==='chalk-dust')c.fillStyle=texture(id,n.fill);
  else if(id==='wood-grain')c.fillStyle=texture(id,n.fill);
  else if(id==='felt-fabric')c.fillStyle=texture(id,n.fill);
  return;
 }
 if(n.fill!==null&&typeof n.fill==='string'&&n.type!=='image'){
  if(['cel-paint','brushed-metal','clear-acrylic','polished-glass','ceramic-glaze','plastic-toy','lowpoly-facets'].includes(id)){
   const g=c.createLinearGradient(0,0,w,id==='brushed-metal'?0:h);
   let stops=id==='cel-paint'?[[0,15],[.69,15],[.7,-15],[1,-15]]:id==='brushed-metal'?[[0,-25],[.26,15],[.51,45],[.66,-10],[1,0]]:id==='lowpoly-facets'?[[0,12],[.48,12],[.49,-12],[1,-12]]:[[0,24],[.17,12],[.65,0],[1,-16]];
   for(const [p,q] of stops)g.addColorStop(p,color(v,q));c.fillStyle=g;
  }else c.fillStyle=texture(id,n.fill);
 }
 if(['cut-paper','wood-grain','clay-matte','felt-fabric','plastic-toy','ceramic-glaze'].includes(id)){c.shadowColor=id==='cut-paper'?'rgba(43,30,17,.3)':'rgba(26,42,41,.23)';c.shadowBlur=id==='clay-matte'?18:7;c.shadowOffsetX=id==='cut-paper'?7:3;c.shadowOffsetY=id==='cut-paper'?10:6}
 if(id==='neon-emission'){c.shadowColor=n.stroke||n.fill||'#75d2e4';c.shadowBlur=18;c.lineWidth=Math.max(2,n.lineWidth||3)}
 if(id==='letterpress'){c.shadowColor='rgba(255,255,245,.8)';c.shadowOffsetX=1;c.shadowOffsetY=2;c.shadowBlur=0}
 }
 window.CourseSurface={ids:()=>[...ids],apply,texture};
})();
