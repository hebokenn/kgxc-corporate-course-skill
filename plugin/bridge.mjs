import {spawn} from 'node:child_process';
import {readFileSync, existsSync} from 'node:fs';
import {homedir} from 'node:os';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

export const root = dirname(dirname(fileURLToPath(import.meta.url)));
export const tools = JSON.parse(readFileSync(join(root, 'plugin/tools.json'), 'utf8'));
export function pythonExecutable() {
  if (process.env.KGXC_COURSE_PYTHON) return process.env.KGXC_COURSE_PYTHON;
  const config = process.env.COURSE_CONFIG_DIR || join(process.env.XDG_CONFIG_HOME || join(homedir(), '.config'), 'corporate-training-motion');
  try { const value = JSON.parse(readFileSync(join(config, 'tools.json'), 'utf8')).python; if (value && existsSync(value)) return value; } catch {}
  return 'python3';
}
export function callTool(name, args = {}, {signal, timeout = 55000} = {}) {
  if (!tools.some(tool => tool.name === name)) return Promise.reject(new Error('未知制课工具'));
  return invoke(name,args,{signal,timeout});
}
export function callWorkspace(name,args,options={}) {
  if (!['relocate','deliver','workbench_live','cleanup_preview','retention','open_delivery'].includes(name)) return Promise.reject(new Error('未知工作区操作'));
  return invoke(name,args,{...options,workspace:true});
}
function invoke(name,args,{signal,timeout=55000,workspace=false}={}) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable(), [join(root, 'plugin/service.py'), workspace?'--workspace-once':'--once'], {
      cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, stdio: ['pipe', 'pipe', 'pipe'], signal,
    });
    let output = '', error = '', finished = false;
    const timer = setTimeout(() => { child.kill('SIGTERM'); done(reject, new Error('制课请求超时；请查询实际课程状态后继续')); }, timeout);
    const done = (fn, value) => { if (finished) return; finished = true; clearTimeout(timer); fn(value); };
    child.stdout.on('data', chunk => { output += chunk; if (output.length > 12 * 1024 * 1024) { child.kill('SIGTERM'); done(reject, new Error('制课响应过大，请使用摘要查询')); } });
    child.stderr.on('data', chunk => { error = (error + chunk).slice(-4000); });
    child.on('error', err => done(reject, err));
    child.on('close', code => {
      if (finished) return;
      try { const value = JSON.parse(output); done(resolve, value); } catch { done(reject, new Error(code === 0 ? '制课服务返回了无效数据' : '制课服务启动失败：' + error.slice(-1500))); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({name, arguments: args}));
  });
}
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1] && process.argv.includes('--stdio')) {
  const child = spawn(pythonExecutable(), [join(root, 'plugin/service.py'), '--stdio'], {
    cwd: root, env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, stdio: 'inherit',
  });
  for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => child.kill(sig));
  child.on('error', error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
  child.on('exit', code => { process.exitCode = code ?? 1; });
}
