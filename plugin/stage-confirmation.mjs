/** The browser can request a card, but only the native user question service can submit an answer. */
export function createStageConfirmationHost(ctx,{review,resolveCourse,dispatchFeedback,logger=ctx.logger}){
  const pending=new Map(),controllers=new Set(),feedbackRuns=new Map();
  const keyOf=(session,path,id)=>JSON.stringify([session,path,id]);
  const stageValid=stage=>['script','pilot','final'].includes(stage);
  function prune(){
    const oldest=Date.now()-30*60*1000;
    for(const [key,value] of pending)if(value.status!=='pending'&&value.at<oldest)pending.delete(key);
  }
  async function handle(action,args={}){
    prune();
    const {session_id,course_path,stage,question_id}=args;
    const feedbackAction=action==='stage-feedback-submit';
    if(typeof session_id!=='string'||typeof course_path!=='string'||!stageValid(stage)||(!feedbackAction&&!/^kgxc-confirm-[a-f0-9]{36}$/.test(question_id||'')))throw Error('确认问题参数无效。');
    const get=name=>ctx.get?.(name);
    const registry=get('agents'),agent=registry?.get(session_id);
    if(!agent||agent.session?.id!==session_id||resolveCourse(session_id,agent.session)!==course_path)throw Error('课程或对话已切换，请查看当前课程。');
    if(feedbackAction){
      if(!/^[0-9a-f-]{36}$/.test(args.feedback_id||''))throw Error('反馈标识无效。');
      const feedbackKey=keyOf(session_id,course_path,args.feedback_id);
      if(feedbackRuns.has(feedbackKey))return feedbackRuns.get(feedbackKey);
      const started=(async()=>{
        const saved=await review('stage_feedback_save',args);
        if(!saved.ok)throw Error(saved.error);
        if(registry.get(session_id)!==agent||resolveCourse(session_id,agent.session)!==course_path)
          return {ok:true,status:'saved',error_message:'课程已切换，修改意见已保存，未启动制作。',feedback:saved.feedback};
        try{
          const spec=await review('stage_feedback_dispatch_spec',{course_path,feedback_id:args.feedback_id});
          if(!spec.ok)throw Error(spec.error);
          if(spec.dispatch_status==='requested')return {ok:true,status:'requested',feedback:saved.feedback};
          if(agent.status==='running')throw Error('AI 正在执行其他工作，请稍后重试。');
          if(typeof dispatchFeedback!=='function')throw Error('当前工作台未接通修改执行。');
          await dispatchFeedback({course_path,session_id,feedback:spec.feedback});
          try{
            const receipt=await review('stage_feedback_dispatched',{course_path,feedback_id:args.feedback_id});
            if(!receipt.ok)throw Error(receipt.error);
          }catch(error){logger?.warn?.('反馈已交给 AI，登记启动回执失败：'+error.message);}
          return {ok:true,status:'requested',feedback:saved.feedback};
        }catch(error){return {ok:true,status:'saved',error_message:error.message,feedback:saved.feedback};}
      })();
      feedbackRuns.set(feedbackKey,started);
      started.then(value=>{if(value.status!=='requested')feedbackRuns.delete(feedbackKey);},()=>feedbackRuns.delete(feedbackKey));
      return started;
    }
    const key=keyOf(session_id,course_path,question_id),existing=pending.get(key);
    const view=result=>({ok:true,status:result?.status||'not_requested',...(result?.error?{error_message:result.error}:{})});
    if(action==='stage-confirmation-status')return view(existing);
    if(action==='stage-confirmation-cancel'){
      if(existing?.status==='pending'){existing.status='cancelled';existing.controller.abort();}
      return view(existing);
    }
    if(action!=='stage-confirmation-request')throw Error('未知确认问题操作。');
    if(existing?.status==='pending'||existing?.status==='confirmed')return view(existing);
    if(agent.status==='running')return {ok:true,status:'busy'};
    const service=get('userQuestions');
    if(typeof service?.ask!=='function')throw Error('当前 DSH 宿主没有原生问答服务，未记录任何确认。');
    for(const [otherKey,other] of pending)if(otherKey!==key&&other.session_id===session_id&&other.status==='pending'){
      other.status='cancelled';other.controller.abort();
    }
    const controller=new AbortController(),attempt={status:'pending',at:Date.now(),session_id,controller};
    pending.set(key,attempt);controllers.add(controller);
    // Acquire the in-flight slot before the first await to coalesce simultaneous clients.
    void (async()=>{
      try{
        const spec=await review('stage_confirmation_request',{course_path,stage,question_id});
        if(!spec.ok)throw Error(spec.error);
        if(registry.get(session_id)!==agent||resolveCourse(session_id,agent.session)!==course_path)throw Error('课程或对话已切换，请查看当前课程。');
        const result=await service.ask({agent,signal:controller.signal,questions:[spec.question]});
        if(controller.signal.aborted||registry.get(session_id)!==agent||resolveCourse(session_id,agent.session)!==course_path)throw Error('课程或对话已切换，本次未确认。');
        const answer=Array.isArray(result?.answers)&&result.answers.length===1?result.answers[0]:null;
        if(!answer||answer.id!==question_id||answer.custom?.trim()||!Array.isArray(answer.selected)||answer.selected.length!==1||!spec.question.options.some(o=>o.label===answer.selected[0])){
          attempt.status='skipped';return;
        }
        const value=await review('stage_confirmation_answer',{course_path,stage,question_id,selected:answer.selected[0]});
        if(!value.ok)throw Error(value.error);
        attempt.status=value.status;
      }catch(error){if(controller.signal.aborted)return;attempt.status='failed';attempt.error=error.message;logger?.warn?.('课程确认问答未完成：'+error.message);}
      finally{attempt.at=Date.now();controllers.delete(controller);}
    })();
    return view(attempt);
  }
  handle.courseBusy=path=>[...pending.entries()].some(([key,value])=>value.status==='pending'&&JSON.parse(key)[1]===path);
  handle.dispose=()=>{for(const controller of controllers)controller.abort();controllers.clear();};
  return handle;
}
