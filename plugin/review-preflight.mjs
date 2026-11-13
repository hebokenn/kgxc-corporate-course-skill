import {createHash} from 'node:crypto';
import {mkdir,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

export function assertCleanLearnerPayload(payload){
  const marker=/\b(?:UV\d{2,}(?:-F\d+)?|(?:PILOT|FINAL|STORYBOARD|SCRIPT)-F\d+|history:F\d+)\b|\bUSER-FOLLOWUP-[A-Za-z0-9]+|\/Users\/[^\s"']+|file:\/\/|(?:^|\s)(?:project|qa|source|work)\/[^\s]+\.(?:json|md|pdf|wav|mp4)\b/i;
  const forbidden=new Set(['producer_history','prior_reviews','repair_history','source_document','expected_answer','teaching_objectives','original_material']);
  function walk(value,path='$'){
    if(typeof value==='string'&&marker.test(value))throw Error('REVIEW_INPUT_CONTAMINATED: '+path);
    if(Array.isArray(value))return value.forEach((v,i)=>walk(v,path+'['+i+']'));
    if(value&&typeof value==='object')for(const [k,v] of Object.entries(value)){
      if(forbidden.has(k))throw Error('REVIEW_INPUT_CONTAMINATED: '+path+'.'+k);
      walk(v,path+'.'+k);
    }
  }
  walk(payload);return payload;
}

export async function probeReviewer({get,selection,prepared,packet,course_path,strict=true}){
  // Successful local ingress demonstrates supported attachment transport only;
  // actual sent/received artifact IDs are audited after the model invocation.
  const capabilities=['text','media_probe','automatic_audio_technical'];
  const probes=[{kind:'composed-route',ok:prepared?.config?.provider===selection.provider&&prepared?.config?.model===selection.model}];
  const attachments=get('attachments');
  if(attachments?.saveImage){
    const data=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNQiFjwHwADzAIY3R2iUgAAAABJRU5ErkJggg==','base64');
    const ref=await attachments.saveImage({data,mediaType:'image/png',name:'kgxc-capability-probe.png'});
    const ok=ref!==undefined&&ref!==null;
    probes.push({kind:'image-attachment-ingress',ok,sha256:createHash('sha256').update(data).digest('hex')});
    if(ok)capabilities.push('images');
  }
  const needs={script_read:['text'],storyboard_read:['text'],frames:['images'],frame_sequence:['images'],full_av:['continuous_video','audio_listening'],user_listening:['user_listening'],media_probe:['media_probe'],automatic_audio_technical:['automatic_audio_technical']};
  const checks=(packet.checklist||[]).map(c=>({id:c.id,method:c.required_method,critical:c.critical===true,missing:(needs[c.required_method]||['unknown_method']).filter(x=>!capabilities.includes(x))}));
  const receipt={schema:'review-runner-probe/1',route:{provider:prepared.config.provider,model:prepared.config.model},tool:'DSH native isolated Agent',capabilities,probes,checks,
    ready:probes.every(p=>p.ok)&&!checks.some(c=>c.critical&&c.missing.length),inference_performed:false,course_blind_review:false,
    limits:['No continuous video/audio ingress is implemented by this runner.','Attachment ingress does not prove a model saw an image.']};
  const dir=join(course_path,'project','qa','review-capabilities');await mkdir(dir,{recursive:true});
  await writeFile(join(dir,packet.run_id+'.json'),JSON.stringify(receipt,null,2),{mode:0o600});
  if(strict&&!receipt.ready){const error=Error('REVIEW_CAPABILITY_MISSING: '+checks.filter(c=>c.critical&&c.missing.length).map(c=>c.id+'='+c.missing.join(',')).join('; '));error.capability_preflight=receipt;error.execution_phase='preflight';error.model_invoked=false;throw error;}
  return receipt;
}
