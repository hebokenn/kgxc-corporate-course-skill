import {randomBytes, timingSafeEqual,randomUUID} from 'node:crypto';
import {readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
import {root, tools, callTool, callWorkspace, callReview, pythonExecutable} from './bridge.mjs';
import {editorHost} from './editor-host.mjs';
import {SessionCourses} from './session-courses.mjs';
import {serveDelivery} from './delivery-files.mjs';
import {z} from 'zod';
import {productionProjection,productionSnapshot} from './production-monitor.mjs';
import {reviewHost} from './review-host.mjs';
import {studioProxy} from './studio-proxy.mjs';
import {updateChecker,getStableRelease} from './update-check.mjs';
import {createUpdateInstaller} from './update-install.mjs';
import {createStageConfirmationHost} from './stage-confirmation.mjs';

const version = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version;

export const name = 'kgxc-course';
export const inject = ['tools'];
export function apply(ctx) {
  const checkUpdate=updateChecker({version});
  const bindings = new Map();
  const courses = new SessionCourses();
  const sessionOf=id=>ctx.get?.('agents')?.get(id)?.session||ctx.get?.('sessions')?.get(id);
  const courseOf=id=>courses.resolve(id,sessionOf(id)).course_path;
  const attaching=new Map(),attachingCourse=new Set(),relocating=new Set();
  const reviews=reviewHost(ctx,{bindings});
  function assertBound(args,path=args.course_path){
    if(!args.session_id||path!==courseOf(args.session_id)||relocating.has(path))throw Error('请求与本对话的当前课程不一致；没有更改任何课程。');
  }
  const editor = editorHost(ctx, bindings,callTool,{supervision:reviews,assertBound});
  const confirmations=createStageConfirmationHost(ctx,{review:callReview,resolveCourse:(id,session)=>courses.resolve(id,session).course_path,
    dispatchFeedback:({course_path,session_id,feedback:f})=>editor('stage',{course_path,session_id,target_stage:f.stage,
      segment_id:f.segment_id,time:f.version_binding.time,artifact_path:f.artifact_path,artifact_sha256:f.artifact_sha256,feedback_id:f.id,
      user_instruction:f.text,instruction:'用户通过右侧提交了这条针对当前版本的修改意见（已登记反馈 ID '+f.id+'）。只处理该意见及其关联范围，保留现有制作流程、审批与盲审边界；不要凭意见提交补填任何确认。'})
  });
  function updateBusyReason(){
    const agents=ctx.get?.('agents');
    if(typeof agents?.list!=='function')return '暂时无法确认 DSH 是否空闲，未开始安装。';
    const jobs=ctx.get?.('jobs');
    const liveAgents=agents.list();
    const hasJobs=[undefined,...liveAgents.map(agent=>agent.session?.id??agent.id).filter(Boolean)].some(id=>
      jobs?.list?.(id).some(job=>['running','stopping'].includes(job.status)));
    if(liveAgents.some(agent=>agent.status!=='idle')||hasJobs||attaching.size||relocating.size)
      return 'DSH 还有任务在运行。已下载更新，等任务完成后再安装。';
    const paths=new Set([...bindings.keys(),...Object.values(courses.entries).map(row=>row.course_path).filter(Boolean)]);
    for(const path of paths){
      if(reviews.courseBusy(path)||confirmations.courseBusy(path))return '课程仍在审阅或等待确认，完成后再安装。';
      const locks=join(path,'project','work','render-locks');
      try{
        for(const entry of readdirSync(locks,{withFileTypes:true})){
          if(!entry.isFile()||!entry.name.endsWith('.json'))continue;
          const lock=JSON.parse(readFileSync(join(locks,entry.name),'utf8'));
          if(lock.status!=='running')continue;
          if(!Number.isSafeInteger(lock.owner_pid)||lock.owner_pid<=0)throw Error('invalid render owner');
          try{process.kill(lock.owner_pid,0);return '课程正在渲染，完成后再安装。';}
          catch(error){if(error.code!=='ESRCH')throw error;}
        }
      }catch(error){if(error.code!=='ENOENT')return '暂时无法确认课程是否正在渲染，未开始安装。';}
    }
    return null;
  }
  const installer=createUpdateInstaller({version,getRelease:getStableRelease,busyReason:updateBusyReason,
    helperPath:join(root,'plugin','update-install-helper.py'),python:pythonExecutable()});
  ctx.on?.('dispose',()=>confirmations.dispose());
  ctx.on?.('session/event',(session,event)=>{
    const agent=ctx.get?.('agents')?.get(session.id);
    if(agent)void reviews.observe(agent,event).catch(error=>ctx.logger?.warn?.('课程监督已停止执行：'+error.message));
  });
  ctx.on?.('agent/status',({agent,status})=>{
    if(status==='idle')void reviews.onIdle(agent).catch(error=>ctx.logger?.warn?.('课程自动独立审阅未启动：'+error.message));
  });
  ctx.tools.guard?.(execution=>reviews.blockReason(execution.agent));
  ctx.on?.('tools/pre-execute',async(execution,next)=>{
    const path=execution.agent?.session&&courses.resolve(execution.agent.session.id,execution.agent.session).course_path;
    if(path&&relocating.has(path))throw Error('当前课程正在迁移，完成后再操作。');
    if(path&&execution.name?.startsWith('kgxc_course_')&&(execution.name==='kgxc_course_create'||
      execution.arguments?.course_path&&execution.arguments.course_path!==path))throw Error('本对话不能操作其他课程，请打开目标课程的独立对话。');
    await reviews.beforeTool(execution.agent,execution.name,execution.arguments);return next();
  },{prepend:true});
  ctx.inject(['sessionProjections'],scoped=>scoped.sessionProjections.register(productionProjection(z)));
  for (const spec of tools) {
    ctx.tools.register({
      name: spec.name, description: spec.description, parameters: spec.inputSchema, timeoutMs: 60000,
      output: {schema: {type: 'object'}, render: (_args, value) => [{type: 'text', text: JSON.stringify(value)}]},
      execute: async (args, execution) => {
        const session=execution?.agent?.session;
        const owned=session&&courses.resolve(session.id,session).course_path;
        const selecting=['kgxc_course_create','kgxc_course_resume'].includes(spec.name);
        if(owned&&(spec.name==='kgxc_course_create'||args.course_path&&args.course_path!==owned))
          return {ok:false,error:'本对话已绑定另一门课程。请打开目标课程的独立对话，原任务不会切换。'};
        if((owned&&relocating.has(owned))||(args.course_path&&relocating.has(args.course_path)))return {ok:false,error:'当前课程正在迁移，完成后再操作。'};
        if(session?.id&&(attaching.has(session.id)||args.course_path&&attachingCourse.has(args.course_path)))return {ok:false,error:'该对话正在关联课程，请稍候。'};
        const claim=session?.id&&selecting?Symbol():null;
        const targetPath=claim&&args.course_path;
        if(targetPath&&!owned&&courses.sessionsFor(targetPath).some(id=>id!==session.id))
          return {ok:false,error:'这门课已有独立对话，请从课程列表打开。'};
        if(claim)attaching.set(session.id,claim);
        if(targetPath)attachingCourse.add(targetPath);
        try{
        if (spec.name === 'kgxc_course_create' && !args.course_path && execution?.agent?.session?.header?.cwd) args = {...args,workspace_path:execution.agent.session.header.cwd};
        const value = await callTool(spec.name, args, {signal: execution?.signal});
        courses.record(spec.name,value,execution?.agent);
        if(value.ok&&value.course_path&&session&&courses.resolve(session.id,session).course_path===value.course_path&&
          (!bindings.has(value.course_path)||bindings.get(value.course_path)===execution.agent))bindings.set(value.course_path,execution.agent);
        if(value.ok&&value.course_path&&execution?.agent&&['kgxc_course_create','kgxc_course_resume'].includes(spec.name))void reviews.onIdle(execution.agent).catch(error=>ctx.logger?.warn?.('关联课程后的独立审阅未启动：'+error.message));
        return value;
        }finally{if(targetPath)attachingCourse.delete(targetPath);if(claim&&attaching.get(session.id)===claim)attaching.delete(session.id);}
      },
    });
  }
  ctx.inject(['skills'], scoped => {
    for (const folder of ['corporate-training-motion', 'elearning-course-design']) {
      const path = join(root, 'skills', folder, 'SKILL.md');
      const text = readFileSync(path, 'utf8');
      const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/.exec(text);
      if (!match) throw new Error('制课 Skill 元数据无效：' + folder);
      const description = /^description:\s*(.+)$/m.exec(match[1])?.[1];
      scoped.skills.register({name: folder, description, content: match[2], path, source: 'kgxc-course-plugin',
        invocation: {modelInvocable: true, userInvocable: true}, resourceBase: {kind: 'directory', path: join(root, 'skills', folder)}});
    }
  });
  const token = randomBytes(32).toString('hex');
  const json = (res, status, value) => { res.writeHead(status, {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store'}); res.end(JSON.stringify(value)); };
  const validToken=req=>{const value=req.headers['x-kgxc-token'];return typeof value==='string'&&value.length===token.length&&timingSafeEqual(Buffer.from(value),Buffer.from(token));};
  const views=studioProxy({validToken,json,resolveCourse:sessionId=>{const session=ctx.get?.('agents')?.get(sessionId)?.session||ctx.get?.('sessions')?.get(sessionId);return courses.resolve(sessionId,session).course_path;}});
  ctx.inject(['webServer'], scoped => {
    scoped.effect(() => scoped.webServer.register({kind: 'prefix', path: '/api/kgxc-course', handler: async (req, res) => {
      try {
        const host = req.headers.host;
        const address = req.socket?.remoteAddress;
        if (host && !['127.0.0.1', 'localhost', '[::1]'].includes(new URL('http://' + host).hostname) || address && !['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(address)) return json(res, 403, {ok: false, error: '制课接口仅供本机使用'});
        const route = new URL(req.url, 'http://localhost').pathname;
        if(route.startsWith('/api/kgxc-course/content/'))return await views.serve(req,res,new URL(req.url,'http://localhost'));
        if(req.method==='GET'&&route==='/api/kgxc-course/delivery/file')return await serveDelivery(req,res,new URL(req.url,'http://localhost'));
        if (req.method === 'GET' && route === '/api/kgxc-course/meta') {
          return json(res, 200, {ok: true, version, token, media_origin:scoped.webServer.getOrigin?.()||'', tools: tools.map(tool => tool.name)});
        }
        if (req.method === 'GET' && route === '/api/kgxc-course/updates') return json(res,200,await checkUpdate());
        if (req.method === 'GET' && route === '/api/kgxc-course/update-install') return json(res,200,await installer());
        if (req.method === 'GET' && route === '/api/kgxc-course/courses') return json(res, 200, await callTool('kgxc_course_list'));
        if (req.method !== 'POST' || !['/api/kgxc-course/call','/api/kgxc-course/editor','/api/kgxc-course/context','/api/kgxc-course/workspace','/api/kgxc-course/progress','/api/kgxc-course/review','/api/kgxc-course/view','/api/kgxc-course/updates','/api/kgxc-course/update-install'].includes(route)) return json(res, 404, {ok: false, error: '未知操作'});
        const supplied = req.headers['x-kgxc-token'];
        if (typeof supplied !== 'string' || supplied.length !== token.length || !timingSafeEqual(Buffer.from(supplied), Buffer.from(token))) return json(res, 403, {ok: false, error: '请重新打开制课工作台'});
        if (!String(req.headers['content-type'] || '').startsWith('application/json')) return json(res, 415, {ok: false, error: '需要 JSON 请求'});
        let body = '', bytes = 0;
        for await (const chunk of req) { bytes += chunk.length; if (bytes > 4 * 1024 * 1024) return json(res, 413, {ok: false, error: '请求过大'}); body += chunk; }
        const request = JSON.parse(body);
        if(route.endsWith('/update-install')){
          if(!request||Object.keys(request).some(key=>!['action','version'].includes(key))||
              !['download','install'].includes(request.action)||(request.version!==undefined&&!/^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}$/.test(request.version)))return json(res,400,{ok:false,error:'更新请求无效。'});
          const value=await installer(request.action,request.version);return json(res,value.ok?200:value.code==='install_busy'?409:400,value);
        }
        if(route.endsWith('/updates'))return json(res,200,await checkUpdate({force:true}));
        if(route.endsWith('/view'))return json(res,200,await views.open(request));
        if(route.endsWith('/review')){
          const agent=ctx.get?.('agents')?.get(request.session_id),session=agent?.session||ctx.get?.('sessions')?.get(request.session_id);
          const path=courses.resolve(request.session_id,session).course_path;
          if(!path||request.course_path!==path)throw Error('课程已切换，请在当前课程重新打开审阅');
          return json(res,200,await reviews(request.action,{...request,course_path:path,busy:agent?.status==='running'||Boolean(request.busy)}));
        }
        if(route.endsWith('/progress')){
          const agent=ctx.get?.('agents')?.get(request.session_id),session=agent?.session||ctx.get?.('sessions')?.get(request.session_id);
          const path=courses.resolve(request.session_id,session).course_path;
          const state=session&&ctx.get?.('sessionProjections')?.stateOf(session,'kgxcProduction');
          return json(res,200,{ok:true,production:productionSnapshot(state,{course_path:path,running:agent?.status==='running'})});
        }
        if (route.endsWith('/context')) {
          const session = ctx.get?.('sessions')?.get(request.session_id) || ctx.get?.('agents')?.get(request.session_id)?.session;
          return json(res,200,{...courses.resolve(request.session_id,session),workspace_path:session?.header?.cwd});
        }
        if(route.endsWith('/workspace')) {
          const agent=ctx.get?.('agents')?.get(request.session_id);
          const session=agent?.session || ctx.get?.('sessions')?.get(request.session_id);
          const path=courses.resolve(request.session_id,session).course_path;
          if(!path||!session?.header?.cwd)throw Error('当前课程或会话工作区尚未就绪');
          if(request.course_path&&request.course_path!==path)throw Error('当前对话不拥有请求中的课程，未进行任何操作。');
          const operation=request.action;
          if(!operation)throw Error('请明确指定工作区操作。');
          const moving=operation==='relocate';
          if(moving||operation==='deliver'||operation==='retention'){
            const boundAgent=bindings.get(path);
            const anyRunning=[agent,boundAgent,...courses.sessionsFor(path).map(id=>ctx.get?.('agents')?.get(id))].some(owner=>owner?.status==='running');
            if(relocating.has(path)||anyRunning||reviews.courseBusy(path)||confirmations.courseBusy(path))
              throw Error('这门课还在制作、检查或等待确认，不能迁移、交付或清理。');
          }
          if(moving)relocating.add(path);
          try{
          const value=await callWorkspace(operation,{course_path:path,workspace_path:session.header.cwd,choice:request.choice,request_id:request.request_id},{timeout:120000});
          if(value.ok&&moving){
            courses.relocate(value.previous_path,value.course_path);
            if(value.previous_path!==value.course_path)bindings.delete(value.previous_path);
          }
          if(value.ok&&operation==='deliver'&&agent)agent.inject(Object.freeze({id:randomUUID(),role:'user',source:Object.freeze({kind:'kgxc-course-context'}),content:Object.freeze([Object.freeze({type:'text',text:'当前课程已完成桌面交付，逐字稿、小样、配音与过程工程均保留。制作授权不构成删除授权；只有用户在具体清理范围弹窗中明确选择后才能清理。交付位置：'+value.delivery.delivery_root})])}));
          return json(res,200,value);
          }finally{if(moving)relocating.delete(path);}
        }
        if(route.endsWith('/editor')){
          const args=request.arguments||{},action=request.action;
          if(action==='course-session'){
            if(typeof args.course_path!=='string'||!args.course_path.startsWith('/'))throw Error('课程路径无效。');
            const eligible=Array.isArray(args.session_ids)?new Set(args.session_ids.slice(0,500)):null;
            for(const id of eligible||[])if(typeof id==='string'&&/^[a-zA-Z0-9_-]{1,150}$/.test(id))courseOf(id);
            const owners=courses.sessionsFor(args.course_path);
            // Do not create a session if an original owner exists but cannot be opened in this UI.
            return json(res,200,{ok:true,session_id:owners.find(id=>!eligible||eligible.has(id))||owners[0]||null});
          }
          if(action==='attach-course'||action==='select_delivery'||action==='bind'&&args.select){
            const session=sessionOf(args.session_id);
            if(!session)throw Error('目标独立对话尚未连接，请先打开后重试。');
            const owned=courseOf(args.session_id);
            if(owned&&owned!==args.course_path)throw Error('该对话已有自己的课程；请打开目标课程的独立对话，原任务不会切换。');
            if(owned===args.course_path)return json(res,200,{ok:true,session_id:args.session_id});
            if(attaching.has(args.session_id)||attachingCourse.has(args.course_path)||relocating.has(args.course_path)||ctx.get?.('agents')?.get(args.session_id)?.status==='running')
              throw Error('目标对话或课程正在执行其他操作，未关联。');
            const claim=Symbol();attaching.set(args.session_id,claim);attachingCourse.add(args.course_path);
            try{
              const value=await callTool('kgxc_course_resume',{course_path:args.course_path});
              if(!value.ok)throw Error(value.error);
              if(value.course_path!==args.course_path||relocating.has(args.course_path))throw Error('课程目录已变更，请刷新课程列表。');
              const other=courses.sessionsFor(value.course_path).find(id=>id!==args.session_id);
              if(other)return json(res,200,{ok:true,session_id:other,existing:true});
              if(ctx.get?.('agents')?.get(args.session_id)?.status==='running')throw Error('目标对话开始了其他任务，未关联。');
              courses.attach(args.session_id,value.course_path,session);
              return json(res,200,{ok:true,session_id:args.session_id});
            }finally{attachingCourse.delete(args.course_path);if(attaching.get(args.session_id)===claim)attaching.delete(args.session_id);}
          }
          if(action==='bind'&&courseOf(args.session_id)!==args.course_path)return json(res,200,{ok:true,stale:true});
          assertBound(args);
          if(['stage-confirmation-request','stage-confirmation-status','stage-confirmation-cancel','stage-feedback-submit'].includes(action))return json(res,200,await confirmations(action,args));
          return json(res,200,await editor(action,args));
        }
        const readCalls=new Set(['kgxc_course_environment','kgxc_course_resume','kgxc_course_status','kgxc_course_job','kgxc_course_list']);
        if(!readCalls.has(request.name)){
          if(!request.arguments?.course_path)throw Error('请从已关联课程的对话执行此操作。');
          assertBound({...request.arguments,session_id:request.session_id});
        }
        return json(res,200,await callTool(request.name,request.arguments||{}));
      } catch (error) { return json(res, 400, {ok: false, error: error.message}); }
    }}), 'kgxc-course: local course API');
  });
}
