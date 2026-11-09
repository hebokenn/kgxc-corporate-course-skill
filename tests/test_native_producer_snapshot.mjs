import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const electron='/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness';
test('installed native producer QA snapshots preserve the original dispatch, history and later ordinary behavior',{skip:!existsSync(electron)},()=>{
  const output=execFileSync(electron,[fileURLToPath(new URL('./fixtures/native_producer_snapshot.mjs',import.meta.url))],{env:{...process.env,ELECTRON_RUN_AS_NODE:'1'},encoding:'utf8',timeout:30000});
  const value=JSON.parse(output.trim().split('\n').at(-1));
  assert.equal(value.ok,true);assert.equal(value.network_inference_calls,0);assert.ok(value.excluded_history_count>0);
  for(const key of ['config_preserved','signal_preserved','system_identity_preserved','other_agent_unchanged','next_ordinary_turn_restored','consecutive_qa_restored','automatic_time_context_excluded','native_skill_catalog_suppressed','native_skill_catalog_restored','forged_catalog_rejected','pending_input_retained','late_user_stopped','unknown_execution_rejected','current_developer_fail_closed'])assert.equal(value[key],true,key);
  assert.equal(value.audit_scope,'producer-qa-snapshot');
});
