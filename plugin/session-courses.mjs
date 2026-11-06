import {mkdirSync,readFileSync,writeFileSync,renameSync} from 'node:fs';
import {homedir} from 'node:os';
import {join,isAbsolute} from 'node:path';
import {randomUUID} from 'node:crypto';

const selectors = new Set(['kgxc_course_create','kgxc_course_resume']);
const operations = new Set([...selectors,'kgxc_course_status','kgxc_course_update','kgxc_course_editor','kgxc_course_export']);
const validPath = value => typeof value === 'string' && isAbsolute(value);

// Migrate only structured successful tool results from this selected session.
// Quoted paths and the old UI's injected context never establish ownership.
export function courseFromLog(log = []) {
  const calls = new Map(); let selected, fallback;
  for (const event of log) {
    if (event.type === 'assistant/message') {
      for (const block of event.data?.message?.content || []) {
        if (block.type === 'tool-call') calls.set(block.id,block.name || block.toolName);
      }
    }
    if (event.type !== 'tool/result' || event.data?.message?.isError) continue;
    const name = calls.get(event.data?.message?.source?.callId);
    if (!operations.has(name)) continue;
    for (const block of event.data.message.content || []) {
      if (block.type !== 'text') continue;
      try {
        const value = JSON.parse(block.text);
        if (value.ok && validPath(value.course_path)) {
          if (selectors.has(name)) selected = value.course_path;
          else fallback = value.course_path;
        }
      } catch {}
    }
  }
  return selected || fallback || null;
}

export class SessionCourses {
  constructor(directory = process.env.COURSE_CONFIG_DIR || join(process.env.XDG_CONFIG_HOME || join(homedir(),'.config'),'corporate-training-motion')) {
    this.file = join(directory,'dsh-session-courses.json');
    try { this.entries = JSON.parse(readFileSync(this.file,'utf8')).sessions || {}; }
    catch (error) { if (error.code !== 'ENOENT') throw error; this.entries = {}; }
  }
  set(sessionId,coursePath) {
    if (typeof sessionId !== 'string' || !/^[a-zA-Z0-9_-]{1,150}$/.test(sessionId)) throw Error('会话标识无效');
    if (coursePath !== null && !validPath(coursePath)) throw Error('课程路径无效');
    this.entries[sessionId] = {course_path:coursePath,updated_at:Date.now()};
    mkdirSync(join(this.file,'..'),{recursive:true});
    const pending = this.file + '.' + randomUUID() + '.tmp';
    writeFileSync(pending,JSON.stringify({version:1,sessions:this.entries},null,2)+'\n',{mode:0o600});
    renameSync(pending,this.file);
    return coursePath;
  }
  resolve(sessionId,session) {
    if (!sessionId) return {ok:true,ready:true,course_path:null};
    if (Object.hasOwn(this.entries,sessionId)) return {ok:true,ready:true,course_path:this.entries[sessionId].course_path};
    if (!session) return {ok:true,ready:false,course_path:null};
    const path = courseFromLog(session.log);
    if (path) this.set(sessionId,path);
    return {ok:true,ready:true,course_path:path};
  }
  record(name,value,agent) {
    if (!value.ok || !validPath(value.course_path) || !agent?.session?.id) return;
    const id = agent.session.id;
    if (selectors.has(name) || operations.has(name) && !Object.hasOwn(this.entries,id)) this.set(id,value.course_path);
  }
  relocate(previous,current) {
    for(const [id,value] of Object.entries(this.entries))if(value.course_path===previous)this.set(id,current);
  }
}
