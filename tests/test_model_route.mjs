import test from 'node:test';
import assert from 'node:assert/strict';
import {requireRoute,sessionCallAudit} from '../plugin/isolated-review-agent.mjs';
test('native and optional custom routes are accepted without a shared model default',()=>{
 for(const route of [{provider:'deepseek',model:'deepseek-chat'},{provider:'codex-chatgpt',model:'gpt-6.1-sol'},{provider:'custom',model:'local-model'}])assert.deepEqual(requireRoute(route),route);
 for(const route of [null,{}, {provider:'',model:'m'},{provider:'p',model:' '}])assert.throws(()=>requireRoute(route),/有效/);
});
test('an admitted native route cannot silently switch provider or model',()=>{
 const route={provider:'deepseek',model:'deepseek-chat'};
 assert.throws(()=>requireRoute({provider:'other',model:route.model},route),/绑定不一致/);
 assert.throws(()=>requireRoute({provider:route.provider,model:'other'},route),/绑定不一致/);
 const agent={session:{id:'s',log:[{seq:1,type:'request/header',data:{header:{config:{provider:'other',model:'other'}}}}]}};
 assert.throws(()=>sessionCallAudit(agent,route,{role:'producer'}),/绑定不一致/);
});
