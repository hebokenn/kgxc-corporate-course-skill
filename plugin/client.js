window.__ModuleLoader__.load({
  id:'kgxc-course-plugin',
  factory:require=>{
    const {createElement:h,useState,useEffect,useRef}=require('react');
    const API='/api/kgxc-course'; let token;
    async function request(path,data,retried=false){
      if(data&&!token)token=(await request('/meta')).token;
      const response=await fetch(API+path,data?{method:'POST',headers:{'Content-Type':'application/json','X-KGXC-Token':token},body:JSON.stringify(data)}:{});
      if(data&&response.status===403&&!retried){token=(await request('/meta')).token;return request(path,data,true);}
      const value=await response.json();if(!response.ok||value.ok===false){const error=Error(value.error||'操作失败');error.code=value.code||value.reason;error.status=response.status;throw error;}return value;
    }
    const call=(name,args={})=>request('/call',{name,arguments:args});
    function updateNotice(value,detail=false){
      if(value?.status==='rate-limited'||value?.status==='rate_limited'||['rate_limited','rate-limited','github_anonymous_rate_limit'].includes(value?.reason)){
        const retry=Number(value.retry_at??value.retryAt);
        return 'GitHub 暂时限制更新检查频率。'+(Number.isFinite(retry)&&retry>Date.now()?'可在 '+new Date(retry).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' 后重试。':'请稍后再试。');
      }
      return value?.update?'发现新版 '+value.update.version+'。':value?.status==='checked'?(detail?'已是最新稳定版。':'已是最新版。'):'暂时无法确认最新版本，请稍后重试。';
    }
    function useUpdateInstall(enabled){
      const [state,setState]=useState({phase:'idle'}),live=useRef(false),op=useRef(false),serial=useRef(0);
      useEffect(()=>{
        live.current=enabled;
        if(!enabled)return;
        const ticket=serial.current;
        void request('/update-install').then(value=>{if(live.current&&ticket===serial.current&&value.phase)setState(value);}).catch(()=>{});
        return()=>{live.current=false;serial.current++;};
      },[enabled]);
      useEffect(()=>{
        if(!enabled||!['downloading','installing'].includes(state.phase))return;
        let stop=false,timer,failures=0;
        const tick=async()=>{
          try{
            const value=await request('/update-install');
            failures=0;if(!stop&&value.phase&&value.phase!=='idle')setState(value);
            if(!stop&&(!value.phase||['downloading','installing'].includes(value.phase)))timer=setTimeout(tick,700);
          }catch(error){
            if(!stop&&++failures<3)timer=setTimeout(tick,900);
            else if(!stop&&state.phase!=='installing')setState({...state,phase:'failed',error:'无法读取下载进度，请重试。'});
          }
        };
        timer=setTimeout(tick,450);return()=>{stop=true;clearTimeout(timer);};
      },[enabled,state.phase]);
      async function act(action,version){
        if(op.current||!enabled)return;
        op.current=true;++serial.current;
        setState(previous=>({...previous,phase:action==='download'?'downloading':'installing',version:version||previous.version,error:null,pending:false}));
        try{
          const value=await request('/update-install',{action,...(version?{version}:{})});
          if(live.current&&value.phase)setState(value);
        }catch(error){
          if(live.current){
            const blocked=action==='install'&&(error.status===409||['busy','pending','install_busy'].includes(error.code)||/正在|进行中|稍后|busy|pending|运行中/i.test(error.message));
            setState(previous=>({...previous,phase:blocked?'ready':'failed',pending:blocked,error:error.message}));
          }
        }finally{op.current=false;}
      }
      return {state,act};
    }
    function updateControls(flow,update,{busy=false,save}={}){
      const {state,act}=flow,phase=state.phase,version=state.version||update?.version;
      if(typeof navigator!=='undefined'&&!/Mac/i.test(navigator.platform||navigator.userAgent||''))return update&&h('a',{href:update.release_url,target:'_blank',rel:'noopener noreferrer'},'打开发布页下载');
      if(phase==='idle'&&!update)return null;
      const total=Number(state.total),received=Number(state.received),known=total>0&&Number.isFinite(received);
      const percentage=known?Math.min(100,Math.max(0,Math.floor(100*received/total))):null;
      const button=(text,action,disabled=false)=>h('button',{type:'button',disabled,onClick:action},text);
      if(phase==='downloading')return h('span',{className:'kgxc-update-flow',role:'status'},'正在下载更新'+(percentage===null?'…':' '+percentage+'%'),h('progress',{max:100,...(percentage===null?{}:{value:percentage}),'aria-label':'更新下载进度'}));
      if(phase==='installing')return h('span',{role:'status'},state.message||'请正常退出 DeepSeek Harness。更新完成后会自动重开；不用退出 Codex。');
      if(phase==='ready')return h('span',{className:'kgxc-update-flow'},h('span',{role:'status'},busy||state.pending||state.busy?'更新已下载，等当前工作结束后再安装。':'更新已下载'+(version?'（'+version+'）':'')+'。'),
        button('退出并安装',async()=>{try{if(save)await save();await act('install',version);}catch{/* workbench retains its own unsaved-draft error */}},busy));
      if(phase==='failed')return h('span',{className:'kgxc-update-flow'},h('span',{role:'alert'},state.error||'更新失败，请重试。'),
        update&&button('重试下载',()=>void act('download',update.version)),
        h('a',{href:update?.release_url||'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/latest',target:'_blank',rel:'noopener noreferrer'},'打开发布页备用下载'));
      return button('下载更新',()=>void act('download',update.version));
    }
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
    const TABS=[...STAGES.slice(0,-1).map(([key,label])=>[key,label,null]),['final','画面与配音','body'],['final','后期与成片','post']];
    function visibleConfirmation(item,nativeQuestion,sessionId,chatOpen){
      return Boolean(item&&chatOpen&&nativeQuestion?.kind==='question'&&nativeQuestion.sessionId===sessionId&&
        !nativeQuestion.review&&nativeQuestion.questions?.some(question=>question.id===item.id));
    }
    function savedDraft(path){try{return JSON.parse(localStorage.getItem(draftKey(path))||'null');}catch{return null;}}
    const QUESTION_CSS=`.kgxc-chat [data-question-key]{min-width:0;box-sizing:border-box}.kgxc-chat [data-question-key]>section{width:100%;max-width:100%;box-sizing:border-box;max-height:calc(100dvh - 145px);overflow:auto}.kgxc-chat [data-question-key] button[role="radio"][aria-checked="true"]{background:#edf3ff;border-color:#6b89d4;box-shadow:inset 3px 0 #5676c5}.kgxc-chat [data-question-key] button[role="radio"]:focus-visible{outline:2px solid #5676c5;outline-offset:2px}`;
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
    const CSS=`.kgxc-panel{height:100%;min-height:0;display:flex;flex-direction:column;background:#fff;color:#2c3036;font:14px/1.7 system-ui,sans-serif}.kgxc-switch{display:flex;flex-wrap:wrap;flex-shrink:0;gap:10px;align-items:center;padding:8px 24px;border-bottom:1px solid #e7e8e9;font-size:12px;color:#7b8087}.kgxc-switch select{border:0;background:transparent;color:#454b54;font:inherit;max-width:80%}.kgxc-layout{display:flex;flex:1;min-height:0;min-width:0}.kgxc-editor{display:flex;flex:1;min-width:320px;min-height:0;position:relative}.kgxc-frame{flex:1;min-height:0;width:100%;border:0}.kgxc-native{display:block;overflow:auto;background:#fafbfc}.kgxc-chat{display:flex;flex-direction:column;min-height:0;width:var(--kgxc-chat-width,360px);min-width:290px;max-width:60%;border-left:1px solid #e0e3e7;flex-shrink:0;background:var(--background,#fff);color:var(--text-primary,#282d34)}.kgxc-chat-head{display:flex;gap:8px;align-items:center;padding:10px 14px;border-bottom:1px solid #e7e8e9}.kgxc-chat-head strong{flex:1;font-size:14px}.kgxc-chat button,.kgxc-reopen{font:inherit;border:1px solid #d6dbe2;background:transparent;color:inherit;border-radius:6px;padding:5px 9px;cursor:pointer;font-size:12px}.kgxc-chat-tools{display:flex;gap:8px;padding:10px 14px}.kgxc-chat-note{font-size:11px;color:#818791;padding:0 14px 8px}.kgxc-chat-body{display:flex;flex:1;min-height:0;min-width:0;flex-direction:column;overflow:hidden}.kgxc-chat-native{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden}.kgxc-chat-native>div{flex:1;min-height:0}.kgxc-divider{width:5px;cursor:col-resize;flex-shrink:0;background:#fafbfc;touch-action:none}.kgxc-chat-toggle{margin-left:auto;flex-shrink:0;font:inherit;border:1px solid #d6dbe2;background:#fff;color:#324e7e;border-radius:6px;padding:5px 9px;cursor:pointer}.kgxc-chat-toggle:focus-visible{outline:2px solid #5676c5;outline-offset:2px}.kgxc-chat-error{font-size:12px;color:#a24b3c;margin:0 14px 8px}.kgxc-chat [data-phase]{min-width:0}.kgxc-empty{margin:auto;max-width:450px;padding:36px}.kgxc-empty h1{font-size:22px}.kgxc-empty p{color:#616b7b}.kgxc-onboarding-actions{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 10px}.kgxc-onboarding-actions button{font:inherit;border:1px solid #dbe2ee;border-radius:9px;padding:7px 11px;background:#fff;color:#354764;cursor:pointer}.kgxc-onboarding-actions button:disabled{opacity:.55;cursor:default}.kgxc-onboarding-actions button.kgxc-onboarding-primary{background:#2455ee;border-color:#2455ee;color:#fff}.kgxc-onboarding-hint{font-size:12px}.kgxc-update-notice{display:flex;align-items:center;gap:12px;flex-wrap:wrap;flex-shrink:0;padding:8px 24px;background:#eef5ff;color:#324e7e;font-size:12px}.kgxc-update-notice a{color:inherit;text-decoration:underline}.kgxc-update-notice button{margin-left:auto;border:0;background:transparent;color:inherit;cursor:pointer}.kgxc-error{color:#9b3b32;padding:12px 24px;background:#fff1ed}`;
    const onboardingSessions=new Map();
    const ONBOARDING_PROMPTS={
      upload:'请用我上传的资料和实拍照片制作课程。先梳理受众、学习目标和课程结构，保存一版可编辑的大纲。遇到关键事实缺口时请先问我，不要先制作视频。',
      describe:'我想制作一门课程。主题：　；面向：　；希望学员学会：　。请先保存一版可编辑的大纲，遇到关键事实缺口时先问我。'
    };
    function Workspace(props){return props.renderSlot('kgxc.workspace',{});}
    function SessionPanel(props){return h(Panel,{...props,key:props.sessionId||'no-session'});}
    function Panel({ctx,sessionId,useSession,useSessionStatus,renderSlot}){
      const session=useSession(value=>value);
      const sessionStatus=useSessionStatus(value=>value.get(sessionId));
      const running=Boolean(sessionStatus?.running??session?.running);
      const [courses,setCourses]=useState([]),[active,setActive]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
      const [workspacePath,setWorkspacePath]=useState('');
      const [stage,setStage]=useState('sources'),[stageMeta,setStageMeta]=useState(null),[requestedStage,setRequestedStage]=useState(null);
      const [finalPhase,setFinalPhase]=useState('body');
      const frame=useRef(null),layout=useRef(null),generation=useRef(0),alive=useRef(true),leaving=useRef(new Map()),wasRunning=useRef(running),frameEpoch=useRef(0);
      const runningRef=useRef(running);runningRef.current=running;
      const productionRef=useRef(null);
      const [chatOpen,setChatOpen]=useState(()=>localStorage.getItem('kgxc-chat-open')!=='false');
      const [chatWidth,setChatWidth]=useState(()=>Math.max(290,Math.min(600,Number(localStorage.getItem('kgxc-chat-width'))||360)));
      const [retentionPrompt,setRetentionPrompt]=useState(null),[retentionBusy,setRetentionBusy]=useState(false);
      const reminded=useRef(new Set());
      const requestedQuestions=useRef(new Set());
      const [confirmation,setConfirmation]=useState(null);
      const [feedbackDraft,setFeedbackDraft]=useState(null);
      const [feedbackState,setFeedbackState]=useState(null);
      const feedbackBusy=useRef(false);
      function openFeedback(context){
        if(!context?.course_path||context.course_path!==activeRef.current?.course_path)return;
        openQuestionPane();
        setFeedbackState(null);
        setFeedbackDraft(previous=>{
          if(previous?.course_path===context.course_path&&previous.stage===context.stage&&previous.question_id===context.question_id&&
             previous.artifact_sha256===context.artifact_sha256&&previous.time===context.time&&previous.segment_id===context.segment_id)return previous;
          const saved=context.feedback,binding=saved?.version_binding;
          return {...context,...(binding?{segment_id:binding.segment_id??undefined,time:binding.time??undefined,artifact_path:binding.artifact_path??undefined,
            artifact_sha256:binding.artifact_sha256??undefined,location_label:saved.location_label||context.location_label}:{}),
            id:saved?.id||crypto.randomUUID(),text:saved?.text||''};
        });
      }
      async function submitFeedback(event){
        event.preventDefault();
        const draft=feedbackDraft;
        if(!draft?.text.trim()||feedbackBusy.current||!current()||stageMeta?.unsaved_edits||activeRef.current?.course_path!==draft.course_path)return;
        feedbackBusy.current=true;setFeedbackState({id:draft.id,status:'submitting'});
        try{
          const value=await request('/editor',{action:'stage-feedback-submit',arguments:{session_id:sessionId,course_path:draft.course_path,
            stage:draft.stage,question_id:draft.question_id,base_revision:stageMeta?.revision,feedback_id:draft.id,text:draft.text,
            segment_id:draft.segment_id,time:draft.time,artifact_path:draft.artifact_path,artifact_sha256:draft.artifact_sha256,location_label:draft.location_label}});
          if(!current()||activeRef.current?.course_path!==draft.course_path)return;
          setFeedbackState({id:draft.id,course_path:draft.course_path,status:value.status,message:value.error_message});
          if(value.status==='requested')setFeedbackDraft(previous=>previous?.id===draft.id?null:previous);
          await refresh();
        }catch(error){if(current()&&activeRef.current?.course_path===draft.course_path)setFeedbackState({id:draft.id,status:'failed',message:error.message});}
        finally{feedbackBusy.current=false;}
      }
      const activeRef=useRef(null),confirmationInFlight=useRef(null),confirmationArgs=useRef(null);
      const [onboarding,setOnboarding]=useState(()=>onboardingSessions.get(sessionId)||null);
      useEffect(()=>{if(onboardingSessions.has(sessionId))onboardingSessions.delete(sessionId);},[sessionId]);
      activeRef.current=active;
      const confirmationCandidates=stageMeta?.course_path===active?.course_path?(stageMeta?.pending_confirmations||[]):[];
      const pendingConfirmation=confirmationCandidates.find(item=>item.stage===stage)||confirmationCandidates.find(item=>!item.decision_status)||confirmationCandidates[0];
      const visibleQuestion=confirmationCandidates.find(item=>visibleConfirmation(item,sessionStatus?.pendingInteraction,sessionId,chatOpen));
      const displayQuestion=visibleQuestion||pendingConfirmation;
      const displayStatus=visibleQuestion?'visible':displayQuestion?
        ((confirmation?.key===active?.course_path+':'+displayQuestion.id&&confirmation.status)||displayQuestion.decision_status||'queued'):'none';
      const editingFeedback=Boolean(chatOpen&&feedbackDraft&&feedbackDraft.course_path===active?.course_path);
      const questionPresentation={type:'kgxc-editor-confirmation',course_path:active?.course_path,question_id:displayQuestion?.id,stage:displayQuestion?.stage,status:displayStatus,editing_feedback:editingFeedback};
      const questionPresentationRef=useRef(null);
      questionPresentationRef.current=questionPresentation;
      useEffect(()=>{
        if(!active||active.delivery_only)return;
        frame.current?.contentWindow.postMessage(questionPresentationRef.current,new URL(active.workbench_url).origin);
      },[active?.course_path,active?.workbench_url,active?.delivery_only,displayQuestion?.id,displayStatus,editingFeedback,stage,finalPhase]);
      function openQuestionPane(){setChatOpen(true);localStorage.setItem('kgxc-chat-open','true');}
      async function askConfirmation(item,manual=false){
        const path=active?.course_path;
        if(!path||!item||!current()||stageMeta?.unsaved_edits||confirmationInFlight.current||runningRef.current||sessionStatus?.pendingInteraction)return;
        if(!manual&&item.decision_status)return;
        const key=path+':'+item.id;
        if(!manual&&confirmation?.key===key)return;
        confirmationInFlight.current=key;
        setConfirmation({key,status:'requesting'});
        openQuestionPane();
        const args={course_path:path,session_id:sessionId,stage:item.stage,question_id:item.id};confirmationArgs.current=args;
        try{
          let value=await request('/editor',{action:'stage-confirmation-request',arguments:args});
          while(value.status==='pending'&&current()&&activeRef.current?.course_path===path){
            await new Promise(resolve=>setTimeout(resolve,850));
            if(!current()||activeRef.current?.course_path!==path)return;
            value=await request('/editor',{action:'stage-confirmation-status',arguments:args});
          }
          if(!current()||activeRef.current?.course_path!==path)return;
          setConfirmation(['busy','cancelled'].includes(value.status)?null:{key,course_path:path,stage:item.stage,status:value.status,error:value.error_message});
          if(value.status==='changes_requested')openFeedback({course_path:path,stage:item.stage,question_id:item.id,label:item.label});
          if(['confirmed','deferred','changes_requested'].includes(value.status))await refresh();
        }catch(error){if(current()&&activeRef.current?.course_path===path)setConfirmation({key,status:'failed',error:error.message});}
        finally{if(confirmationInFlight.current===key){confirmationInFlight.current=null;confirmationArgs.current=null;}}
      }
      useEffect(()=>{
        const args=confirmationArgs.current;
        if(args&&args.course_path===active?.course_path&&(stageMeta?.unsaved_edits||pendingConfirmation?.id!==args.question_id)){
          void request('/editor',{action:'stage-confirmation-cancel',arguments:args}).catch(()=>{});
          return;
        }
        if(!pendingConfirmation||stageMeta?.unsaved_edits||running||sessionStatus?.pendingInteraction||confirmationInFlight.current)return;
        const timer=setTimeout(()=>void askConfirmation(pendingConfirmation),150);
        return()=>clearTimeout(timer);
      },[active?.course_path,pendingConfirmation?.id,pendingConfirmation?.decision_status,stageMeta?.unsaved_edits,running,sessionStatus?.pendingInteraction,confirmation?.status]);
      const [availableUpdate,setAvailableUpdate]=useState(null);
      const updateInstall=useUpdateInstall(true);
      const updateGeneration=useRef(0);
      const [updateBusy,setUpdateBusy]=useState(false);
      const [updateMessage,setUpdateMessage]=useState('');
      const manualUpdate=useRef(false);
      async function checkUpdates(){
        if(manualUpdate.current)return;
        manualUpdate.current=true;
        const generation=++updateGeneration.current;
        setUpdateBusy(true);setUpdateMessage('正在检查更新…');
        try{
          const value=await request('/updates',{});
          if(!alive.current||generation!==updateGeneration.current)return;
          showUpdate(value,true);
          setUpdateMessage(updateNotice(value));
        }catch{
          if(alive.current)setUpdateMessage('暂时无法检查更新，请稍后重试。');
        }finally{
          manualUpdate.current=false;
          if(alive.current)setUpdateBusy(false);
        }
      }
      function showUpdate(value,manual=false){
        if(value.status==='unavailable')return;
        const update=value.update;
        setAvailableUpdate(update&&(manual||localStorage.getItem('kgxc-update-dismissed')!==update.version)?update:null);
      }
      useEffect(()=>{
        let live=true,timer;
        const check=async()=>{
          if(!live)return;
          const generation=updateGeneration.current;
          let delay=2*60*1000;
          try{
            const value=await request('/updates');
            if(!live)return;
            if(generation===updateGeneration.current)showUpdate(value);
            if(value.status==='checked')delay=15*60*1000;
            if(Number.isFinite(value.checked_at))delay=Math.max(1000,delay-Math.max(0,Date.now()-value.checked_at));
          }catch{/* Checking for updates must not interrupt course production. */}
          if(live)timer=setTimeout(check,delay);
        };
        void check();
        return()=>{live=false;clearTimeout(timer);};
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
        if(!active||active.delivery_only||running||sessionStatus?.pendingInteraction||confirmationInFlight.current||(pendingConfirmation&&!pendingConfirmation.decision_status&&!confirmation)||!stageMeta?.waiting_decisions?.length||!current())return;
        const key=active.course_path+':'+JSON.stringify(stageMeta.waiting_decisions);
        if(requestedQuestions.current.has(key))return;
        requestedQuestions.current.add(key);setChatOpen(true);localStorage.setItem('kgxc-chat-open','true');
        request('/editor',{action:'stage',arguments:{course_path:active.course_path,session_id:sessionId,target_stage:'questions',context_stage:stage,instruction:'主动调用 ask_user_question，只展示当前方案已保存且尚未回答的选择。当前待选ID：'+stageMeta.waiting_decisions.map(d=>d.id).join('、')+'。不改课程、不推进阶段、不重新询问已回答或已委托决定的事项。'}}).catch(error=>{requestedQuestions.current.delete(key);if(current())setError(error.message);});
      },[active?.course_path,stageMeta?.waiting_decisions,running,sessionStatus?.pendingInteraction,confirmation?.status]);
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
      useEffect(()=>{setStageMeta(null);setRequestedStage(null);if(!active){setStage('sources');setFinalPhase('body');return;}const remembered=localStorage.getItem('kgxc-stage:'+active.course_path);setStage(STAGES.some(([key])=>key===remembered)?remembered:STAGES.some(([key])=>key===active.workflow?.stage)?active.workflow.stage:'outline');setFinalPhase(localStorage.getItem('kgxc-final-phase:'+active.course_path)==='post'?'post':'body');},[active?.course_path]);
      function selectFinalPhase(phase){setFinalPhase(phase);if(active)localStorage.setItem('kgxc-final-phase:'+active.course_path,phase);}
      async function navigateStage(next,phase){try{await prepareLeave();if(!current())return;if(next===stage&&(!phase||phase===finalPhase)){frameEpoch.current++;setActive(value=>value&&({...value}));}if(next!==stage)setStageMeta(null);if(phase)selectFinalPhase(phase);setStage(next);if(active)localStorage.setItem('kgxc-stage:'+active.course_path,next);}catch(e){setError(e.message);}}
      async function prepareLeave(){
        if(!active||active.delivery_only||!frame.current)return;
        const live=await request('/workspace',{action:'workbench_live',session_id:sessionId,course_path:active.course_path});
        if(!current())return;
        if(live.alive===false){
          const attempt=++generation.current,course=await call('kgxc_course_resume',{course_path:active.course_path});
          if(current()&&attempt===generation.current){frameEpoch.current++;setActive(course);setStageMeta(null);}
          return;
        }
        const id=crypto.randomUUID();
        await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{leaving.current.delete(id);reject(Error('草稿尚未保存，请稍后再切换。'));},20000);leaving.current.set(id,{resolve,reject,timer});frame.current.contentWindow.postMessage({type:'kgxc-editor-leave',id},new URL(active.workbench_url).origin);});
      }
      const [courseOffer,setCourseOffer]=useState(null);
      const switchInFlight=useRef(false);
      async function open(path,{separate=false}={}){
        if(switchInFlight.current||!path)return;
        if(path===active?.course_path){await refresh();return;}
        switchInFlight.current=true;
        setError('');try{
          const workspaceList=ctx.uiWorkspace.workspaces.list.getSnapshot().items;
          const known=workspaceList.flatMap(item=>item.sessionIds||[]);
          const owner=await request('/editor',{action:'course-session',arguments:{course_path:path,session_ids:known}});
          if(!current())return;
          if(owner.session_id){
            if(!known.includes(owner.session_id))throw Error('这门课已有独立对话。请从 DSH 会话列表打开原对话，避免另开一份。');
            await prepareLeave();if(!current())return;
            setCourseOffer(null);ctx.uiWorkspace.openSession(owner.session_id);ctx.layout.selectPanel('kgxc-course');return;
          }
          if(!separate){
            setCourseOffer({path,title:courses.find(item=>item.course_path===path)?.title||'该课程'});
            return;
          }
          await prepareLeave();if(!current())return;
          const attempt=++generation.current;setLoading(true);
          const workspace=workspaceList.filter(item=>item.path&&path.startsWith(item.path+'/')).sort((a,b)=>b.path.length-a.path.length)[0]||
            workspaceList.find(item=>item.sessionIds?.includes(sessionId)||item.path===session?.cwd)||await ctx.uiWorkspace.workspaces.initializeDefault();
          if(!current()||attempt!==generation.current)return;
          const id=await ctx.uiWorkspace.sessions.create({workspaceId:workspace.workspaceId});
          if(!current()||attempt!==generation.current)return;
          const selected=await request('/editor',{action:'attach-course',arguments:{course_path:path,session_id:id}});
          if(!current()||attempt!==generation.current)return;
          setCourseOffer(null);ctx.uiWorkspace.openSession(selected.session_id);ctx.layout.selectPanel('kgxc-course');
        }catch(e){if(current())setError(e.message);}
        finally{switchInFlight.current=false;if(current())setLoading(false);}
      }
      function startOnboarding(mode){
        if(!sessionId){void newCourse(mode);return;}
        if(loading||running||sessionStatus?.pendingInteraction)return;
        openQuestionPane();
        setOnboarding({mode,sessionId});
      }
      async function newCourse(mode){
        setError('');try{
          await prepareLeave();if(!current())return;
          const workspace=ctx.uiWorkspace.workspaces.list.getSnapshot().items.find(item=>item.sessionIds.includes(sessionId)||item.path===session?.cwd)||await ctx.uiWorkspace.workspaces.initializeDefault();
          const id=await ctx.uiWorkspace.sessions.create({workspaceId:workspace.workspaceId});
          if(!current())return;
          if(typeof mode==='string'&&Object.hasOwn(ONBOARDING_PROMPTS,mode))onboardingSessions.set(id,{mode,sessionId:id});
          openQuestionPane();ctx.uiWorkspace.openSession(id);ctx.layout.selectPanel('kgxc-course');
        }catch(e){if(current())setError(e.message);}
      }
      async function moveIntoWorkspace(){
        try{setError('');await prepareLeave();if(!current())return;setLoading(true);const value=await request('/workspace',{action:'relocate',session_id:sessionId,course_path:active?.course_path});if(current()){setActive(value);setLoading(false);}}
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
        try{const value=await request('/workspace',{action:'cleanup_preview',session_id:sessionId,course_path:course.course_path});if(value.preview.course_path&&value.preview.course_path!==course.course_path)throw Error('当前课程已切换，过程文件保持原样，请重新打开选择。');if(current()&&attempt===generation.current){setRetentionPrompt(previous=>previous&&previous.course.course_path===course.course_path?({...previous,preview:value.preview,previewLoading:false}):previous);return true;}}
        catch(error){if(current()&&attempt===generation.current)setRetentionPrompt(previous=>previous&&({...previous,preview:null,previewLoading:false,previewError:error.message}));}return false;
      }
      async function chooseRetention(choice){
        if(!current()||retentionBusy||!retentionPrompt)return;
        setRetentionBusy(true);
        try{const value=await request('/workspace',{action:'retention',session_id:sessionId,course_path:retentionPrompt.course.course_path,choice,request_id:retentionPrompt.preview?.request_id});if(current()){setActive(value);setRetentionPrompt(null);}}
        catch(error){if(current())setRetentionPrompt(previous=>previous&&({...previous,error:error.message}));}
        finally{if(current())setRetentionBusy(false);}
      }
      async function resumeEngineering(){try{await open(active.course_path);selectFinalPhase('post');setStage('final');}catch(error){setError(error.message);}}
      async function openSavedFolder(){try{await request('/workspace',{action:'open_delivery',session_id:sessionId,course_path:active?.course_path});if(current())setError('');}catch(error){if(current()){if(retentionPrompt)setRetentionPrompt(previous=>previous&&({...previous,error:error.message}));else setError(error.message);}}}
      useEffect(()=>{
        if(!active||active.delivery_only)return;
        const origin=new URL(active.workbench_url).origin;
        if(frame.current)ownedFrames.set(frame.current.contentWindow,{origin,path:active.course_path});
        const receive=async event=>{
          if(event.source!==frame.current?.contentWindow||event.origin!==origin)return;
          if(event.data?.type==='kgxc-editor-ready'){event.source.postMessage({type:'kgxc-editor-host',draft:savedDraft(active.course_path),running:runningRef.current},origin);if(productionRef.current?.course_path===active.course_path)event.source.postMessage({type:'kgxc-editor-production',...productionRef.current},origin);event.source.postMessage(questionPresentationRef.current,origin);return;}
          if(event.data?.type==='kgxc-studio-state'&&event.data.course_path===active.course_path){setStageMeta(previous=>!previous||(event.data.revision||0)>=(previous.revision||0)?event.data:previous);return;}
          if(event.data?.type==='kgxc-editor-feedback'&&event.data.course_path===active.course_path){
            const {stage:feedbackStage,segment_id,time,artifact_path,artifact_sha256,location_label}=event.data;
            if(!['script','pilot','final'].includes(feedbackStage))return;
            openFeedback({course_path:active.course_path,stage:feedbackStage,segment_id,time,artifact_path,artifact_sha256,location_label,
              question_id:stageMeta?.pending_confirmations?.find(item=>item.stage===feedbackStage&&item.decision_status==='changes_requested')?.id});
            return;
          }
          if(event.data?.type==='kgxc-editor-leave-result'){const item=leaving.current.get(event.data.id);if(item){clearTimeout(item.timer);leaving.current.delete(event.data.id);event.data.error?item.reject(Error(event.data.error)):item.resolve();}return;}
          if(event.data?.type!=='kgxc-editor-request'||event.data.course_path!==active.course_path)return;
          const {id,action,...args}=event.data;
          if(action==='review'){
            try{const result=await request('/review',{...args,action:args.review_action,session_id:sessionId,course_path:active.course_path});event.source.postMessage({type:'kgxc-editor-result',id,result},origin);}
            catch(error){event.source.postMessage({type:'kgxc-editor-result',id,error:error.message},origin);}return;
          }
          if(action==='deliver'){
            try{if(runningRef.current)throw Error('请等待当前 AI 制作结束后再保存交付文件。');const value=await request('/workspace',{action:'deliver',session_id:sessionId,course_path:active.course_path});event.source.postMessage({type:'kgxc-editor-result',id,result:value},origin);if(value.ok){setActive(value);setStage('final');setStageMeta(null);if(value.delivery?.cleanup_decision?.choice!=='keep')void showRetention(value);}}
            catch(error){event.source.postMessage({type:'kgxc-editor-result',id,error:error.message},origin);}return;
          }
          if(!['rewrite','cancel','render','stage'].includes(action))return;
          try{if(['stage','render'].includes(action)&&runningRef.current)throw Error('当前 AI 正在制作，请等待结束，或在右侧停止后重试。');const result=await request('/editor',{action,arguments:{...args,session_id:sessionId}});event.source.postMessage({type:'kgxc-editor-result',id,result},origin);if(action==='stage'&&STAGES.some(([key])=>key===result.target_stage)){setRequestedStage(result.target_stage);if(result.target_stage==='final'&&args.context_stage!=='final')selectFinalPhase('body');setStage(result.target_stage);localStorage.setItem('kgxc-stage:'+active.course_path,result.target_stage);}}
          catch(e){event.source.postMessage({type:'kgxc-editor-result',id,error:e.message},origin);}
        };
        const element=frame.current,nativeReceive=event=>receive({source:element.contentWindow,origin,data:event.detail});
        element?.addEventListener?.('kgxc-message',nativeReceive);
        element?.contentWindow?.postMessage({type:'kgxc-editor-host',draft:savedDraft(active.course_path),running:runningRef.current},origin);
        window.addEventListener('message',receive);return()=>{window.removeEventListener('message',receive);element?.removeEventListener?.('kgxc-message',nativeReceive);};
      },[active,stageMeta?.pending_confirmations]);
      const retryStatus=pendingConfirmation&&confirmation?.key===active?.course_path+':'+pendingConfirmation.id?confirmation.status:pendingConfirmation?.decision_status;
      const reask=Boolean(pendingConfirmation&&!stageMeta?.unsaved_edits&&['failed','skipped','deferred','changes_requested','not_requested'].includes(retryStatus));
      const shownFeedback=feedbackDraft?.course_path===active?.course_path?feedbackDraft:null;
      const submitting=shownFeedback&&feedbackState?.id===shownFeedback.id&&feedbackState.status==='submitting';
      const changesPrompt=pendingConfirmation&&retryStatus==='changes_requested';
      const stageLabel=key=>({script:'逐字稿',pilot:'有声小样',final:'成片'})[key]||'课程';
      const locateSeconds=value=>{const seconds=Math.floor(value);return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0');};
      const feedbackLocation=shownFeedback&&(shownFeedback.location_label||(typeof shownFeedback.time==='number'?'视频内 '+locateSeconds(shownFeedback.time):stageLabel(shownFeedback.stage)+' · 当前版本'));
      const confirmedHere=confirmation?.course_path===active?.course_path&&confirmation?.status==='confirmed'&&
        (confirmation.stage===stage||displayStatus==='confirmed');
      const confirmedNext={script:'接下来可以继续分镜制作。',pilot:'接下来可以开始制作完整视频。',final:'接下来可以保存并交付成片。'}[confirmation?.stage];
      const rightActions=(confirmedHere||retryStatus==='deferred'||changesPrompt||shownFeedback||(feedbackState?.status==='requested'&&feedbackState.course_path===active?.course_path))&&h('section',{className:'kgxc-chat-checkpoint','aria-label':'当前确认与反馈'},
        confirmedHere&&h('p',{role:'status'},stageLabel(confirmation.stage)+'已确认。'+(confirmedNext||'')),
        retryStatus==='deferred'&&h('p',{role:'status'},'已记为稍后确认，暂不进入下一阶段。'),
        changesPrompt&&!shownFeedback&&h('button',{type:'button',onClick:()=>openFeedback({course_path:active.course_path,stage:pendingConfirmation.stage,question_id:pendingConfirmation.id,label:pendingConfirmation.label,feedback:pendingConfirmation.feedback})},'填写修改意见'),
        feedbackState?.status==='requested'&&feedbackState.course_path===active?.course_path&&!shownFeedback&&h('p',{role:'status'},'修改意见已交给 AI。'),
        shownFeedback&&h('form',{onSubmit:submitFeedback},h('label',null,'修改意见 · '+feedbackLocation,h('textarea',{autoFocus:true,maxLength:8000,rows:3,value:shownFeedback.text,disabled:submitting||feedbackState?.status==='saved',placeholder:'写明哪里有问题、希望怎样改',onChange:event=>setFeedbackDraft(previous=>({...previous,text:event.target.value}))})),
          feedbackState?.id===shownFeedback.id&&['saved','failed'].includes(feedbackState.status)&&h('p',{role:'status'},(feedbackState.status==='saved'?'已保存，尚未启动修改：':'未提交：')+(feedbackState.message||'')),
          h('div',null,h('button',{type:'submit',disabled:submitting||!shownFeedback.text.trim()||Boolean(stageMeta?.unsaved_edits)},submitting?'正在提交…':feedbackState?.status==='saved'?'重试交给 AI':'提交给 AI 修改'),
            h('button',{type:'button',disabled:submitting,onClick:()=>setFeedbackDraft(null)},'关闭'))));
      const url=active&&!active.delivery_only?active.workbench_url+'/studio.html?stage='+stage+(stage==='final'?'&phase='+finalPhase:'')+'&parentOrigin='+encodeURIComponent(location.origin):null;
      const tabLabel=TABS.find(([key,,phase])=>key===stage&&(!phase||phase===finalPhase))?.[1]||'工作台';
      return h('section',{className:'kgxc-panel','aria-label':'课程工作台'},
        h('div',{className:'kgxc-switch kgxc-window-drag'},h('button',{onClick:newCourse,disabled:loading},'新建课程'),h('label',{htmlFor:'kgxc-course'},active?'当前课程':'继续已有课程'),h('select',{id:'kgxc-course',value:active?.course_path||'',disabled:loading||!sessionId,onChange:e=>e.target.value&&open(e.target.value)},h('option',{value:'',disabled:true},'选择已有课程…'),courses.map(c=>h('option',{key:c.course_id,value:c.course_path},c.title))),active&&!active.delivery_only&&workspacePath&&!active.course_path.startsWith(workspacePath+'/')&&h('button',{onClick:moveIntoWorkspace,disabled:loading},'工程迁入当前工作区'),h('button',{type:'button',className:'kgxc-chat-toggle',onClick:toggleChat,'aria-expanded':chatOpen,'aria-controls':'kgxc-ai-chat'},chatOpen?'收起 AI 对话':'打开 AI 对话'),h('button',{type:'button',className:'kgxc-update-top',disabled:updateBusy,'aria-busy':updateBusy,onClick:()=>void checkUpdates()},updateBusy?'正在检查…':'检查更新')),
        updateMessage&&h('div',{className:'kgxc-update-status',role:'status'},updateMessage),
        courseOffer&&h('div',{className:'kgxc-update-notice',role:'status'},h('span',null,'「'+courseOffer.title+'」没有独立对话。当前课程和运行中的任务不会被切换。'),h('button',{type:'button',disabled:loading,onClick:()=>void open(courseOffer.path,{separate:true})},'为该课程打开独立对话'),h('button',{type:'button',onClick:()=>setCourseOffer(null)},'取消')),
        (availableUpdate||updateInstall.state.phase!=='idle')&&h('div',{className:'kgxc-update-notice'},availableUpdate&&updateInstall.state.phase==='idle'&&h('span',null,'课程插件有新稳定版 '+availableUpdate.version+'。'),
          updateControls(updateInstall,availableUpdate,{busy:running||Boolean(sessionStatus?.pendingInteraction)||Boolean(stageMeta?.producing),save:async()=>{try{await prepareLeave();}catch(error){setUpdateMessage(error.message);throw error;}}}),
          availableUpdate&&updateInstall.state.phase==='idle'&&h('button',{type:'button',onClick:dismissUpdate,'aria-label':'忽略此版本更新提醒'},'稍后')),
        error&&h('div',{className:'kgxc-error',role:'alert'},error),
        active&&!active.delivery_only&&h('nav',{className:'kgxc-stages',role:'tablist','aria-label':'制课阶段'},TABS.map(([key,label,phase])=>h('button',{key:phase||key,role:'tab','aria-selected':stage===key&&(!phase||phase===finalPhase),onClick:()=>navigateStage(key,phase)},h('strong',null,label)))),
        h('div',{className:'kgxc-layout',ref:layout,style:{'--kgxc-chat-width':chatWidth+'px'}},h('div',{className:'kgxc-editor'},active?(active.delivery_only?h(DeliveryView,{course:active,onRetention:()=>showRetention(),onResume:resumeEngineering,onOpenFolder:openSavedFolder}):h('kgxc-studio-view',{class:'kgxc-frame kgxc-native',ref:frame,'session-id':sessionId,'course-path':active.course_path,key:active.course_path+':'+frameEpoch.current,title:'课程'+tabLabel,src:url})):h('div',{className:'kgxc-empty'},h('h1',null,loading?'正在打开课程…':'开始一门新课程'),!loading&&h('div',{className:'kgxc-onboarding'},h('p',null,'上传讲稿、文档或实拍照片，或说说你想教什么。发送后，AI 先给你一份可编辑的大纲，不会直接做视频。'),h('div',{className:'kgxc-onboarding-actions'},h('button',{type:'button',className:'kgxc-onboarding-primary',disabled:running||Boolean(sessionStatus?.pendingInteraction),onClick:()=>startOnboarding('upload')},'上传资料，开始做课'),h('button',{type:'button',disabled:running||Boolean(sessionStatus?.pendingInteraction),onClick:()=>startOnboarding('describe')},'描述课程，开始做课')),h('p',{className:'kgxc-onboarding-hint'},'已有课程？可从上方选择继续制作。')))),chatOpen&&h('div',{className:'kgxc-divider',role:'separator','aria-label':'调整 AI 对话栏宽度','aria-orientation':'vertical',onPointerDown:resize}),chatOpen&&h('aside',{id:'kgxc-ai-chat',className:'kgxc-chat','aria-label':'课程 AI 对话'},h('div',{className:'kgxc-chat-head'},h('strong',null,'AI 对话'),reask&&h('button',{type:'button',title:confirmation?.error||undefined,disabled:running||Boolean(sessionStatus?.pendingInteraction),onClick:()=>void askConfirmation(pendingConfirmation,true)},'重新打开'+pendingConfirmation.label+'确认'),h('button',{onClick:toggleChat,'aria-label':'收起 AI 对话'},'收起')),rightActions,renderSlot('kgxc.chat',{coursePath:active?.delivery_only?undefined:active?.course_path,courseTitle:active?.workflow?.title,onCourseUpdate:refresh,onboarding:!active?onboarding:null,onboardingHandled:()=>setOnboarding(null)}))),
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
    function Chat({ctx,coursePath,courseTitle,onCourseUpdate,sessionId,useSession,useConversation,useSessions,useInput,inputActions,renderFactorySlot,onboarding,onboardingHandled}){
      const session=useSession(value=>value),conversation=useConversation(value=>value);
      const summaryBlank=useSessions(value=>sessionId===undefined?undefined:value.byId[sessionId]?.blank);
      const [message,setMessage]=useState(''),[picking,setPicking]=useState(false);
      const draft=useInput?.(value=>value?.draft),intake=useRef(null),chatBody=useRef(null);
      useEffect(()=>{
        if(!onboarding||onboarding.sessionId!==sessionId||intake.current===onboarding)return;
        intake.current=onboarding;
        let disposed=false,timer,attempts=0;
        // Keep the user's existing draft. This prepares the real composer and never submits.
        if(inputActions&&typeof draft==='string'&&!draft.trim()){
          try{inputActions.insertText(ONBOARDING_PROMPTS[onboarding.mode],inputActions.captureInsertion());}catch{}
        }
        const focusComposer=()=>chatBody.current?.querySelector('[contenteditable="true"],textarea')?.focus();
        const ready=()=>{
          if(disposed)return;
          if(onboarding.mode==='upload'){
            if(ctx.conversation.input.canPickFiles(sessionId)){
              try{ctx.conversation.input.pickFiles(sessionId);}
              catch(error){setMessage('未能打开选择窗口。可点击右侧「上传文件」重试。');}
            }else if(attempts++<12){timer=setTimeout(ready,75);return;}
            else setMessage('文件选择尚未就绪，可点击右侧「上传文件」重试。');
          }else focusComposer();
          onboardingHandled?.();
        };
        timer=setTimeout(ready,0);
        return()=>{disposed=true;clearTimeout(timer);if(intake.current===onboarding)intake.current=null;};
      },[onboarding,sessionId]);
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
      return h('div',{className:'kgxc-chat-body',ref:chatBody},h('div',{className:'kgxc-chat-tools'},h('button',{onClick:chooseFolder,disabled:picking},picking?'正在选择…':'引用文件夹'),h('button',{onClick:chooseFiles,disabled:!sessionId},'上传文件')),h('p',{className:'kgxc-chat-note'},courseTitle?'当前课程：'+courseTitle:'沿用 DSH 当前对话，可发送资料开始制课。'),message&&h('p',{className:'kgxc-chat-error',role:'alert'},message),h('div',{className:'kgxc-chat-native'},renderFactorySlot('conversation.content',{variant:'embedded',phase,hero:phase==='hero'},{slots:{views:ChatView}})));
    }
    const ONBOARDING_UPDATE_CSS=`.kgxc-plugin-update-action{display:flex;align-items:center;flex-wrap:wrap;gap:7px;font-size:12px;color:inherit}.kgxc-plugin-update-action button{font:inherit;color:inherit;cursor:pointer;background:transparent;border:1px solid #a9b1c277;border-radius:7px;padding:5px 8px}.kgxc-plugin-update-action button:disabled{opacity:.65;cursor:default}.kgxc-update-flow{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap}.kgxc-update-flow progress{width:100px;height:8px}.kgxc-plugin-update-action a{color:inherit;text-decoration:underline}`;
    function PluginUpdateAction({subject}){
      const own=subject?.kind==='bundle'&&subject.pkg?.name==='kgxc-course-plugin';
      const [result,setResult]=useState(null),[busy,setBusy]=useState(false);
      const flow=useUpdateInstall(own);
      const live=useRef(false),pending=useRef(false);
      useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);
      if(!own)return null;
      async function check(){
        if(pending.current)return;
        pending.current=true;setBusy(true);setResult(null);
        try{const value=await request('/updates',{});if(live.current)setResult(value);}
        catch{if(live.current)setResult({status:'unavailable'});}
        finally{pending.current=false;if(live.current)setBusy(false);}
      }
      const update=result?.update;
      return h('div',{className:'kgxc-plugin-update-action'},
        h('button',{type:'button',disabled:busy,onClick:()=>void check()},busy?'正在检查 GitHub…':'检查 GitHub 更新'),
        result&&h('span',{role:'status'},updateNotice(result,true)),
        updateControls(flow,update));
    }
    function apply(ctx){
      defineNativeStudio();
      ctx.effect(()=>{const style=document.createElement('style');style.dataset.plugin='kgxc-course-plugin';style.textContent=CSS+QUESTION_CSS+ONBOARDING_UPDATE_CSS+`.kgxc-stages{display:grid;grid-template-columns:repeat(6,minmax(95px,1fr));overflow-x:auto;flex-shrink:0;background:#fafbfc;border-bottom:1px solid #e1e5eb}.kgxc-stages button{border:0;border-right:1px solid #e6e9ee;background:transparent;padding:13px 15px;cursor:pointer;text-align:left;color:#525d6b}.kgxc-stages button[aria-selected=true]{background:#edf2fa;box-shadow:inset 0 -2px #6682b6;color:#324e7e}.kgxc-stages strong,.kgxc-stages span{display:block;font-size:13px}.kgxc-stages span{font-size:10px;color:#8a929d;margin-top:4px}.kgxc-panel{font-family:Inter,"PingFang SC",sans-serif;background:#f6f6f8;color:#17191f}.kgxc-switch{padding:12px 24px;background:#fff;border-color:#e9e9ed;gap:14px}.kgxc-switch::before{content:'K / STUDIO';font-size:11px;letter-spacing:.12em;font-weight:800;color:#17191f;margin-right:12px}.kgxc-switch label{display:none}html[data-platform="darwin"]:not([data-fullscreen]) .kgxc-window-drag{-webkit-app-region:drag;app-region:drag}html[data-platform="darwin"]:not([data-fullscreen]) .kgxc-window-drag :is(button,select,input,textarea,a,label,[role="button"],[tabindex],[contenteditable]){-webkit-app-region:no-drag;app-region:no-drag}.kgxc-switch .kgxc-update-top{margin-inline-start:auto;white-space:nowrap}.kgxc-update-status{flex-shrink:0;padding:4px 24px;text-align:right;font-size:12px;color:#565c65}.kgxc-switch button{border:1px solid #e4e4e9;background:#fff;border-radius:8px;padding:6px 11px;color:#40434e}.kgxc-stages{background:#fff!important;border-color:#e9e9ed!important;padding:0 24px;gap:12px;display:flex!important}.kgxc-stages button{border:0!important;border-radius:0!important;padding:10px 4px!important;color:#8a8e99!important;min-width:60px}.kgxc-stages button[aria-selected=true]{background:transparent!important;box-shadow:inset 0 -2px #2455ee!important;color:#2455ee!important}.kgxc-stages strong{font-size:12px!important;font-weight:500}.kgxc-stages span{display:none!important}.kgxc-chat{background:#fff;border-color:#e8e8ee}.kgxc-chat-head{padding:20px 22px;border-bottom:0}.kgxc-chat-head strong{font-size:14px;color:#20232c}.kgxc-chat-note{display:none}.kgxc-chat-tools{padding:0 22px 10px}.kgxc-chat button{border-radius:8px;border-color:#e5e5eb}.kgxc-chat-checkpoint{margin:0 16px 12px;padding:12px;border:1px solid #e4e8f1;border-radius:9px;background:#f8faff}.kgxc-chat-checkpoint p{margin:0 0 6px}.kgxc-chat-checkpoint textarea{box-sizing:border-box;display:block;width:100%;margin:5px 0 9px;padding:7px;font:inherit;border:1px solid #cad2e1;border-radius:6px;resize:vertical}.kgxc-chat-checkpoint form button+button{margin-left:6px}.kgxc-divider{background:#ececf1;width:4px}.kgxc-chat-toggle{color:#424759!important}.kgxc-native{background:#f6f6f8}@media(max-width:800px){.kgxc-layout{position:relative}.kgxc-editor{min-width:0}.kgxc-chat{position:absolute;right:0;top:0;bottom:0;width:min(360px,100%);max-width:100%;min-width:0;z-index:30;box-shadow:-12px 0 35px #1a234415}.kgxc-divider{display:none}}`;document.head.appendChild(style);return()=>style.remove();},'kgxc-course: editor styles');
      ctx.effect(()=>{document.addEventListener('click',submitLastChoice,true);return()=>document.removeEventListener('click',submitLastChoice,true);},'kgxc-course: submit last explicit choice');
      ctx.effect(()=>{const receive=event=>{const owner=ownedFrames.get(event.source),data=event.data;if(!owner||owner.origin!==event.origin||data?.type!=='kgxc-editor-draft'||data.course_path!==owner.path)return;if(data.dirty){localStorage.setItem(draftKey(owner.path),JSON.stringify({text:data.text,base_text:data.base_text,base_revision:data.base_revision}));}else if(savedDraft(owner.path)?.text===data.text)localStorage.removeItem(draftKey(owner.path));};window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive);},'kgxc-course: preserve pending manual edits');
      ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:'kgxc-course',children:{'kgxc.workspace':{kind:'single',scope:'session-maybe'}}},Workspace));
      ctx.slots.inject('kgxc.workspace',()=>ctx.slots.register({name:'kgxc.workspace',inject:()=>({ctx}),children:{'kgxc.chat':{kind:'single',scope:'session-maybe'}}},SessionPanel));
      ctx.slots.inject('plugins.detail.actions',()=>ctx.slots.register({name:'plugins.detail.actions',id:'kgxc-course-github-update',order:15},PluginUpdateAction));
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
