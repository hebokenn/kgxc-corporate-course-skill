import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const electron='/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness';
test('installed DSH Agent services enforce fresh contexts, empty executors and no original-source leakage before inference',{skip:!existsSync(electron)},()=>{
  const output=execFileSync(electron,[fileURLToPath(new URL('./fixtures/native_review_contract.mjs',import.meta.url))],{env:{...process.env,ELECTRON_RUN_AS_NODE:'1'},encoding:'utf8',timeout:30000});
  const result=JSON.parse(output.trim().split('\n').at(-1));
  assert.equal(result.ok,true);assert.equal(result.network_inference_calls,0);assert.equal(result.synthetic_streams,4);assert.equal(result.global_injectors_executed,0);assert.equal(new Set(result.independent_ids).size,4);
  assert.ok(result.registered_local_tools.includes('spawn_teammate'));assert.ok(result.registered_local_tools.includes('native_late_local'));
  assert.ok(result.suppressed_context_names.includes('team:identity'));assert.ok(result.suppressed_context_names.includes('working-directory:current'));
  assert.equal(result.normal_agent_context_unchanged,true);assert.equal(result.local_tool_executions,0);
  assert.equal(result.storyboard_navigation_evidence_contract,true);
});
