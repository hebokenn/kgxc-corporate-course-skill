import {randomBytes, timingSafeEqual,randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {root, tools, callTool, callWorkspace} from './bridge.mjs';
import {editorHost} from './editor-host.mjs';
import {SessionCourses} from './session-courses.mjs';
import {serveDelivery} from './delivery-files.mjs';
import {z} from 'zod';
import {productionProjection,productionSnapshot} from './production-monitor.mjs';
import {reviewHost} from './review-host.mjs';
import {studioProxy} from './studio-proxy.mjs';

const version = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version;

export const name = 'kgxc-course';
export const inject = ['tools'];
export function apply(ctx) {
  const bindings = new Map();
  const courses = new SessionCourses();
  const reviews=reviewHost(ctx,{bindings});
  const editor = editorHost(ctx, bindings,callTool,{supervision:reviews});
  ctx.on?.('session/event',(session,event)=>{
    const agent=ctx.get?.('agents')?.get(session.id);
    if(agent)void reviews.observe(agent,event).catch(error=>ctx.logger?.warn?.('课程监督已停止执行：'+error.message));
  });
  ctx.on?.('agent/status',({agent,status})=>{
    if(status==='idle')void reviews.onIdle(agent).catch(error=>ctx.logger?.warn?.('课程自动独立审阅未启动：'+error.message));
  });
  ctx.tools.guard?.(execution=>reviews.blockReason(execution.agent));
  ctx.on?.('tools/pre-execute',async(execution,next)=>{
    await reviews.beforeTool(execution.agent,execution.name,execution.arguments);return next();
  },{prepend:true});
  ctx.inject(['sessionProjections'],scoped=>scoped.sessionProjections.register(productionProjection(z)));
  for (const spec of tools) {
    ctx.tools.register({
      name: spec.name, description: spec.description, parameters: spec.inputSchema, timeoutMs: 60000,
      output: {schema: {type: 'object'}, render: (_args, value) => [{type: 'text', text: JSON.stringify(value)}]},
      execute: async (args, execution) => {
        if (spec.name === 'kgxc_course_create' && !args.course_path && execution?.agent?.session?.header?.cwd) args = {...args,workspace_path:execution.agent.session.header.cwd};
        const value = await callTool(spec.name, args, {signal: execution?.signal});
        if (value.ok && value.course_path && execution?.agent) bindings.set(value.course_path, execution.agent);
        courses.record(spec.name,value,execution?.agent);
        if(value.ok&&value.course_path&&execution?.agent&&['kgxc_course_create','kgxc_course_resume'].includes(spec.name))void reviews.onIdle(execution.agent).catch(error=>ctx.logger?.warn?.('关联课程后的独立审阅未启动：'+error.message));
        return value;
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
        if (req.method === 'GET' && route === '/api/kgxc-course/courses') return json(res, 200, await callTool('kgxc_course_list'));
        if (req.method !== 'POST' || !['/api/kgxc-course/call','/api/kgxc-course/editor','/api/kgxc-course/context','/api/kgxc-course/workspace','/api/kgxc-course/progress','/api/kgxc-course/review','/api/kgxc-course/view'].includes(route)) return json(res, 404, {ok: false, error: '未知操作'});
        const supplied = req.headers['x-kgxc-token'];
        if (typeof supplied !== 'string' || supplied.length !== token.length || !timingSafeEqual(Buffer.from(supplied), Buffer.from(token))) return json(res, 403, {ok: false, error: '请重新打开制课工作台'});
        if (!String(req.headers['content-type'] || '').startsWith('application/json')) return json(res, 415, {ok: false, error: '需要 JSON 请求'});
        let body = '', bytes = 0;
        for await (const chunk of req) { bytes += chunk.length; if (bytes > 4 * 1024 * 1024) return json(res, 413, {ok: false, error: '请求过大'}); body += chunk; }
        const request = JSON.parse(body);
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
          const operation=request.action||'relocate';
          const value=await callWorkspace(operation,{course_path:path,workspace_path:session.header.cwd,choice:request.choice,request_id:request.request_id},{timeout:120000});
          if(value.ok&&operation==='relocate'){courses.relocate(value.previous_path,value.course_path);if(agent)bindings.set(value.course_path,agent);await editor('bind',{course_path:value.course_path,session_id:request.session_id});}
          if(value.ok&&operation==='deliver'&&agent)agent.inject(Object.freeze({id:randomUUID(),role:'user',source:Object.freeze({kind:'kgxc-course-context'}),content:Object.freeze([Object.freeze({type:'text',text:'当前课程已完成桌面交付，逐字稿、小样、配音与过程工程均保留。制作授权不构成删除授权；只有用户在具体清理范围弹窗中明确选择后才能清理。交付位置：'+value.delivery.delivery_root})])}));
          return json(res,200,value);
        }
        if (route.endsWith('/editor') && request.action === 'bind' && !request.arguments?.select) {
          const args = request.arguments || {};
          const session = ctx.get?.('sessions')?.get(args.session_id) || ctx.get?.('agents')?.get(args.session_id)?.session;
          if (courses.resolve(args.session_id,session).course_path !== args.course_path) return json(res,200,{ok:true,stale:true});
        }
        if(route.endsWith('/editor')&&request.action==='select_delivery'){
          const args=request.arguments||{},value=await callTool('kgxc_course_resume',{course_path:args.course_path});
          if(!value.delivery_only)throw Error('当前课程仍有工程，请从普通工作台打开');
          courses.set(args.session_id,value.course_path);return json(res,200,{ok:true});
        }
        const result = route.endsWith('/editor') ? await editor(request.action, request.arguments || {}) : await callTool(request.name, request.arguments || {});
        if (route.endsWith('/editor') && request.action === 'bind' && request.arguments.select && result.ok) courses.set(request.arguments.session_id,request.arguments.course_path);
        return json(res, 200, result);
      } catch (error) { return json(res, 400, {ok: false, error: error.message}); }
    }}), 'kgxc-course: local course API');
  });
}
