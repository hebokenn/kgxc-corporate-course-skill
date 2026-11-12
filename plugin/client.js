window.__ModuleLoader__.load({
  id:'kgxc-course-plugin',
  factory:require=>{
    const {createElement:h,useState,useEffect,useRef}=require('react');
    const API='/api/kgxc-course'; let token;
    async function request(path,data,retried=false){
      if(data&&!token)token=(await request('/meta')).token;
      const response=await fetch(API+path,data?{method:'POST',headers:{'Content-Type':'application/json','X-KGXC-Token':token},body:JSON.stringify(data)}:{});
      if(data&&response.status===403&&!retried){token=(await request('/meta')).token;return request(path,data,true);}
      const value=await response.json();if(!response.ok||value.ok===false)throw Error(value.error||'操作失败');return value;
    }
    const call=(name,args={})=>request('/call',{name,arguments:args});
    function defineNativeStudio(){
      if(typeof customElements==='undefined'||customElements.get('kgxc-studio-view'))return;
      customElements.define('kgxc-studio-view',class extends HTMLElement{
        static observedAttributes=['src'];
        constructor(){super();this.attachShadow({mode:'open'});this.epoch=0;this.messages=[];this.contentWindow={postMessage:(data,origin)=>{if(origin!==new URL(this.getAttribute('src')).origin)return;if(this.view)this.view.receive(data);else this.messages.push(data);}};}
        connectedCallback(){void this.open();}
        attributeChangedCallback(){if(this.isConnected)void this.open();}
        disconnectedCallback(){this.epoch++;this.view?.dispose();this.view=null;this.messages=[];}
        async open(){
          const epoch=++this.epoch;this.view?.dispose();this.view=null;this.shadowRoot.textContent='正在恢复课程…';
          try{
            const sourceURL=this.getAttribute('src'),session_id=this.getAttribute('session-id'),course_path=this.getAttribute('course-path');
            const [module,access]=await Promise.all([require.async('./client.studio-native.js'),request('/view',{session_id,course_path})]);
            if(!this.isConnected||epoch!==this.epoch)return;
            const resourceFetch=async(url,options={},retry=false)=>{
              const headers=new Headers(options.headers);if(options.method&&options.method!=='GET')headers.set('X-KGXC-Token',token);
              const response=await fetch(url,{...options,headers});
              if(response.status===403&&!retry){token=(await request('/meta')).token;return resourceFetch(url,options,true);}return response;
            };
            this.view=module.mountNative(this,{sourceURL,resourceBase:access.resource_base,fetch:resourceFetch,onMessage:data=>{if(epoch===this.epoch)this.dispatchEvent(new CustomEvent('kgxc-message',{detail:data}));}});
            for(const data of this.messages.splice(0))this.view.receive(data);
          }catch(error){if(epoch===this.epoch)this.shadowRoot.textContent='课程界面未能恢复：'+error.message;}
        }
      });
    }
    const ownedFrames=new WeakMap(),draftKey=path=>'kgxc-unsaved-draft:'+path;
    const STAGES=[['sources','资料'],['outline','大纲'],['script','逐字稿'],['storyboard','分镜'],['pilot','有声小样'],['final','整课交付']];
    function savedDraft(path){try{return JSON.parse(localStorage.getItem(draftKey(path))||'null');}catch{return null;}}
    const QUESTION_CSS=`.kgxc-chat [data-question-key]:not(:has(>section>header button[aria-expanded="false"])){position:fixed;inset:0;z-index:1000;box-sizing:border-box;padding:32px;background:rgba(24,31,43,.28);display:flex;align-items:center;justify-content:center}.kgxc-chat [data-question-key]>section{width:min(680px,calc(100vw - 64px));max-width:680px;max-height:calc(100dvh - 64px)}.kgxc-chat [data-question-key] button[role="radio"][aria-checked="true"]{background:#edf3ff;border-color:#6b89d4;box-shadow:inset 3px 0 #5676c5}.kgxc-chat [data-question-key] button[role="radio"]:focus-visible{outline:2px solid #5676c5;outline-offset:2px}`;
    function submitLastChoice(event){
      // Capture the page BEFORE React's handler advances a previous question.
      const option=event.target.closest?.('button[role="radio"]');
      const card=option?.closest('.kgxc-chat [data-question-key]');
      if(!event.isTrusted||!card||option.disabled)return;
      const footer=card.querySelector('footer'),page=footer?.textContent.match(/(\d+)\s*\/\s*(\d+)/);
      if(!page||page[1]!==page[2])return;
      const question=card.querySelector('section')?.getAttribute('aria-labelledby');
      requestAnimationFrame(()=>{
        if(!card.isConnected||card.querySelector('section')?.getAttribute('aria-labelledby')!==question||option.getAttribute('aria-checked')!=='true')return;
        const submit=Array.from(card.querySelector('footer')?.querySelectorAll('button')||[]).at(-1);
        if(submit&&!submit.disabled)submit.click();
      });
    }
    const CSS=`.kgxc-panel{height:100%;min-height:0;display:flex;flex-direction:column;background:#fff;color:#2c3036;font:14px/1.7 system-ui,sans-serif}.kgxc-switch{display:flex;flex-wrap:wrap;flex-shrink:0;gap:10px;align-items:center;padding:8px 24px;border-bottom:1px solid #e7e8e9;font-size:12px;color:#7b8087}.kgxc-switch select{border:0;background:transparent;color:#454b54;font:inherit;max-width:80%}.kgxc-layout{display:flex;flex:1;min-height:0;min-width:0}.kgxc-editor{display:flex;flex:1;min-width:320px;min-height:0;position:relative}.kgxc-frame{flex:1;min-height:0;width:100%;border:0}.kgxc-native{display:block;overflow:auto;background:#fafbfc}.kgxc-chat{display:flex;flex-direction:column;min-height:0;width:var(--kgxc-chat-width,360px);min-width:290px;max-width:60%;border-left:1px solid #e0e3e7;flex-shrink:0;background:var(--background,#fff);color:var(--text-primary,#282d34)}.kgxc-chat-head{display:flex;gap:8px;align-items:center;padding:10px 14px;border-bottom:1px solid #e7e8e9}.kgxc-chat-head strong{flex:1;font-size:14px}.kgxc-chat button,.kgxc-reopen{font:inherit;border:1px solid #d6dbe2;background:transparent;color:inherit;border-radius:6px;padding:5px 9px;cursor:pointer;font-size:12px}.kgxc-chat-tools{display:flex;gap:8px;padding:10px 14px}.kgxc-chat-note{font-size:11px;color:#818791;padding:0 14px 8px}.kgxc-chat-body{display:flex;flex:1;min-height:0;min-width:0;flex-direction:column;overflow:hidden}.kgxc-chat-native{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden}.kgxc-chat-native>div{flex:1;min-height:0}.kgxc-divider{width:5px;cursor:col-resize;flex-shrink:0;background:#fafbfc;touch-action:none}.kgxc-chat-toggle{margin-left:auto;flex-shrink:0;font:inherit;border:1px solid #d6dbe2;background:#fff;color:#324e7e;border-radius:6px;padding:5px 9px;cursor:pointer}.kgxc-chat-toggle:focus-visible{outline:2px solid #5676c5;outline-offset:2px}.kgxc-chat-error{font-size:12px;color:#a24b3c;margin:0 14px 8px}.kgxc-chat [data-phase]{min-width:0}.kgxc-empty{margin:auto;max-width:450px;padding:36px}.kgxc-empty h1{font-size:22px}.kgxc-empty p{color:#7b8087}.kgxc-update-notice{display:flex;align-items:center;gap:12px;flex-wrap:wrap;flex-shrink:0;padding:8px 24px;background:#eef5ff;color:#324e7e;font-size:12px}.kgxc-update-notice a{color:inherit;text-decoration:underline}.kgxc-update-notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}.kgxc-error{color:#9b3b32;padding:12px 24px;background:#fff1ed}`;
    function Workspace(props){return props.renderSlot('kgxc.workspace',{});}
    function SessionPanel(props){return h(Panel,{...props,key:props.sessionId||'no-session'});}
    function Panel({ctx,sessionId,useSession,useSessionStatus,renderSlot}){
      const session=useSession(value=>value);
      const sessionStatus=useSessionStatus(value=>value.get(sessionId));
      const running=Boolean(sessionStatus?.running??session?.running);
      const [courses,setCourses]=useState([]),[active,setActive]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
      const [workspacePath,setWorkspacePath]=useState('');
      const [stage,setStage]=useState('sources'),[stageMeta,setStageMeta]=useState(null),[requestedStage,setRequestedStage]=useState(null);
      const frame=useRef(null),layout=useRef(null),generation=useRef(0),alive=useRef(true),leaving=useRef(new Map()),wasRunning=useRef(running),frameEpoch=useRef(0);
      const runningRef=useRef(running);runningRef.current=running;
      const productionRef=useRef(null);
      const [chatOpen,setChatOpen]=useState(()=>localStorage.getItem('kgxc-chat-open')!=='false');
      const [chatWidth,setChatWidth]=useState(()=>Math.max(290,Math.min(600,Number(localStorage.getItem('kgxc-chat-width'))||360)));
      const [retentionPrompt,setRetentionPrompt]=useState(null),[retentionBusy,setRetentionBusy]=useState(false);
      const reminded=useRef(new Set());
      const requestedQuestions=useRef(new Set());
      const [availableUpdate,setAvailableUpdate]=useState(null);
      useEffect(()=>{
        let live=true;
        request('/updates').then(value=>{
          const update=value.update;
          if(live&&update&&localStorage.getItem('kgxc-update-dismissed')!==update.version)setAvailableUpdate(update);
        }).catch(()=>{});
        return()=>{live=false;};
      },[]);
      function dismissUpdate(){try{localStorage.setItem('kgxc-update-dismissed',availableUpdate.version);}catch{}setAvailableUpdate(null);}
      function toggleChat(){setChatOpen(value=>{localStorage.setItem('kgxc-chat-open',String(!value));return !value;});}
      function resize(event){event.preventDefault();const start=event.clientX,width=chatWidth;event.currentTarget.setPointerCapture(event.pointerId);const target=event.currentTarget;const move=e=>{const max=Math.max(290,(layout.current?.clientWidth||900)*.6);setChatWidth(Math.max(290,Math.min(max,width+start-e.clientX)));};const end=()=>{target.removeEventListener('pointermove',move);target.removeEventListener('pointerup',end);};target.addEventListener('pointermove',move);target.addEventListener('pointerup',end);}
      useEffect(()=>{localStorage.setItem('kgxc-chat-width',String(chatWidth));},[chatWidth]);
      const current=()=>alive.current&&ctx.uiWorkspace.selection.getSnapshot().sessionId===sessionId;
      useEffect(()=>{alive.current=true;return()=>{alive.current=false;generation.current++;};},[]);
      async function refresh(){
        const attempt=++generation.current;
        try{
          const [context,list]=await Promise.all([request('/context',{session_id:sessionId}),request('/courses')]);
          if(!current()||attempt!==generation.current)return;
          setCourses(list.courses);
          setWorkspacePath(context.workspace_path||'');
          if(!context.course_path){setActive(null);setLoading(false);return;}
          if(active?.course_path===context.course_path&&active.delivery_only){setLoading(false);return;}
          setLoading(!active);
          const course=await call('kgxc_course_resume',{course_path:context.course_path});
          if(!current()||attempt!==generation.current)return;
          if(active?.course_path===course.course_path&&active.workbench_url===course.workbench_url&&!course.delivery_only)frame.current?.contentWindow.postMessage({type:'kgxc-editor-refresh'},new URL(course.workbench_url).origin);
          setActive(course);setLoading(false);
          if(course.delivery?.cleanup_status==='deferred'&&!reminded.current.has(course.delivery.course_id)){reminded.current.add(course.delivery.course_id);void showRetention(course);}
        }catch(e){if(current()&&attempt===generation.current){setError(e.message);setLoading(false);}}
      }
      useEffect(()=>{refresh();},[sessionId,session?.openState]);
      useEffect(()=>{if(sessionStatus?.pendingInteraction){setChatOpen(true);localStorage.setItem('kgxc-chat-open','true');}},[sessionStatus?.pendingInteraction]);
      useEffect(()=>{
        if(!active||active.delivery_only||running||sessionStatus?.pendingInteraction||!stageMeta?.waiting_decisions?.length||!current())return;
        const key=active.course_path+':'+JSON.stringify(stageMeta.waiting_decisions);
        if(requestedQuestions.current.has(key))return;
        requestedQuestions.current.add(key);setChatOpen(true);localStorage.setItem('kgxc-chat-open','true');
        request('/editor',{action:'stage',arguments:{course_path:active.course_path,session_id:sessionId,target_stage:'questions',context_stage:stage,instruction:'主动调用 ask_user_question，只展示当前方案已保存且尚未回答的选择。当前待选ID：'+stageMeta.waiting_decisions.map(d=>d.id).join('、')+'。不改课程、不推进阶段、不重新询问已回答或已委托决定的事项。'}}).catch(error=>{if(current())setError(error.message);});
      },[active?.course_path,stageMeta?.waiting_decisions,running,sessionStatus?.pendingInteraction]);
      useEffect(()=>{if(wasRunning.current&&!running){setRequestedStage(null);refresh();}wasRunning.current=running;},[running]);
      useEffect(()=>{if(active&&!active.delivery_only&&frame.current)frame.current.contentWindow.postMessage({type:'kgxc-editor-busy',running},new URL(active.workbench_url).origin);},[running,active]);
      useEffect(()=>{
        if(!active||active.delivery_only)return;
        let live=true,timer;const path=active.course_path,origin=new URL(active.workbench_url).origin;
        const poll=async()=>{
          clearTimeout(timer);if(!live||document.hidden)return;
          try{
            const value=await request('/progress',{session_id:sessionId});
            if(!live||!current())return;
            productionRef.current={course_path:path,production:value.production};
            frame.current?.contentWindow.postMessage({type:'kgxc-editor-production',course_path:path,production:value.production},origin);
            if(running||value.production?.current)timer=setTimeout(poll,2000);
          }catch{if(live&&running)timer=setTimeout(poll,3000);}
        };
        const visible=()=>{if(!document.hidden)poll();else clearTimeout(timer);};
        document.addEventListener('visibilitychange',visible);poll();
        return()=>{live=false;clearTimeout(timer);document.removeEventListener('visibilitychange',visible);};
      },[active?.course_path,active?.delivery_only,running,sessionId]);
      useEffect(()=>{setStageMeta(null);setRequestedStage(null);if(!active){setStage('sources');return;}const remembered=localStorage.getItem('kgxc-stage:'+active.course_path);setStage(STAGES.some(([key])=>key===remembered)?remembered:STAGES.some(([key])=>key===active.workflow?.stage)?active.workflow.stage:'outline');},[active?.course_path]);
      async function navigateStage(next){try{await prepareLeave();if(!current())return;if(next===stage){frameEpoch.current++;setActive(value=>value&&({...value}));}setStageMeta(null);setStage(next);if(active)localStorage.setItem('kgxc-stage:'+active.course_path,next);}catch(e){setError(e.message);}}
      async function prepareLeave(){
        if(!active||active.delivery_only||!frame.current)return;
        const live=await request('/workspace',{action:'workbench_live',session_id:sessionId});
        if(!current())return;
        if(live.alive===false){
          const attempt=++generation.current,course=await call('kgxc_course_resume',{course_path:active.course_path});
          if(current()&&attempt===generation.current){frameEpoch.current++;setActive(course);setStageMeta(null);}
          return;
        }
        const id=crypto.randomUUID();
        await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{leaving.current.delete(id);reject(Error('草稿尚未保存，请稍后再切换。'));},20000);leaving.current.set(id,{resolve,reject,timer});frame.current.contentWindow.postMessage({type:'kgxc-editor-leave',id},new URL(active.workbench_url).origin);});
      }
      async function open(path){
        setError('');try{
          await prepareLeave();
          if(!current())return;
          const attempt=++generation.current;setLoading(true);setRetentionPrompt(null);
          const course=await call('kgxc_course_resume',{course_path:path});
          if(!current()||attempt!==generation.current)return;
          await request('/editor',{action:course.delivery_only?'select_delivery':'bind',arguments:{course_path:path,session_id:sessionId,select:true}});
          if(!current()||attempt!==generation.current)return;
          setActive(course);setLoading(false);
        }catch(e){if(current()){setError(e.message);setLoading(false);}}
      }
      async function newCourse(){
        setError('');try{
          await prepareLeave();if(!current())return;
          const workspace=ctx.uiWorkspace.workspaces.list.getSnapshot().items.find(item=>item.sessionIds.includes(sessionId)||item.path===session?.cwd)||await ctx.uiWorkspace.workspaces.initializeDefault();
          const id=await ctx.uiWorkspace.sessions.create({workspaceId:workspace.workspaceId});
          if(!current())return;
          ctx.uiWorkspace.openSession(id);ctx.layout.selectPanel('kgxc-course');
        }catch(e){if(current())setError(e.message);}
      }
      async function moveIntoWorkspace(){
        try{setError('');await prepareLeave();if(!current())return;setLoading(true);const value=await request('/workspace',{session_id:sessionId});if(current()){setActive(value);setLoading(false);}}
        catch(e){if(current()){setError(e.message);setLoading(false);}}
      }
      async function showRetention(course=active){
        if(!course?.delivery||course.delivery.cleanup_status==='complete')return;
        setRetentionPrompt({course,preview:null,error:'',previewError:'',previewLoading:false});
      }
      async function previewRetention(){
        const course=retentionPrompt?.course;if(!course||!current())return false;
        const attempt=generation.current;
        setRetentionPrompt(previous=>previous&&({...previous,previewLoading:true,previewError:''}));
        try{const value=await request('/workspace',{action:'cleanup_preview',session_id:sessionId});if(value.preview.course_path&&value.preview.course_path!==course.course_path)throw Error('当前课程已切换，过程文件保持原样，请重新打开选择。');if(current()&&attempt===generation.current){setRetentionPrompt(previous=>previous&&previous.course.course_path===course.course_path?({...previous,preview:value.preview,previewLoading:false}):previous);return true;}}
        catch(error){if(current()&&attempt===generation.current)setRetentionPrompt(previous=>previous&&({...previous,preview:null,previewLoading:false,previewError:error.message}));}return false;
      }
      async function chooseRetention(choice){
        if(!current()||retentionBusy||!retentionPrompt)return;
        setRetentionBusy(true);
        try{const value=await request('/workspace',{action:'retention',session_id:sessionId,choice,request_id:retentionPrompt.preview?.request_id});if(current()){setActive(value);setRetentionPrompt(null);}}
        catch(error){if(current())setRetentionPrompt(previous=>previous&&({...previous,error:error.message}));}
        finally{if(current())setRetentionBusy(false);}
      }
      async function resumeEngineering(){try{await open(active.course_path);setStage('final');}catch(error){setError(error.message);}}
      async function openSavedFolder(){try{await request('/workspace',{action:'open_delivery',session_id:sessionId});if(current())setError('');}catch(error){if(current()){if(retentionPrompt)setRetentionPrompt(previous=>previous&&({...previous,error:error.message}));else setError(error.message);}}}
      useEffect(()=>{
        if(!active||active.delivery_only)return;
        const origin=new URL(active.workbench_url).origin;
        if(frame.current)ownedFrames.set(frame.current.contentWindow,{origin,path:active.course_path});
        const receive=async event=>{
          if(event.source!==frame.current?.contentWindow||event.origin!==origin)return;
          if(event.data?.type==='kgxc-editor-ready'){event.source.postMessage({type:'kgxc-editor-host',draft:savedDraft(active.course_path),running:runningRef.current},origin);if(productionRef.current?.course_path===active.course_path)event.source.postMessage({type:'kgxc-editor-production',...productionRef.current},origin);return;}
          if(event.data?.type==='kgxc-studio-state'&&event.data.course_path===active.course_path){setStageMeta(previous=>!previous||(event.data.revision||0)>=(previous.revision||0)?event.data:previous);return;}
          if(event.data?.type==='kgxc-editor-leave-result'){const item=leaving.current.get(event.data.id);if(item){clearTimeout(item.timer);leaving.current.delete(event.data.id);event.data.error?item.reject(Error(event.data.error)):item.resolve();}return;}
          if(event.data?.type!=='kgxc-editor-request'||event.data.course_path!==active.course_path)return;
          const {id,action,...args}=event.data;
          if(action==='review'){
            try{const result=await request('/review',{...args,action:args.review_action,session_id:sessionId,course_path:active.course_path});event.source.postMessage({type:'kgxc-editor-result',id,result},origin);}
            catch(error){event.source.postMessage({type:'kgxc-editor-result',id,error:error.message},origin);}return;
          }
          if(action==='deliver'){
            try{if(runningRef.current)throw Error('请等待当前 AI 制作结束后再保存交付文件。');const value=await request('/workspace',{action:'deliver',session_id:sessionId});event.source.postMessage({type:'kgxc-editor-result',id,result:value},origin);if(value.ok){setActive(value);setStage('final');setStageMeta(null);if(value.delivery?.cleanup_decision?.choice!=='keep')void showRetention(value);}}
            catch(error){event.source.postMessage({type:'kgxc-editor-result',id,error:error.message},origin);}return;
          }
          if(!['rewrite','cancel','render','stage'].includes(action))return;
          try{if(['stage','render'].includes(action)&&runningRef.current)throw Error('当前 AI 正在制作，请等待结束，或在右侧停止后重试。');const result=await request('/editor',{action,arguments:{...args,session_id:sessionId}});event.source.postMessage({type:'kgxc-editor-result',id,result},origin);if(action==='stage'&&STAGES.some(([key])=>key===result.target_stage)){setRequestedStage(result.target_stage);setStage(result.target_stage);localStorage.setItem('kgxc-stage:'+active.course_path,result.target_stage);}}
          catch(e){event.source.postMessage({type:'kgxc-editor-result',id,error:e.message},origin);}
        };
        const element=frame.current,nativeReceive=event=>receive({source:element.contentWindow,origin,data:event.detail});
        element?.addEventListener?.('kgxc-message',nativeReceive);
        element?.contentWindow?.postMessage({type:'kgxc-editor-host',draft:savedDraft(active.course_path),running:runningRef.current},origin);
        window.addEventListener('message',receive);return()=>{window.removeEventListener('message',receive);element?.removeEventListener?.('kgxc-message',nativeReceive);};
      },[active]);
      function stageStatus(key){const meta=stageMeta||{},gates=meta.gates||active?.workflow?.gates||[],gate=gates.find(g=>g.id===key),has=key==='sources'?meta.has_sources:key==='outline'?meta.has_outline:key==='script'?meta.has_script:key==='storyboard'?meta.has_storyboard:key==='pilot'?meta.has_pilot:meta.has_final;if(requestedStage===key&&(running||meta.producing)&&!sessionStatus?.pendingInteraction)return '生成中';if(key==='sources'&&gates.some(g=>g.id==='outline'&&g.status==='confirmed'))return '已确认';if(meta.dirty&&has&&['script','storyboard','pilot','final'].includes(key))return '修改后待更新';if(gate?.status==='stale')return '修改后待更新';if(gate?.status==='delivered')return '正式交付';if(gate?.status==='confirmed')return key==='storyboard'?'分镜审阅通过':'用户已确认';const review=meta.ai_review?.nodes?.[key];if(review?.passed)return key==='storyboard'?'独立审阅通过':'AI通过，待你确认';return has?(key==='storyboard'?'待独立审阅':'待你确认'):'尚未生成';}
      const url=active&&!active.delivery_only?active.workbench_url+'/studio.html?stage='+stage+'&parentOrigin='+encodeURIComponent(location.origin):null;
      return h('section',{className:'kgxc-panel','aria-label':'课程工作台'},
        h('div',{className:'kgxc-switch'},h('button',{onClick:newCourse,disabled:loading},'新建课程'),h('label',{htmlFor:'kgxc-course'},active?'当前课程':'继续已有课程'),h('select',{id:'kgxc-course',value:active?.course_path||'',disabled:loading||!sessionId,onChange:e=>e.target.value&&open(e.target.value)},h('option',{value:'',disabled:true},'选择已有课程…'),courses.map(c=>h('option',{key:c.course_id,value:c.course_path},c.title))),active&&!active.delivery_only&&workspacePath&&!active.course_path.startsWith(workspacePath+'/')&&h('button',{onClick:moveIntoWorkspace,disabled:loading},'工程迁入当前工作区'),h('button',{type:'button',className:'kgxc-chat-toggle',onClick:toggleChat,'aria-expanded':chatOpen,'aria-controls':'kgxc-ai-chat'},chatOpen?'收起 AI 对话':'打开 AI 对话')),
        availableUpdate&&h('div',{className:'kgxc-update-notice',role:'status'},h('span',null,'课程插件有新稳定版 '+availableUpdate.version+'。当前课程可继续制作，更新前请保存并退出 DSH。'),h('a',{href:availableUpdate.release_url,target:'_blank',rel:'noopener noreferrer'},'查看更新与下载'),h('button',{type:'button',onClick:dismissUpdate,'aria-label':'忽略此版本更新提醒'},'稍后')) ,
        error&&h('div',{className:'kgxc-error',role:'alert'},error),
        active&&!active.delivery_only&&h('nav',{className:'kgxc-stages',role:'tablist','aria-label':'制课阶段'},STAGES.map(([key,label])=>h('button',{key,role:'tab','aria-selected':stage===key,onClick:()=>navigateStage(key)},h('strong',null,label),h('span',null,stageStatus(key))))),
        h('div',{className:'kgxc-layout',ref:layout,style:{'--kgxc-chat-width':chatWidth+'px'}},h('div',{className:'kgxc-editor'},active?(active.delivery_only?h(DeliveryView,{course:active,onRetention:()=>showRetention(),onResume:resumeEngineering,onOpenFolder:openSavedFolder}):h('kgxc-studio-view',{class:'kgxc-frame kgxc-native',ref:frame,'session-id':sessionId,'course-path':active.course_path,key:active.course_path+':'+frameEpoch.current,title:'课程'+(STAGES.find(([key])=>key===stage)?.[1]||'工作台'),src:url})):h('div',{className:'kgxc-empty'},h('h1',null,loading?'正在打开课程…':'开始一门新课程'),!loading&&h('p',null,'在右侧告诉 AI 要制作哪门课程，或上传资料。这里只显示本次对话关联的课程。'))),chatOpen&&h('div',{className:'kgxc-divider',role:'separator','aria-label':'调整 AI 对话栏宽度','aria-orientation':'vertical',onPointerDown:resize}),chatOpen&&h('aside',{id:'kgxc-ai-chat',className:'kgxc-chat','aria-label':'课程 AI 对话'},h('div',{className:'kgxc-chat-head'},h('strong',null,'AI 对话'),h('button',{onClick:toggleChat,'aria-label':'收起 AI 对话'},'收起')),renderSlot('kgxc.chat',{coursePath:active?.delivery_only?undefined:active?.course_path,courseTitle:active?.workflow?.title,onCourseUpdate:refresh}))),
        retentionPrompt&&h(RetentionDialog,{key:retentionPrompt.course.delivery.course_id,prompt:retentionPrompt,busy:retentionBusy,onChoose:chooseRetention,onPreview:previewRetention,onOpenFolder:openSavedFolder,onClose:()=>!retentionBusy&&setRetentionPrompt(null)}));
    }
    function RetentionDialog({prompt,busy,onChoose,onClose,onPreview,onOpenFolder}){
      const [reviewDelete,setReviewDelete]=useState(false),panel=useRef(null),preview=prompt.preview;
      useEffect(()=>{const before=document.activeElement;panel.current?.querySelector('button')?.focus();return()=>before?.focus?.();},[]);
      function keys(event){if(event.key==='Escape'&&!busy){event.preventDefault();onClose();}if(event.key==='Tab'){const nodes=Array.from(panel.current?.querySelectorAll('button:not(:disabled),summary,textarea')||[]);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}}
      const size=bytes=>bytes>=1073741824?(bytes/1073741824).toFixed(2)+' GB':(bytes/1048576).toFixed(1)+' MB';
      return h('div',{style:{position:'fixed',inset:0,zIndex:1100,background:'rgba(24,31,43,.3)',display:'flex',alignItems:'center',justifyContent:'center',padding:'24px'},onKeyDown:keys},
        h('section',{ref:panel,role:'dialog','aria-modal':true,'aria-labelledby':'kgxc-retention-title',style:{background:'#fff',color:'#2c3036',borderRadius:'12px',padding:'28px',width:'min(620px,100%)',maxHeight:'calc(100vh - 48px)',overflow:'auto',boxSizing:'border-box'}},
          h('h2',{id:'kgxc-retention-title',style:{marginTop:0}},reviewDelete?'请核对本次清理范围':'成片已保存，过程文件怎么处理？'),
          h('p',null,prompt.course.delivery.title),h('p',{style:{fontSize:'12px',overflowWrap:'anywhere'}},'保存位置：'+(prompt.course.delivery.delivery_root||'')),h('button',{onClick:onOpenFolder},'打开保存文件夹'),h('p',null,'逐字稿、小样、配音与工程目前全部保留。关闭此窗口不会删除文件。'),
          preview?h('div',null,h('p',null,'本课过程文件共 '+preview.file_count+' 个，约 '+size(preview.bytes)+'。'),h('details',{open:reviewDelete},h('summary',null,'查看本课过程文件范围'),preview.groups.filter(g=>g.files).map(g=>h('p',{key:g.label},g.label+'：'+g.files+' 个，'+size(g.bytes))))):h('p',{role:'status'},prompt.previewLoading?'正在核对清理范围；文件保持保留…':'选择保留无需清理检查；需要清理时再查看具体范围。'),
          prompt.previewError&&h('p',{role:'status'},'成品已保存；清理范围暂未核对：'+prompt.previewError+'。仍可保留全部或稍后提醒。'),
          reviewDelete&&h('p',null,'确认后将删除以上整套过程文件，无法继续编辑本课；独立原件另存，桌面成片、字幕和封面保留。'),
          prompt.error&&h('p',{role:'alert',style:{color:'#a24b3c'}},prompt.error),
          h('div',{style:{display:'flex',gap:'10px',flexWrap:'wrap',marginTop:'22px'}},
            h('button',{disabled:busy,onClick:()=>onChoose('keep')},'保留全部（推荐）'),
            h('button',{disabled:busy,onClick:()=>onChoose('later')},'稍后提醒我'),
            !reviewDelete?h('button',{disabled:busy||prompt.previewLoading,onClick:async()=>{if(preview||await onPreview())setReviewDelete(true);}},'查看并选择清理'):h('button',{disabled:busy||!preview||!!prompt.error,onClick:event=>{if(event.isTrusted)onChoose('delete-process-files');},style:{color:'#a23f30'}},'确认清理所列过程文件'),
            h('button',{disabled:busy,onClick:onClose},'关闭并保留'))));
    }
    function DeliveryView({course,onRetention,onResume,onOpenFolder}){
      const player=useRef(null),value=course.delivery,[mediaOrigin,setMediaOrigin]=useState(''),[mediaError,setMediaError]=useState('');
      useEffect(()=>{let live=true;request('/meta').then(meta=>{const origin=new URL(meta.media_origin||location.origin);if(!['http:','https:'].includes(origin.protocol)||!['127.0.0.1','localhost','[::1]'].includes(origin.hostname))throw Error('成品回看服务尚未就绪');if(live)setMediaOrigin(origin.origin);}).catch(error=>{if(live)setMediaError(error.message);});return()=>{live=false;};},[value.course_id]);
      // Electron fetch uses an IPC bridge; <video> does not. Use the host's real
      // loopback HTTP listener so native media can issue seek/range requests.
      const fileURL=index=>mediaOrigin+API+'/delivery/file?course_id='+encodeURIComponent(value.course_id)+'&index='+index;
      const cover=value.files.findIndex(f=>/\.(png|jpe?g|webp)$/i.test(f.name));
      return h('section',{className:'kgxc-delivery',style:{overflow:'auto',padding:'24px',width:'100%'}},
        h('p',{style:{color:'#79818b'}},'整课交付'),h('h1',null,value.title),h('p',null,value.cleanup_status==='complete'?'成品已保存到桌面；过程文件此前已清理。':'成品已保存到桌面，逐字稿、小样、配音和过程工程均保留。'),
        h('div',{style:{display:'flex',gap:'12px',flexWrap:'wrap',margin:'12px 0'}},h('button',{onClick:onOpenFolder},'打开保存文件夹'),value.cleanup_status!=='complete'&&h('button',{onClick:onResume},'继续查看与编辑工程'),value.cleanup_status!=='complete'&&h('button',{onClick:onRetention},'过程文件处理选择')),
        value.review_context==='qa-simulation'&&h('p',null,'独立验证课程，技术模拟不代表正式业务课验收。'),
        !mediaOrigin&&h('p',{role:'status'},mediaError||'正在连接成品播放器…'),
        mediaOrigin&&value.files.map((file,index)=>/\.mp4$/i.test(file.name)?h('video',{key:file.name,ref:player,controls:true,preload:'metadata',poster:cover>=0?fileURL(cover):undefined,src:fileURL(index),style:{width:'100%',maxHeight:'65vh',background:'#20242a'}}):null),
        h('div',{style:{display:'flex',gap:'10px',flexWrap:'wrap',marginTop:'12px'}},(value.chapters||[]).map(chapter=>h('button',{key:chapter.id||chapter.title+':'+chapter.start,onClick:()=>{if(player.current)player.current.currentTime=Math.min(chapter.start,Math.max(0,(player.current.duration||Infinity)-.1));}},chapter.title))),
        mediaOrigin&&h('div',{style:{display:'flex',gap:'18px',flexWrap:'wrap',marginTop:'14px'}},value.files.map((file,index)=>h('a',{key:file.name,href:fileURL(index)+'&download=1',download:file.name},file.name))),
        h('p',{style:{fontSize:'12px',color:'#79818b',overflowWrap:'anywhere'}},value.delivery_root));
    }
    function ChatView(props){return props.renderSlot('conversation.session',{view:'chat'});}
    function Chat({ctx,coursePath,courseTitle,onCourseUpdate,sessionId,useSession,useConversation,useSessions,inputActions,renderFactorySlot}){
      const session=useSession(value=>value),conversation=useConversation(value=>value);
      const summaryBlank=useSessions(value=>sessionId===undefined?undefined:value.byId[sessionId]?.blank);
      const [message,setMessage]=useState(''),[picking,setPicking]=useState(false);
      useEffect(()=>{let alive=true;if(sessionId&&coursePath)request('/editor',{action:'bind',arguments:{course_path:coursePath,session_id:sessionId}}).catch(error=>{if(alive)setMessage(error.message);});return()=>{alive=false;};},[sessionId,coursePath]);
      async function chooseFolder(){
        setPicking(true);setMessage('');const insertion=inputActions?.captureInsertion();
        try{const picker=window.__DSH_DIRECTORY_PICKER__;const path=await (picker?picker.pick():ctx.uiWorkspace.pickDirectory());if(path){if(!inputActions){const workspace=await ctx.uiWorkspace.workspaces.create({path});await ctx.uiWorkspace.openWorkspace(workspace.workspaceId);ctx.layout.selectPanel('kgxc-course');}else if(!inputActions.insertText('@'+JSON.stringify(path)+' ',insertion))setMessage('输入内容已改变，请重新选择文件夹。');}}
        catch(error){setMessage(error.message);}finally{setPicking(false);}
      }
      function chooseFiles(){setMessage('');if(!sessionId||!ctx.conversation.input.canPickFiles(sessionId))setMessage('对话尚未就绪，请稍后再上传文件。');else ctx.conversation.input.pickFiles(sessionId);}
      const active=Boolean(session&&(session.running||!session.blank&&!session.awaitingFirstTurn||conversation?.activeTargets?.size>0));
      const settling=Boolean(session&&!active&&session.openState==='loading'&&summaryBlank!==true);
      const phase=settling?'settling':active?'active':'hero';
      return h('div',{className:'kgxc-chat-body'},h('div',{className:'kgxc-chat-tools'},h('button',{onClick:chooseFolder,disabled:picking},picking?'正在选择…':'选择文件夹'),h('button',{onClick:chooseFiles,disabled:!sessionId},'上传文件')),h('p',{className:'kgxc-chat-note'},courseTitle?'当前课程：'+courseTitle:'沿用 DSH 当前对话，可发送资料开始制课。'),message&&h('p',{className:'kgxc-chat-error',role:'alert'},message),h('div',{className:'kgxc-chat-native'},renderFactorySlot('conversation.content',{variant:'embedded',phase,hero:phase==='hero'},{slots:{views:ChatView}})));
    }
    function apply(ctx){
      defineNativeStudio();
      ctx.effect(()=>{const style=document.createElement('style');style.dataset.plugin='kgxc-course-plugin';style.textContent=CSS+QUESTION_CSS+`.kgxc-stages{display:grid;grid-template-columns:repeat(6,minmax(95px,1fr));overflow-x:auto;flex-shrink:0;background:#fafbfc;border-bottom:1px solid #e1e5eb}.kgxc-stages button{border:0;border-right:1px solid #e6e9ee;background:transparent;padding:13px 15px;cursor:pointer;text-align:left;color:#525d6b}.kgxc-stages button[aria-selected=true]{background:#edf2fa;box-shadow:inset 0 -2px #6682b6;color:#324e7e}.kgxc-stages strong,.kgxc-stages span{display:block;font-size:13px}.kgxc-stages span{font-size:10px;color:#8a929d;margin-top:4px}`;document.head.appendChild(style);return()=>style.remove();},'kgxc-course: editor styles');
      ctx.effect(()=>{document.addEventListener('click',submitLastChoice,true);return()=>document.removeEventListener('click',submitLastChoice,true);},'kgxc-course: submit last explicit choice');
      ctx.effect(()=>{const receive=event=>{const owner=ownedFrames.get(event.source),data=event.data;if(!owner||owner.origin!==event.origin||data?.type!=='kgxc-editor-draft'||data.course_path!==owner.path)return;if(data.dirty){localStorage.setItem(draftKey(owner.path),JSON.stringify({text:data.text,base_text:data.base_text,base_revision:data.base_revision}));}else if(savedDraft(owner.path)?.text===data.text)localStorage.removeItem(draftKey(owner.path));};window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive);},'kgxc-course: preserve pending manual edits');
      ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:'kgxc-course',children:{'kgxc.workspace':{kind:'single',scope:'session-maybe'}}},Workspace));
      ctx.slots.inject('kgxc.workspace',()=>ctx.slots.register({name:'kgxc.workspace',inject:()=>({ctx}),children:{'kgxc.chat':{kind:'single',scope:'session-maybe'}}},SessionPanel));
      ctx.slots.inject('kgxc.chat',()=>ctx.slots.register({name:'kgxc.chat',inject:()=>({ctx})},Chat));
      ctx.slots.inject('conversation.session.header.actions',()=>ctx.slots.register({name:'conversation.session.header.actions',id:'kgxc-course',order:15,inject:()=>({ctx})},SessionEntry));
      ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:'kgxc-course',order:15,label:()=> '课程工作台'},props=>h('svg',{width:props.size||18,height:props.size||18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('rect',{x:3,y:4,width:18,height:14,rx:2}),h('path',{d:'M9 21h6M12 18v3M10 8l5 3-5 3z'}))));
    }
    function SessionEntry({ctx,sessionId,useSession}){
      const session=useSession(value=>value);
      useEffect(()=>{let alive=true;request('/context',{session_id:sessionId}).then(context=>{if(alive&&context.course_path&&ctx.uiWorkspace.selection.getSnapshot().sessionId===sessionId)ctx.layout.selectPanel('kgxc-course');}).catch(()=>{});return()=>{alive=false;};},[sessionId,session?.openState,session?.running]);
      return h('button',{type:'button',onClick:()=>ctx.layout.selectPanel('kgxc-course'),'aria-label':'打开课程工作台'},'课程工作台');
    }
    return {name:'kgxc-course',inject:['slots','layout','uiWorkspace','uiConversation','conversation'],apply};
  }
});
