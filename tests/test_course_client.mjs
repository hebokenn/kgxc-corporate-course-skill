import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

async function client(fetcher,{pending,chatOpen,updateDismissed}={}){
  let index=0,states=[],effects=[],cleanups=[],clickListener;const entries=[],animation=[],dependencies=[],listeners=new Map();
  const react={createElement:(type,props,...children)=>({type,props:{...props,children}}),
    useState:initial=>{const i=index++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],value=>{states[i]=typeof value==='function'?value(states[i]):value;}];},
    useRef:initial=>{const i=index++;return states[i]??=( {current:initial} );},
    useEffect:(fn,deps)=>{const i=index++,before=dependencies[i];if(!before||!deps||deps.some((value,j)=>!Object.is(value,before[j]))){dependencies[i]=deps;effects.push(()=>{cleanups[i]?.();cleanups[i]=fn();});}}};
  const storage=new Map([['kgxc-active-course','/tmp/old-global-course']]);let plugin;
  if(updateDismissed)storage.set('kgxc-update-dismissed',updateDismissed);
  if(chatOpen!==undefined)storage.set('kgxc-chat-open',String(chatOpen));
  const browser={__ModuleLoader__:{load:spec=>{plugin=spec.factory(()=>react);}},addEventListener:(name,fn)=>{if(!listeners.has(name))listeners.set(name,new Set());listeners.get(name).add(fn);},removeEventListener:(name,fn)=>listeners.get(name)?.delete(fn)};
  vm.runInNewContext(await readFile(new URL('../plugin/client.js',import.meta.url),'utf8'),{
    window:browser,fetch:fetcher,localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    URL,location:{origin:'dsh-app://app'},crypto:globalThis.crypto,setTimeout,clearTimeout,
    document:{addEventListener:(name,fn)=>{if(name==='click')clickListener=fn;},removeEventListener:()=>{}},requestAnimationFrame:fn=>animation.push(fn),
  });
  const selection={sessionId:'new-session'};
  const ctx={uiWorkspace:{selection:{getSnapshot:()=>selection}},effect:(fn,title)=>{if(title==='kgxc-course: submit last explicit choice')fn();},slots:{inject:(_name,fn)=>fn(),register:(options,component)=>{entries.push({options,component});return()=>{};}}};
  plugin.apply(ctx);
  const scoped=entries.find(x=>x.options.name==='kgxc.workspace');
  const props={ctx,sessionId:'new-session',useSession:()=>({openState:'ready'}),useSessionStatus:selector=>selector(new Map([['new-session',{pendingInteraction:pending}]])),renderSlot:()=>null};
  const panel=scoped.component(props).type;
  return {ctx,selection,entries,storage,states,setPending:value=>{pending=value;},click:event=>clickListener(event),message:async event=>{for(const fn of [...listeners.get('message')||[]])await fn(event);},animate:()=>{for(const fn of animation.splice(0))fn();},render:()=>{index=0;return panel(props);},renderChild:node=>{index=100;return node.type(node.props);},flush:()=>{for(const effect of effects.splice(0))effect();},unmount:()=>{for(const cleanup of cleanups.splice(0))cleanup?.();}};
}
const response=value=>({ok:true,json:async()=>value});
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
test('plugin reload refreshes a stale connection token once before retrying the same read request',async()=>{
  const tokens=[],bodies=[];let metadata=0,contexts=0;
  const app=await client(async(url,options)=>{
    if(url.endsWith('/meta')){metadata++;return response({ok:true,token:metadata===1?'old-token':'current-token'});}
    if(url.endsWith('/context')){contexts++;tokens.push(options.headers['X-KGXC-Token']);bodies.push(options.body);if(contexts===1)return {ok:false,status:403,json:async()=>({ok:false,error:'请重新打开制课工作台'})};return response({ok:true,ready:true,course_path:null});}
    return response({ok:true,courses:[]});
  });
  app.render();app.flush();await settle();
  assert.deepEqual(tokens,['old-token','current-token']);assert.equal(bodies[0],bodies[1]);assert.equal(app.states[2],'');app.unmount();
});
function nodes(node){return Array.isArray(node)?node.flatMap(nodes):node&&typeof node==='object'?[node,...nodes(node.props?.children)]:[];}
function button(tree,label){return nodes(tree).find(node=>node.type==='button'&&node.props.children.includes(label));}
async function loadedClient({deliveryChoice,expired=false,cleanupError,courseOwner}={}){
  const calls=[],course={ok:true,course_path:'/tmp/current-course',workbench_url:'http://127.0.0.1:1234',workflow:{stage:'final'}},saved={...course,delivery_only:true,delivery:{course_id:'fixture',title:'本课',delivery_root:'/tmp/desktop/本课',files:[],cleanup_status:'retained',...(deliveryChoice?{cleanup_decision:{choice:deliveryChoice}}:{})}};
  const app=await client(async(url,options)=>{const data=options?.body?JSON.parse(options.body):undefined;calls.push({url,data});
    return response(url.endsWith('/meta')?{ok:true,token:'test'}:url.endsWith('/context')?{ok:true,ready:true,course_path:course.course_path}:data?.name==='kgxc_course_resume'?course:data?.action==='course-session'?{ok:true,session_id:courseOwner}:data?.action==='attach-course'?{ok:true,session_id:data.arguments.session_id}:data?.action==='workbench_live'?{ok:true,alive:!expired}:data?.action==='deliver'?saved:data?.action==='cleanup_preview'?(cleanupError?{ok:false,error:cleanupError}:{ok:true,preview:{request_id:'current-inventory',file_count:12,bytes:12345,groups:[{label:'逐字稿与小样',files:12,bytes:12345}]}}):data?.action==='retention'?saved:{ok:true,courses:[]});
  });
  app.render();app.flush();await settle();const tree=app.render(),sender={postMessage:()=>{}};
  const native=nodes(tree).find(node=>node.type==='kgxc-studio-view');assert.equal(native.props.class,'kgxc-frame kgxc-native');assert.equal(native.props.className,undefined);native.props.ref.current={contentWindow:sender};app.flush();await settle();
  return {app,calls,course,sender,event:data=>({source:sender,origin:'http://127.0.0.1:1234',data:{course_path:course.course_path,...data}})};
}

test('the real DSH client ignores the global recent course in a fresh session and keeps the native conversation entry',async()=>{
  const calls=[];const app=await client(async(url,options)=>{const data=options?.body?JSON.parse(options.body):undefined;calls.push({url,data});
    return response(url.endsWith('/meta')?{ok:true,token:'test'}:url.endsWith('/context')?{ok:true,ready:true,course_path:null}:{ok:true,courses:[{course_id:'old',course_path:'/tmp/old-global-course',title:'旧课'}]});});
  app.render();app.flush();await settle();
  assert.equal(app.states[1],null);assert.equal(app.states[3],false);assert.equal(app.states[2],'');
  assert.equal(calls.some(call=>call.data?.name==='kgxc_course_resume'),false);
  assert.ok(app.entries.some(entry=>entry.options.name==='conversation.session.header.actions'));
  assert.equal(app.entries.find(entry=>entry.options.key==='kgxc-course').options.children['kgxc.workspace'].scope,'session-maybe');
  app.unmount();
});
test('an old session resume arriving after navigation cannot repopulate its unmounted editor',async()=>{
  let finish;const app=await client(async(url,options)=>{
    const data=options?.body?JSON.parse(options.body):undefined;
    if(data?.name==='kgxc_course_resume')return new Promise(resolve=>{finish=()=>resolve(response({ok:true,course_path:'/tmp/old',workbench_url:'http://127.0.0.1:1234'}));});
    return response(url.endsWith('/meta')?{ok:true,token:'test'}:url.endsWith('/context')?{ok:true,ready:true,course_path:'/tmp/old'}:{ok:true,courses:[]});
  });
  app.render();app.flush();await settle();assert.ok(finish,app.states[2]);
  app.selection.sessionId='other-session';app.unmount();finish();await settle();
  assert.equal(app.states[1],null);
});

test('only an explicit click on the last single-choice question submits; defaults, earlier pages and stale cards do not',async()=>{
  const app=await client(async()=>response({ok:true}));let sent=0,page='1 / 3',identity='question-0',checked='false';
  const submit={disabled:false,click:()=>{sent++;submit.disabled=true;}};
  const footer={get textContent(){return page;},querySelectorAll:()=>[{},submit]};
  const section={getAttribute:()=>identity};
  const card={isConnected:true,querySelector:name=>name==='footer'?footer:section};
  const option={disabled:false,closest:()=>card,getAttribute:()=>checked};
  const target={closest:()=>option};
  app.animate();assert.equal(sent,0); // Opening a preselected card never sends it.
  app.click({isTrusted:true,target});page='3 / 3';identity='question-2';checked='true';app.animate();
  assert.equal(sent,0); // The second-to-last click must not submit after native auto-advance.
  app.click({isTrusted:false,target});app.animate();assert.equal(sent,0);
  app.click({isTrusted:true,target});identity='other-question';app.animate();assert.equal(sent,0);
  identity='question-2';app.click({isTrusted:true,target});app.animate();assert.equal(sent,1);
  app.click({isTrusted:true,target});app.animate();assert.equal(sent,1); // Native busy state blocks repeats.
  app.click({isTrusted:true,target:{closest:()=>null}});app.animate();assert.equal(sent,1); // Multi-select is not single-click submission.
});

test('a native pending question reopens a collapsed chat using the host session status',async()=>{
  const app=await client(async(url)=>response(url.endsWith('/meta')?{ok:true,token:'test'}:url.endsWith('/context')?{ok:true,ready:true,course_path:null}:{ok:true,courses:[]}),{pending:{kind:'question'},chatOpen:false});
  app.render();app.flush();await settle();
  assert.equal(app.storage.get('kgxc-chat-open'),'true');app.unmount();
});

test('delivery opens the retention dialog, closing it preserves files, and only an explicit current choice is sent',async()=>{
  const {app,calls,event}=await loadedClient();
  await app.message(event({type:'kgxc-editor-request',id:'save',action:'deliver'}));await settle();
  let dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');assert.ok(dialog);
  let ui=app.renderChild(dialog);assert.ok(nodes(ui).some(node=>node.props.role==='dialog'));
  assert.equal(calls.some(call=>call.data?.action==='retention'),false);
  button(ui,'关闭并保留').props.onClick();assert.equal(nodes(app.render()).some(node=>node.type?.name==='RetentionDialog'),false);
  assert.equal(calls.some(call=>call.data?.action==='retention'),false);
  // Non-destructive choices need no cleanup inventory.
  const delivery=nodes(app.render()).find(node=>node.type?.name==='DeliveryView');await delivery.props.onRetention();await settle();
  dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');ui=app.renderChild(dialog);
  button(ui,'稍后提醒我').props.onClick();await settle();
  assert.deepEqual(calls.filter(call=>call.data?.action==='retention').map(call=>call.data),[{action:'retention',session_id:'new-session',course_path:'/tmp/current-course',choice:'later'}]);assert.equal(calls.some(call=>call.data?.action==='cleanup_preview'),false);app.unmount();
});

test('cleanup requires a second trusted click and explicit keep suppresses the automatic reminder',async()=>{
  const {app,calls,event}=await loadedClient();await app.message(event({type:'kgxc-editor-request',id:'save',action:'deliver'}));await settle();
  let dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');let ui=app.renderChild(dialog);
  assert.equal(calls.some(call=>call.data?.action==='cleanup_preview'),false);
  await button(ui,'查看并选择清理').props.onClick();await settle();assert.equal(calls.some(call=>call.data?.action==='retention'),false);
  dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');ui=app.renderChild(dialog);const confirm=button(ui,'确认清理所列过程文件');assert.ok(confirm);
  confirm.props.onClick({isTrusted:false});await settle();assert.equal(calls.some(call=>call.data?.action==='retention'),false);
  confirm.props.onClick({isTrusted:true});await settle();assert.equal(calls.find(call=>call.data?.action==='retention').data.choice,'delete-process-files');app.unmount();
  const kept=await loadedClient({deliveryChoice:'keep'});await kept.app.message(kept.event({type:'kgxc-editor-request',id:'save',action:'deliver'}));await settle();
  assert.equal(nodes(kept.app.render()).some(node=>node.type?.name==='RetentionDialog'),false);assert.equal(kept.calls.some(call=>call.data?.action==='cleanup_preview'),false);kept.app.unmount();
});

test('saved unanswered decisions request one native question and reject another course state',async()=>{
  const {app,calls,event}=await loadedClient();
  await app.message(event({type:'kgxc-studio-state',course_path:'/tmp/other-course',revision:7,waiting_decisions:[{id:'other'}]}));app.render();app.flush();await settle();
  assert.equal(calls.some(call=>call.data?.arguments?.target_stage==='questions'),false);
  const state={type:'kgxc-studio-state',revision:8,waiting_decisions:[{id:'D-03',question:'缺口怎么处理'}]};
  await app.message(event(state));app.render();app.flush();await settle();
  await app.message(event(state));app.render();app.flush();await settle();
  const requests=calls.filter(call=>call.data?.arguments?.target_stage==='questions');assert.equal(requests.length,1);assert.ok(requests[0].data.arguments.instruction.includes('D-03'));assert.equal(app.storage.get('kgxc-chat-open'),'true');app.unmount();
});


test('stage navigation wakes an expired workbench without waiting for a dead iframe or starting a model',async()=>{
 const {app,calls,sender}=await loadedClient({expired:true});const before=nodes(app.render()).find(n=>n.type==='kgxc-studio-view');
 const tab=nodes(app.render()).find(n=>n.props?.role==='tab'&&nodes(n).some(c=>c.type==='strong'&&c.props.children.includes('分镜')));
 assert.ok(tab,'全课分镜阶段必须可以独立打开');
 await tab.props.onClick();await settle();const after=nodes(app.render()).find(n=>n.type==='kgxc-studio-view');
 assert.match(after.props.src,/stage=storyboard/);assert.notEqual(before.props.key,after.props.key);
 assert.equal(calls.filter(c=>c.data?.name==='kgxc_course_resume').length,2);
 assert.equal(calls.some(c=>c.data?.action==='stage'),false);app.unmount();
});

test('opening a saved folder is available in the delivery view and retention dialog without arbitrary paths',async()=>{
  const {app,calls,event}=await loadedClient();await app.message(event({type:'kgxc-editor-request',id:'save',action:'deliver'}));await settle();
  const dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');const ui=app.renderChild(dialog);
  assert.ok(nodes(ui).some(n=>n.props?.children?.includes('保存位置：/tmp/desktop/本课')));
  await button(ui,'打开保存文件夹').props.onClick();
  const delivery=nodes(app.render()).find(node=>node.type?.name==='DeliveryView');
  const page=app.renderChild(delivery);await button(page,'打开保存文件夹').props.onClick();
  assert.deepEqual(calls.filter(c=>c.data?.action==='open_delivery').map(c=>c.data),[
    {action:'open_delivery',session_id:'new-session',course_path:'/tmp/current-course'},{action:'open_delivery',session_id:'new-session',course_path:'/tmp/current-course'}]);
  assert.equal(calls.some(c=>c.data?.action==='cleanup_preview'||c.data?.action==='retention'),false);app.unmount();
});

test('top navigation splits body and post-production without opening a new workflow gate',async()=>{
  const {app,calls}=await loadedClient({expired:true});
  const tab=label=>nodes(app.render()).find(n=>n.props?.role==='tab'&&nodes(n).some(c=>c.type==='strong'&&c.props.children.includes(label)));
  assert.equal(tab('整课交付'),undefined);
  for(const [label,phase] of [['画面与配音','body'],['后期与成片','post']]){
    await tab(label).props.onClick();await settle();
    const frame=nodes(app.render()).find(n=>n.type==='kgxc-studio-view');
    assert.match(frame.props.src,new RegExp('stage=final&phase='+phase));
    assert.equal(tab(label).props['aria-selected'],true);
    assert.equal(app.storage.get('kgxc-final-phase:/tmp/current-course'),phase);
  }
  assert.equal(calls.some(c=>c.data?.action==='stage'||c.data?.action==='stage-confirmation-request'),false);
  app.unmount();
});

test('studio marks confirmation visible only for the matching live right-side question',async()=>{
  const {app,sender,event}=await loadedClient();
  const messages=[];sender.postMessage=data=>{if(data.type==='kgxc-editor-confirmation')messages.push(data);};
  const q={id:'kgxc-confirm-'+'a'.repeat(36),stage:'final',label:'成片'};
  await app.message(event({type:'kgxc-studio-state',stage:'final',revision:2,pending_confirmations:[q]}));
  const change=p=>{app.setPending(p);app.render();app.flush();return messages.at(-1)?.status;};
  const native={kind:'question',sessionId:'new-session',questions:[{id:q.id}]};
  assert.notEqual(change({...native,questions:[{id:'other'}]}),'visible');
  assert.notEqual(change({...native,sessionId:'other-session'}),'visible');
  assert.notEqual(change({...native,review:[]}),'visible');
  assert.equal(change(native),'visible');
  assert.notEqual(change(undefined),'visible');
  app.unmount();
});

test('a cleanup inventory warning appears once and does not block retaining the saved course',async()=>{
  const {app,calls,event}=await loadedClient({cleanupError:'工程顶层还有未识别文件'});
  await app.message(event({type:'kgxc-editor-request',id:'save',action:'deliver'}));await settle();
  let dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');let ui=app.renderChild(dialog);
  await button(ui,'查看并选择清理').props.onClick();await settle();
  dialog=nodes(app.render()).find(node=>node.type?.name==='RetentionDialog');ui=app.renderChild(dialog);
  assert.equal(nodes(ui).filter(n=>n.props?.children?.some(c=>typeof c==='string'&&c.includes('工程顶层还有未识别文件'))).length,1);
  assert.equal(button(ui,'保留全部（推荐）').props.disabled,false);
  await button(ui,'保留全部（推荐）').props.onClick();await settle();
  assert.equal(calls.find(c=>c.data?.action==='retention').data.choice,'keep');app.unmount();
});

test('persistent toolbar chat control survives collapse, reload and repeated toggles outside the studio',async()=>{
  for(const initiallyOpen of [true,false]){
    const app=await client(async(url)=>response(url.endsWith('/meta')?{token:'test'}:url.endsWith('/context')?{ready:true,course_path:null}:{courses:[]}),{chatOpen:initiallyOpen});
    app.render();app.flush();await settle();
    for(let i=0;i<4;i++){
      const tree=app.render(),toolbar=nodes(tree).find(n=>n.props.className?.split(' ').includes('kgxc-switch')),toggle=nodes(toolbar).find(n=>n.props.className==='kgxc-chat-toggle');
      assert.ok(toggle);const before=toggle.props['aria-expanded'];
      assert.equal(nodes(tree).some(n=>n.props.id==='kgxc-ai-chat'),before);
      assert.equal(nodes(tree).filter(n=>n.props.className==='kgxc-editor').flatMap(nodes).includes(toggle),false);
      toggle.props.onClick();assert.equal(app.storage.get('kgxc-chat-open'),String(!before));
      assert.equal(nodes(app.render()).find(n=>n.props.className==='kgxc-chat-toggle').props['aria-expanded'],!before);
    }
    app.unmount();
  }
});

test('stable update notice is non-blocking, offers an in-app download and dismisses only that version',async()=>{
 const update={version:'0.9.0',release_url:'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v6.9.0'};
 const app=await client(async url=>response(url.endsWith('/updates')?{ok:true,update}:url.endsWith('/meta')?{token:'test'}:url.endsWith('/context')?{ready:true,course_path:null}:{courses:[]}));
 app.render();app.flush();await settle();let tree=app.render();
 assert.ok(nodes(tree).some(n=>n.props.className==='kgxc-update-notice'));
 assert.ok(button(tree,'下载更新'));assert.equal(nodes(tree).some(n=>n.type==='a'),false);
 assert.ok(nodes(tree).some(n=>n.props.className==='kgxc-chat-toggle'));
 nodes(tree).find(n=>n.props['aria-label']==='忽略此版本更新提醒').props.onClick();
 assert.equal(app.storage.get('kgxc-update-dismissed'),update.version);assert.equal(nodes(app.render()).some(n=>n.props.className==='kgxc-update-notice'),false);app.unmount();
});
test('offline update check does not become a course error or prevent opening chat',async()=>{
 const app=await client(async url=>{if(url.endsWith('/updates'))throw Error('offline');return response(url.endsWith('/meta')?{token:'test'}:url.endsWith('/context')?{ready:true,course_path:null}:{courses:[]});},{chatOpen:false});
 app.render();app.flush();await settle();const tree=app.render();assert.equal(app.states[2],'');assert.equal(nodes(tree).some(n=>n.props.className==='kgxc-update-notice'),false);button(tree,'打开 AI 对话').props.onClick();assert.equal(app.storage.get('kgxc-chat-open'),'true');app.unmount();
});
test('dismissed version stays hidden across reopening but a later release is shown',async()=>{
 for(const version of ['0.9.0','0.9.1']){
  const app=await client(async url=>response(url.endsWith('/updates')?{update:{version,release_url:'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v6.9.1'}}:url.endsWith('/meta')?{token:'test'}:url.endsWith('/context')?{ready:true,course_path:null}:{courses:[]}),{updateDismissed:'0.9.0'});
  app.render();app.flush();await settle();assert.equal(nodes(app.render()).some(n=>n.props.className==='kgxc-update-notice'),version==='0.9.1');app.unmount();
 }
});

test('first-use course actions reopen the composer even when chat was collapsed',async()=>{
  const app=await client(async(url)=>response(url.endsWith('/meta')?{ok:true,token:'test'}:url.endsWith('/context')?{ok:true,ready:true,course_path:null}:{ok:true,courses:[]}),{chatOpen:false});
  app.render();app.flush();await settle();
  let tree=app.render();
  assert.ok(button(tree,'上传资料，开始做课'));
  assert.ok(button(tree,'描述课程，开始做课'));
  assert.equal(nodes(tree).some(node=>node.props.id==='kgxc-ai-chat'),false);
  button(tree,'上传资料，开始做课').props.onClick();
  tree=app.render();
  assert.equal(app.storage.get('kgxc-chat-open'),'true');
  assert.ok(nodes(tree).some(node=>node.props.id==='kgxc-ai-chat'));
  assert.equal(app.states[1],null,'opening an intake does not fabricate a course');
  app.unmount();
});

test('first-use native intake only inserts into an empty draft, then opens the owning session file picker',async()=>{
  const app=await client(async()=>response({ok:true}));
  const chat=app.entries.find(x=>x.options.name==='kgxc.chat').component;
  let draft='keep what I wrote',picks=[],insertions=[],handled=0;
  const scope={ctx:{conversation:{input:{canPickFiles:id=>id==='new-session',pickFiles:id=>picks.push(id)}}},sessionId:'new-session',
    useSession:()=>({blank:true}),useConversation:()=>({}),useSessions:()=>true,useInput:select=>select({draft}),
    inputActions:{captureInsertion:()=>({revision:1}),insertText:(text,span)=>{insertions.push([text,span]);return true;},submit:()=>assert.fail('must not submit')},
    renderFactorySlot:()=>null,onboarding:{sessionId:'new-session',mode:'upload'},onboardingHandled:()=>{handled++;}};
  app.renderChild({type:chat,props:scope});app.flush();await new Promise(resolve=>setTimeout(resolve,15));
  assert.deepEqual(picks,['new-session']);assert.deepEqual(insertions,[]);assert.equal(handled,1);
  draft='';scope.onboarding={sessionId:'new-session',mode:'describe'};
  app.renderChild({type:chat,props:scope});app.flush();await new Promise(resolve=>setTimeout(resolve,15));
  assert.match(insertions[0][0],/可编辑的大纲/);assert.equal(insertions[0][1].revision,1);assert.equal(handled,2);
  app.unmount();
});

test('GitHub updater appears only on this installed plugin detail and works without a course session',async()=>{
  const calls=[];
  const app=await client(async(url,options)=>{
    calls.push([url,options?.method]);
    return response(url.endsWith('/meta')?{ok:true,token:'test'}:{ok:true,status:'checked',update:{version:'9.0.1',release_url:'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v9.0.1'}});
  });
  const update=app.entries.find(x=>x.options.name==='plugins.detail.actions');
  assert.ok(update);
  const render=subject=>app.renderChild({type:update.component,props:{subject}});
  assert.equal(render({kind:'bundle',pkg:{name:'other-plugin'}}),null);
  assert.equal(render({kind:'row',pkg:{name:'kgxc-course-plugin'},row:{}}),null);
  assert.deepEqual(calls,[]);
  const own={kind:'bundle',pkg:{name:'kgxc-course-plugin'}};
  let tree=render(own);app.flush();
  button(tree,'检查 GitHub 更新').props.onClick();await settle();
  tree=render(own);
  assert.equal(calls.filter(([url,method])=>url.endsWith('/updates')&&method==='POST').length,1);
  assert.ok(button(tree,'下载更新'));assert.equal(nodes(tree).some(node=>node.type==='a'),false);
  app.unmount();
});

test('opening another course navigates to the existing session without rebinding the old session',async()=>{
  const {app,calls,sender,event}=await loadedClient({courseOwner:'course-b-session'}),opened=[];
  app.ctx.uiWorkspace.workspaces={list:{getSnapshot:()=>({items:[{workspaceId:'w',sessionIds:['new-session','course-b-session']}]})}};
  app.ctx.uiWorkspace.openSession=id=>opened.push(id);app.ctx.layout={selectPanel:()=>{}};
  const request=nodes(app.render()).find(n=>n.type==='select'&&n.props.id==='kgxc-course').props.onChange;
  sender.postMessage=data=>{if(data.type==='kgxc-editor-leave')void app.message(event({type:'kgxc-editor-leave-result',id:data.id}));};
  request({target:{value:'/tmp/course-b'}});await settle();
  assert.deepEqual(opened,['course-b-session']);assert.equal(calls.some(x=>x.data?.action==='attach-course'||x.data?.action==='bind'),false);
  app.unmount();
});
test('browsing an unbound course does not create a session; explicit separate open attaches only the new ID',async()=>{
  const {app,calls,sender,event}=await loadedClient(),opened=[],created=[];
  app.ctx.uiWorkspace.workspaces={list:{getSnapshot:()=>({items:[{workspaceId:'w',sessionIds:['new-session']}]})}};
  app.ctx.uiWorkspace.sessions={create:async args=>{created.push(args);return 'separate-session';}};
  app.ctx.uiWorkspace.openSession=id=>opened.push(id);app.ctx.layout={selectPanel:()=>{}};
  sender.postMessage=data=>{if(data.type==='kgxc-editor-leave')void app.message(event({type:'kgxc-editor-leave-result',id:data.id}));};
  nodes(app.render()).find(n=>n.type==='select'&&n.props.id==='kgxc-course').props.onChange({target:{value:'/tmp/course-b'}});await settle();
  assert.deepEqual(created,[]);assert.deepEqual(opened,[]);
  button(app.render(),'为该课程打开独立对话').props.onClick();await settle();
  assert.equal(created.length,1);assert.deepEqual(opened,['separate-session']);
  assert.equal(calls.find(x=>x.data?.action==='attach-course').data.arguments.session_id,'separate-session');
  assert.equal(calls.some(x=>x.data?.action==='bind'&&x.data?.arguments?.select),false);
  app.unmount();
});

test('top right update action is present before opening a course and only sends one manual request',async()=>{
  let posts=0,finish;
  const app=await client(async(url,options)=>{
    if(url.endsWith('/meta'))return response({ok:true,token:'test'});
    if(url.endsWith('/context'))return response({ok:true,ready:true,course_path:null});
    if(url.endsWith('/updates')&&options.method==='POST'){
      posts++;
      return new Promise(resolve=>{finish=()=>resolve(response({ok:true,status:'checked',update:null}));});
    }
    return response({ok:true,courses:[]});
  });
  try {
    app.render();app.flush();await settle();
    const tree=app.render(),bar=nodes(tree).find(n=>n.props.className?.split(' ').includes('kgxc-switch'));
    const update=button(bar,'检查更新');
    assert.equal(bar.props.children.at(-1),update);
    assert.ok(bar.props.className.split(' ').includes('kgxc-window-drag'));
    assert.equal(nodes(tree).some(n=>n.type==='kgxc-studio-view'),false);
    update.props.onClick();update.props.onClick();await settle();
    assert.equal(posts,1);
    assert.equal(button(app.render(),'正在检查…').props.disabled,true);
    finish();await settle();
    assert.ok(button(app.render(),'检查更新'));
    assert.ok(nodes(app.render()).some(n=>n.props.role==='status'&&n.props.children.includes('已是最新版。')));
  }finally{app.unmount();}
});


test('macOS window drag CSS only scopes the toolbar and excludes interactive controls',async()=>{
  const source=await readFile(new URL('../plugin/client.js',import.meta.url),'utf8');
  assert.match(source,/html\[data-platform="darwin"\]:not\(\[data-fullscreen\]\) \.kgxc-window-drag\{-webkit-app-region:drag;app-region:drag\}/);
  assert.match(source,/\.kgxc-window-drag :is\(button,select,input,textarea,a,label,\[role="button"\],\[tabindex\],\[contenteditable\]\)\{-webkit-app-region:no-drag;app-region:no-drag\}/);
  assert.equal((source.match(/className:'[^']*kgxc-window-drag/g)||[]).length,1);
});

test('plugin detail offers verified in-app download progress then explicit restart, with fallback only on failure',async()=>{
  const calls=[],update={version:'9.0.1',release_url:'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v9.0.1'};
  let phase='idle',attempts=0;
  const app=await client(async(url,options)=>{
    const body=options?.body&&JSON.parse(options.body);calls.push({url,body});
    if(url.endsWith('/meta'))return response({ok:true,token:'test'});
    if(url.endsWith('/updates'))return response({ok:true,status:'checked',update});
    if(body?.action==='download'){attempts++;phase=attempts===1?'failed':'downloading';}
    if(body?.action==='install')phase='installing';
    return response({ok:true,phase,version:update.version,received:phase==='downloading'?25:0,total:100,...(phase==='failed'?{error:'下载校验失败'}:{})});
  });
  const own={kind:'bundle',pkg:{name:'kgxc-course-plugin'}},detail=app.entries.find(x=>x.options.name==='plugins.detail.actions').component;
  const render=()=>app.renderChild({type:detail,props:{subject:own}});
  let tree=render();app.flush();button(tree,'检查 GitHub 更新').props.onClick();await settle();
  tree=render();assert.equal(nodes(tree).some(n=>n.type==='a'),false);button(tree,'下载更新').props.onClick();await settle();
  tree=render();assert.equal(nodes(tree).find(n=>n.type==='a').props.href,update.release_url);
  button(tree,'重试下载').props.onClick();await settle();tree=render();app.flush();
  assert.equal(nodes(tree).find(n=>n.type==='progress').props.value,25);
  assert.equal(calls.some(x=>x.body?.action==='install'),false);
  phase='ready';await new Promise(resolve=>setTimeout(resolve,500));tree=render();app.flush();
  await button(tree,'退出并安装').props.onClick();await settle();
  assert.equal(calls.filter(x=>x.body?.action==='install').length,1);assert.ok(nodes(render()).some(x=>x.props.children?.includes('请正常退出 DeepSeek Harness。更新完成后会自动重开；不用退出 Codex。')));
  app.unmount();
});
test('rate-limited update checks are not presented as latest installed',async()=>{
  const app=await client(async(url)=>response(url.endsWith('/meta')?{ok:true,token:'test'}:{ok:true,status:'unavailable',reason:'rate_limited'}));
  const detail=app.entries.find(x=>x.options.name==='plugins.detail.actions').component;
  const render=()=>app.renderChild({type:detail,props:{subject:{kind:'bundle',pkg:{name:'kgxc-course-plugin'}}}});
  let tree=render();app.flush();button(tree,'检查 GitHub 更新').props.onClick();await settle();tree=render();
  assert.ok(nodes(tree).some(x=>x.props.children?.some(v=>typeof v==='string'&&v.includes('限制更新检查频率'))));
  assert.equal(nodes(tree).some(x=>x.props.children?.includes('已是最新稳定版。')),false);app.unmount();
});

test('server busy leaves the downloaded package pending instead of opening the release page',async()=>{
  const app=await client(async(url,options)=>{
    const body=options?.body&&JSON.parse(options.body);
    if(url.endsWith('/meta'))return response({ok:true,token:'test'});
    if(body?.action==='install')return {ok:false,status:409,json:async()=>({ok:false,code:'busy',error:'课还没有停'})};
    return response({ok:true,phase:'ready',version:'9.0.1'});
  });
  const detail=app.entries.find(x=>x.options.name==='plugins.detail.actions').component;
  const render=()=>app.renderChild({type:detail,props:{subject:{kind:'bundle',pkg:{name:'kgxc-course-plugin'}}}});
  render();app.flush();await settle();
  await button(render(),'退出并安装').props.onClick();await settle();
  const tree=render();
  assert.ok(nodes(tree).some(x=>x.props.children?.includes('更新已下载，等当前工作结束后再安装。')));
  assert.equal(nodes(tree).some(x=>x.type==='a'),false);
  assert.ok(button(tree,'退出并安装'));app.unmount();
});

test('course toolbar shows the corporate logo without making it draggable as an image',async()=>{
  const app=await client(async()=>response({ok:true}));
  const tree=nodes(app.render());
  const toolbar=tree.find(n=>n.props.className==='kgxc-switch kgxc-window-drag');
  const logo=nodes(toolbar).find(n=>n.type==='img'&&n.props.alt==='酷果星创');
  assert.ok(logo);assert.equal(logo.props.draggable,false);
  assert.match(logo.props.src,/^data:image\/png;base64,/);
  assert.ok(button(toolbar,'检查更新'));
  app.unmount();
});

test('toolbar leaves the host-provided titlebar space for collapsed and drawer sidebar modes', async()=>{
  const src=await readFile(new URL('../plugin/client.js',import.meta.url),'utf8');
  assert.match(src,/\.kgxc-switch\{padding:12px 24px;padding-inline-start:max\(24px,var\(--dsh-frame-leading-clearance,0px\)\)/);
  assert.match(src,/\.kgxc-switch\{display:flex;flex-wrap:wrap/);
  assert.match(src,/\.kgxc-window-drag\{-webkit-app-region:drag/);
});
