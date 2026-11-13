import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
// Optional silent prototype. Feed approved content through props; not a finished film.
export const CorporateTraining:React.FC<{title?:string;steps?:string[]}>=({title='课程主题',steps=['对象核对','实际操作','结果确认']})=>{
 const t=useCurrentFrame()/30;
 return <AbsoluteFill style={{background:'#F7F9FC',color:'#172334',fontFamily:'Noto Sans CJK SC, PingFang SC, sans-serif'}}>
  <div style={{position:'absolute',left:112,top:100,fontSize:68}}>{title}</div>
  <div style={{position:'absolute',left:112,right:112,top:350,display:'flex',gap:50}}>
   {steps.map((s,i)=><div key={i} style={{flex:1,padding:40,fontSize:42,background:'#EAF1FB',opacity:interpolate(t,[i*2,i*2+.6],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>{s}</div>)}
  </div>
 </AbsoluteFill>;
};
