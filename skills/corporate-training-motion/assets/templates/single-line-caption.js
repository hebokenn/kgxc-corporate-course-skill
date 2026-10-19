// Canvas adapter. No wrapping/maxWidth squeezing. Supply a licensed installed font.
// Call with the active cue selected from the *display* timeline, not speech events.
function drawSingleLineCaption(ctx,cue,style){
  if(!cue)return null;
  const {text,id}=cue;
  if(/[\r\n]/.test(text)||/\p{P}/u.test(text))throw Error('Subtitle must be one punctuation-free line: '+id);
  ctx.save();ctx.setTransform(1,0,0,1,0,0);
  ctx.font=style.font;ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';ctx.lineWidth=style.strokeWidth;
  const m=ctx.measureText(text),x=style.x,y=style.y,p=style.strokeWidth/2;
  const bounds=[x-m.actualBoundingBoxLeft-p,y-m.actualBoundingBoxAscent-p,x+m.actualBoundingBoxRight+p,y+m.actualBoundingBoxDescent+p],s=style.safe;
  if(bounds[0]<s[0]||bounds[1]<s[1]||bounds[2]>s[2]||bounds[3]>s[3]){ctx.restore();throw Error('Split subtitle; do not shrink/wrap: '+id);}
  ctx.strokeStyle=style.stroke;ctx.fillStyle=style.fill;ctx.strokeText(text,x,y);ctx.fillText(text,x,y);ctx.restore();
  return {id,text,bounds,line_count:1,font:style.font,stroke_width:style.strokeWidth};
}
