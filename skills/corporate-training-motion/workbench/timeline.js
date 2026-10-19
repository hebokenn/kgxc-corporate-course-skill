// Source coordinates stay immutable; all playback uses this integer-frame edit list.
const EMPTY=[],cache=new WeakMap();
export function displayFrame(f,holds,cuts=EMPTY){return f-cuts.reduce((n,c)=>n+Math.max(0,Math.min(f,c.endFrame)-c.startFrame),0)+holds.filter(h=>h.sourceFrame<=f).reduce((n,h)=>n+h.frames,0)}
export function totalFrames(d){return d.sourceDurationFrames-(d.cuts||EMPTY).reduce((n,c)=>n+c.endFrame-c.startFrame,0)+d.holds.reduce((n,h)=>n+h.frames,0)}
function buildSegments(end,holds,cuts){
 const byFrame=new Map(holds.map(h=>[h.sourceFrame,h])),points=[...new Set([0,end,...byFrame.keys(),...cuts.flatMap(c=>[c.startFrame,c.endFrame])])].sort((a,b)=>a-b);let cursor=0,ci=0;const out=[];
 for(let i=0;i<points.length;i++){const a=points[i],h=byFrame.get(a);if(h?.frames){out.push({kind:'hold',startFrame:cursor,endFrame:cursor+h.frames,sourceFrame:Math.max(0,a-1),holdFrame:a,sceneId:h.sceneId});cursor+=h.frames}if(i===points.length-1)break;const b=points[i+1];while(ci<cuts.length&&cuts[ci].endFrame<=a)ci++;if(ci<cuts.length&&cuts[ci].startFrame<=a&&a<cuts[ci].endFrame)continue;out.push({kind:'source',startFrame:cursor,endFrame:cursor+b-a,sourceFrame:a});cursor+=b-a}
 return out;
}
export function segments(d){return buildSegments(d.sourceDurationFrames,d.holds,d.cuts||EMPTY)}
export function sourceFrame(f,holds,cuts=EMPTY){
 let entry=cache.get(holds);if(!entry||entry.cuts!==cuts){entry={cuts,spans:buildSegments(Infinity,holds,cuts)};cache.set(holds,entry)}
 let lo=0,hi=entry.spans.length-1;while(lo<=hi){const i=(lo+hi)>>1,s=entry.spans[i];if(f<s.startFrame)hi=i-1;else if(f>=s.endFrame)lo=i+1;else return s.sourceFrame+(s.kind==='source'?f-s.startFrame:0)}return 0;
}
export function rippleCut(doc,start,end){
 const before=totalFrames(doc);if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||start>=end||end>before||end-start>=before)throw Error('请选择有效裁剪区间，并至少保留一帧课程');
 const d=structuredClone(doc),cuts=[...(d.cuts||[])],removed=new Map();
 for(const s of segments(doc)){const a=Math.max(start,s.startFrame),b=Math.min(end,s.endFrame);if(a>=b)continue;if(s.kind==='hold')removed.set(s.holdFrame,b-a);else cuts.push({startFrame:s.sourceFrame+a-s.startFrame,endFrame:s.sourceFrame+b-s.startFrame})}
 const merged=[];for(const c of cuts.sort((a,b)=>a.startFrame-b.startFrame)){const last=merged.at(-1);if(last&&c.startFrame<=last.endFrame)last.endFrame=Math.max(last.endFrame,c.endFrame);else merged.push(c)}
 d.cuts=merged;d.holds=d.holds.map(h=>({...h,frames:h.frames-(removed.get(h.sourceFrame)||0)})).filter(h=>h.frames>0);
 const move=t=>t<=start?t:t>=end?t-(end-start):start;d.captions=d.captions.map(c=>({...c,startFrame:move(c.startFrame),endFrame:move(c.endFrame)})).filter(c=>c.endFrame>c.startFrame);return d;
}
