import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const electron='/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness';
test('native managed work/QA/work preserves verified catalogs, tools, current results and owned jobs',{skip:!existsSync(electron)},()=>{
  const output=execFileSync(electron,[fileURLToPath(new URL('./fixtures/native_producer_work_snapshot.mjs',import.meta.url))],{env:{...process.env,ELECTRON_RUN_AS_NODE:'1'},encoding:'utf8',timeout:30000});
  const value=JSON.parse(output.trim().split('\n').at(-1));assert.equal(value.ok,true);assert.equal(value.network_inference_calls,0);assert.deepEqual(value.tools_per_step,[51,51]);assert.equal(value.synthetic_file_reads,1);assert.equal(value.verified_jobs,3);
  for(const key of ['current_tool_result_preserved','current_course_context_preserved','native_background_notices_preserved','native_background_output_collected','native_background_returned_idle','unverified_job_notices_rejected','pending_unverified_jobs_rejected','pending_native_job_verified','pending_expired_job_retained','old_pending_notice_excluded','history_prefix_unchanged','config_system_signal_preserved','other_agent_unchanged','ordinary_turn_restored','late_user_stopped_and_retained','abort_stopped','developer_failed_before_dispatch'])assert.equal(value[key],true,key);
  for(const key of ['same_agent','native_full_preserved','native_empty_qa_suppressed','unchanged_catalog_derived','native_full_refresh_preserved','projection_only_no_log_write','native_job_output_and_idle','forged_full_empty_rejected','pending_forged_retained','tools_restored'])assert.equal(value.combined_work_qa_work[key],true,key);
  assert.deepEqual(value.repeat_thresholds,[3,5,8]);for(const key of ['native_repeat_reminders_preserved','pending_repeat_normally_claimed','forged_foreign_consumed_repeats_rejected'])assert.equal(value[key],true,key);
});
