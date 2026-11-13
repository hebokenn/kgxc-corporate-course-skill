import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {reviewResultEnvelope,freezeReviewInput} from '../plugin/review-input-boundary.mjs';
import {REVIEWER_PROMPT,SUPERVISOR_PROMPT} from '../plugin/isolated-review-agent.mjs';

const binding={operation_id:'frozen-operation',execution_sha256:'a'.repeat(64)},receipt={protocol:'synthetic-native-boundary',registration_bound:true,boundary_observed:true,binding};
test('host fills only an absent binding and preserves the raw model body',()=>{
  const raw={summary:'synthetic body',passed:true,findings:[]},envelope=reviewResultEnvelope(raw,{binding,receipt,audit:{id:'actual-native-id'}});
  assert.equal(Object.hasOwn(raw,'binding'),false);assert.deepEqual(envelope.binding,binding);
  assert.equal(envelope.agent_audit.binding_host.source,'host-attached-missing');
  assert.match(envelope.agent_audit.binding_host.observation_scope,/not final HTTP bytes/);
  for(const value of [null,false,0,'',undefined,{...binding,operation_id:'wrong'}])assert.throws(()=>reviewResultEnvelope({...raw,binding:value},{binding,receipt,audit:{}}),/错误的成果绑定/);
  const supplied={...raw,binding:{execution_sha256:binding.execution_sha256,operation_id:binding.operation_id}};
  assert.equal(reviewResultEnvelope(supplied,{binding,receipt,audit:{}}).agent_audit.binding_host.source,'model-present-verified');
});
test('host binding requires the exact observed frozen receipt and never accepts historical failures',()=>{
  const raw={summary:'synthetic body'};
  for(const proof of [null,{...receipt,registration_bound:false},{...receipt,registration_bound:1},{...receipt,boundary_observed:false},{...receipt,binding:{...binding,operation_id:'different'}}]){
    assert.throws(()=>reviewResultEnvelope(raw,{binding,receipt:proof,audit:{}}),/调用边界/);
  }
  const old={binding:null,error:'historically rejected'};
  assert.throws(()=>reviewResultEnvelope(old,{binding,receipt,audit:{}}),/错误的成果绑定/);
  assert.deepEqual(old,{binding:null,error:'historically rejected'});
  const original={binding:{...binding},input:{text:'frozen text'}};const frozen=freezeReviewInput(original);original.binding.operation_id='changed';
  assert.equal(frozen.binding.operation_id,'frozen-operation');assert.ok(Object.isFrozen(frozen.binding));
});
test('reviewer and supervisor contracts request body without copying host binding',()=>{
  for(const prompt of [REVIEWER_PROMPT,SUPERVISOR_PROMPT]){assert.match(prompt,/不复制 binding 或 agent_audit/);assert.doesNotMatch(prompt,/binding:本轮原样绑定/);}
});
const electron='/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness';
test('installed native prepared streams bind exact owned input and reject tampering without network inference',{skip:!existsSync(electron)},()=>{
  const output=execFileSync(electron,[fileURLToPath(new URL('./fixtures/native_review_host_binding.mjs',import.meta.url))],{env:{...process.env,ELECTRON_RUN_AS_NODE:'1'},encoding:'utf8',timeout:30000});
  const result=JSON.parse(output.trim().split('\n').at(-1));
  assert.equal(result.ok,true);assert.equal(result.network_inference_calls,0);
  for(const key of ['missing_binding_attached','wrong_and_null_rejected','native_input_tamper_rejected','downstream_request_tamper_rejected','raw_and_envelope_separate','durable_image_refs_exact','other_agent_unchanged','frozen_binding_not_late_current'])assert.equal(result[key],true,key);
});
