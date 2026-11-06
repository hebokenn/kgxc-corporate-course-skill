import {paragraphAt, previewDocument, replaceSelection} from '/script-editor-model.js';
import {totalFrames, displayFrame} from '/timeline.js';
import {startActivity} from '/activity.js';
const $ = id => document.getElementById(id);
let state, renderer, currentDoc, frame = 0, playing = false, serial = 0, savedSerial = 0;
let saveTimer, saveTask, previewTimer, previewRunning = false, previewWanted = false, renderTimer;
let selection, aiRequest, hostReady = false, undo = [], stopped = false;
let savedText = '', recoveryDraft;
const pending = new Map(), audio = new Audio();
const params = new URLSearchParams(location.search), parentOrigin = params.get('parentOrigin');
function allowedParent(value) { try { const url = new URL(value); return value === 'dsh-app://app' || url.protocol === 'http:' && ['127.0.0.1','localhost'].includes(url.hostname); } catch { return false; } }
const embedded = parent !== window && allowedParent(parentOrigin);
function error(message = '') { $('error').hidden = !message; $('error').textContent = message; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const value = await response.json();
  if (!response.ok || value.ok === false) throw Error(value.error || '操作失败');
  return value;
}
function host(type, data, timeout = 120000) {
  if (!embedded || !hostReady) return Promise.reject(Error('请在 DSH 制课窗口内使用 AI 修改。'));
  const id = crypto.randomUUID();
  return new Promise((resolve,reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(Error('AI 响应超时，请重试。')); }, timeout);
    pending.set(id,{resolve,reject,timer});
    parent.postMessage({type:'kgxc-editor-request',id,action:type,...data}, parentOrigin);
  });
}
window.addEventListener('message', async event => {
  if (!embedded || event.source !== parent || event.origin !== parentOrigin) return;
  const data = event.data;
  if (data?.type === 'kgxc-editor-refresh') { refreshFromAI().catch(e=>error(e.message)); return; }
  if (data?.type === 'kgxc-editor-host') {
    if (hostReady) return;
    hostReady = true;
    if (data.draft && typeof data.draft.text === 'string' && data.draft.text !== $('script').value) {
      if ($('script').value === data.draft.base_text) { const before=$('script').value;$('script').value=data.draft.text;changed(before); }
      else { recoveryDraft=data.draft;$('recovery').hidden=false;$('recovery-text').value=data.draft.text; }
    }
    publishDraft(); return;
  }
  if (data?.type === 'kgxc-editor-leave') {
    try { await save();parent.postMessage({type:'kgxc-editor-leave-result',id:data.id},parentOrigin); }
    catch(e) { parent.postMessage({type:'kgxc-editor-leave-result',id:data.id,error:e.message},parentOrigin); }
    return;
  }
  if (data?.type !== 'kgxc-editor-result' || !pending.has(data.id)) return;
  const item = pending.get(data.id); pending.delete(data.id); clearTimeout(item.timer);
  if (data.error) item.reject(Error(data.error)); else item.resolve(data.result);
});
function announce() { if (embedded) parent.postMessage({type:'kgxc-editor-ready'},parentOrigin); }
function publishDraft() {
  if (embedded && hostReady && state && !recoveryDraft) parent.postMessage({type:'kgxc-editor-draft',course_path:state.course_path,text:$('script').value,base_text:savedText,base_revision:state.revision,dirty:serial!==savedSerial},parentOrigin);
}
function status() {
  $('word-count').textContent = [...$('script').value.replace(/\s/g,'')].length + ' 字';
  $('save-state').textContent = serial !== savedSerial ? '正在保存…' : state?.changed ? '草稿已保存 · 待渲染' : '已保存';
  $('undo').disabled = !undo.length;
  $('render').disabled = !state || !$('script').value.trim() || ['preparing','rendering'].includes(state?.render_request?.status);
  publishDraft();
}
function changed(previous) {
  pause();
  undo.push(previous); if (undo.length > 80) undo.shift(); serial++; status();
  clearTimeout(saveTimer); saveTimer = setTimeout(() => save().catch(e=>error(e.message)),650);
  schedulePreview();
}
async function save() {
  if (saveTask) { await saveTask; if (savedSerial !== serial) return save(); return; }
  if (savedSerial === serial) return;
  const text = $('script').value, checkpoint = serial;
  saveTask = api('/api/editor/save',{text,baseRevision:state.revision}).then(result => { state = result; savedText=text; savedSerial = checkpoint; status(); });
  try { await saveTask; } finally { saveTask = null; }
  if (savedSerial !== serial) return save();
}
async function refreshFromAI() {
  if (!state || serial !== savedSerial || saveTask) return;
  const result = await api('/api/editor');
  if (serial !== savedSerial || saveTask) return;
  const changedDocument = JSON.stringify(state.document) !== JSON.stringify(result.document);
  if ($('script').value !== result.text) undo.push($('script').value);
  state = result; savedText=result.text; $('script').value = result.text; $('title').textContent = result.title;
  status(); showRender(state.render_request);
  if (result.base_changed) error('AI 更新了正式逐字稿，人工草稿已保留，请核对后合并。');
  if (changedDocument) await loadRenderer(); else await updatePreview();
}
function time(value) { return Math.floor(value/60).toString().padStart(2,'0')+':'+Math.floor(value%60).toString().padStart(2,'0'); }
async function paint() {
  if (!renderer || !currentDoc) return;
  try { await renderer.drawFrame(frame); $('preview-error').hidden = true; }
  catch (e) { $('preview-error').hidden = false; $('preview-error').textContent = e.message; }
  $('seek').value = frame; $('time').textContent = time(frame/currentDoc.fps);
}
function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(updatePreview,160); }
async function updatePreview() {
  previewWanted = true; if (previewRunning || !state) return; previewRunning = true;
  try {
    while (previewWanted) {
      previewWanted = false;
      const value = $('script').value, view = previewDocument(state.document,state.base_text,value,$('script').selectionStart);
      $('paragraph-preview').textContent = view.selected?.text || '在左侧输入逐字稿，或等待 AI 生成。';
      $('paragraph-title').textContent = state.title;
      if (!renderer) continue;
      currentDoc = view.document;
      if (view.scene) frame = displayFrame(view.scene.sourceStartFrame,currentDoc.holds,currentDoc.cuts);
      await renderer.load(currentDoc); await paint();
      const dirty = value !== state.base_text;
      $('preview-kind').textContent = dirty ? '文字草稿预览' : '课程实际画面';
      $('preview-note').textContent = dirty ? (view.needsBinding ? '新增或重排的段落尚未绑定画面；右侧保留原画面。点击渲染后由 AI 更新分镜和配音。' : '文字已更新，使用原有画面时轴静音预览。配音和视频在点击渲染后更新。') : '文字改动即时预览；配音和视频在点击渲染后更新。';
      audio.muted = dirty;
    }
  } catch (e) { error(e.message); } finally { previewRunning = false; }
}
function selectCurrent() {
  const area = $('script'), paragraph = paragraphAt(area.value,area.selectionStart);
  if (!paragraph) return;
  area.focus(); area.setSelectionRange(paragraph.start,paragraph.end); selectionChanged();
}
function selectionChanged() {
  pause();
  const area = $('script'), length = area.selectionEnd - area.selectionStart;
  $('selection-state').textContent = length ? `已选择 ${length} 字` : '未选择文字';
  schedulePreview();
}
$('script').addEventListener('beforeinput',()=>{ $('script').dataset.previous = $('script').value; });
$('script').addEventListener('input',()=>changed($('script').dataset.previous ?? state.text));
for (const name of ['select','click','keyup']) $('script').addEventListener(name,selectionChanged);
$('select-paragraph').onclick = selectCurrent;
$('ask-ai').onclick = () => {
  const area = $('script'); if (area.selectionStart === area.selectionEnd) selectCurrent();
  if (area.selectionStart === area.selectionEnd) { error('先写一段逐字稿，再选择需要修改的文字。'); return; }
  selection = {snapshot:area.value,start:area.selectionStart,end:area.selectionEnd,text:area.value.slice(area.selectionStart,area.selectionEnd)};
  $('selected-text').textContent = selection.text; $('selection-label').textContent = `修改选中内容 · ${selection.text.length} 字`;
  $('ai-panel').hidden = false; $('ai-result').hidden = true; $('ai-status').textContent = ''; $('instruction').focus();
};
$('close-ai').onclick = () => { $('ai-panel').hidden = true; };
$('rewrite').onclick = async () => {
  if (!selection || aiRequest) return;
  error(); const id = crypto.randomUUID(); aiRequest = id;
  $('rewrite').disabled = true; $('cancel-ai').hidden = false; $('ai-status').textContent = 'AI 正在修改选中的内容…'; $('ai-result').hidden = true;
  try {
    const result = await host('rewrite',{requestId:id,course_path:state.course_path,text:selection.text,instruction:$('instruction').value.trim() || '改得更口语化、适合课程讲解，保留原有事实和关键步骤。',before:selection.snapshot.slice(Math.max(0,selection.start-1200),selection.start),after:selection.snapshot.slice(selection.end,selection.end+1200)});
    if (aiRequest !== id) return;
    $('suggestion').value = result.text; $('ai-result').hidden = false; $('ai-status').textContent = '建议已生成，请核对后替换。';
  } catch (e) { if (aiRequest === id) $('ai-status').textContent = e.message; }
  finally { if (aiRequest === id) { aiRequest = null; $('rewrite').disabled = false; $('cancel-ai').hidden = true; } }
};
$('cancel-ai').onclick = () => { const id = aiRequest; aiRequest = null; host('cancel',{requestId:id,course_path:state.course_path}).catch(()=>{}); $('rewrite').disabled = false; $('cancel-ai').hidden = true; $('ai-status').textContent = '已取消修改。'; };
$('accept-ai').onclick = () => {
  try { const previous = $('script').value, replacement = $('suggestion').value; if (!replacement.trim()) throw Error('修改建议不能为空。'); $('script').value = replaceSelection(previous,selection,replacement); $('script').focus(); $('script').setSelectionRange(selection.start,selection.start+replacement.length); changed(previous); $('ai-panel').hidden = true; selectionChanged(); error(); }
  catch(e) { error(e.message); }
};
$('undo').onclick = () => { const previous = undo.pop(); if (previous === undefined) return; $('script').value = previous; serial++; status(); schedulePreview(); clearTimeout(saveTimer); saveTimer = setTimeout(()=>save().catch(e=>error(e.message)),500); };
let playStarted = 0, playFrame = 0;
function pause() { playing = false; audio.pause(); $('play').textContent = '播放预览'; }
async function tick(now) {
  if (!playing || document.hidden || stopped) { pause(); return; }
  frame = Math.min(totalFrames(currentDoc)-1,playFrame + Math.round((now-playStarted)*currentDoc.fps/1000));
  await paint(); if (frame >= totalFrames(currentDoc)-1) pause(); else requestAnimationFrame(tick);
}
$('play').onclick = async () => { if (playing) return pause(); playing = true; playFrame = frame; playStarted = performance.now(); $('play').textContent = '暂停'; if (!audio.muted && state.document.media.audio) { audio.currentTime = frame/currentDoc.fps; audio.play().catch(()=>{}); } requestAnimationFrame(tick); };
$('seek').oninput = () => { pause(); frame = Number($('seek').value); paint(); };
document.addEventListener('visibilitychange',()=>{ if (document.hidden) pause(); else if (['preparing','rendering'].includes(state?.render_request?.status)) pollRender(); });
function showRender(request) {
  if (!request) return;
  $('render-status').hidden = false;
  $('render-label').textContent = ({preparing:'正在准备渲染',rendering:'正在渲染视频',complete:'视频已渲染',failed:'本次渲染未完成'})[request.status] || '渲染任务';
  $('render-detail').textContent = request.error || (request.status === 'preparing' ? 'AI 正在按点击时的稿件更新配音与对应画面。你可以继续编辑。' : request.status === 'complete' ? (request.sha256 === state.render_request?.sha256 && serial === savedSerial ? '渲染结果对应本次提交的稿件。' : '渲染结果对应点击时的稿件。') : '完成后可查看视频与字幕。');
  $('progress').hidden = request.status !== 'rendering'; $('progress').value = request.job?.progress || 0;
  $('downloads').replaceChildren();
  if (request.status === 'complete') for (const [key,label] of [['video','查看视频'],['srt','字幕']]) if (request.job?.[key]) { const a = document.createElement('a'); a.textContent = label; a.href = request.job[key]; a.target = '_blank'; $('downloads').append(a); }
  status();
}
async function pollRender() {
  clearTimeout(renderTimer); if (document.hidden || stopped) return;
  try { const result = await api('/api/editor');
    const finished = state.render_request?.status !== 'complete' && result.render_request?.status === 'complete';
    state.render_request = result.render_request; showRender(state.render_request);
    if (finished && serial === savedSerial && result.text === $('script').value) { state = result; await loadRenderer(); }
    if (['preparing','rendering'].includes(state.render_request?.status)) renderTimer = setTimeout(pollRender,2000);
  }
  catch(e) { error(e.message); }
}
$('render').onclick = async () => {
  $('render').disabled = true; error();
  try { await save(); const request = await api('/api/editor/render',{baseRevision:state.revision}); state.render_request = request; showRender(request);
    if (embedded) await host('render',{course_path:state.course_path,requestId:request.id},30000);
    else if (!request.job) throw Error('已保存渲染请求。请在 DSH 对话中继续此课程，让 AI 按当前稿件更新配音和画面。');
    pollRender();
  } catch(e) { error(e.message); if (state?.render_request?.status === 'preparing') { try { state.render_request = await api('/api/editor/render-error',{requestId:state.render_request.id,error:e.message}); showRender(state.render_request); } catch {} } }
  finally { status(); }
};
window.addEventListener('beforeunload',event=>{ if (serial !== savedSerial) { event.preventDefault(); event.returnValue=''; } });
window.addEventListener('pagehide',()=>{ stopped = true; pause(); clearTimeout(renderTimer); for (const item of pending.values()) { clearTimeout(item.timer); item.reject(Error('编辑窗口已关闭')); } pending.clear(); });
document.addEventListener('keydown',e=>{ if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase()==='s') { e.preventDefault(); save().catch(x=>error(x.message)); } });
$('recover').onclick=()=>{if(!recoveryDraft)return;const previous=$('script').value;$('script').value=recoveryDraft.text;recoveryDraft=null;$('recovery').hidden=true;changed(previous);};
startActivity(()=>serial !== savedSerial || Boolean(aiRequest) || ['preparing','rendering'].includes(state?.render_request?.status),()=>playing);
async function loadRenderer() {
  if (!state.has_scenes) return;
  pause(); renderer = null;
  const view = $('preview'); view.src='/renderer.html?revision='+state.document.revision+'&reload='+Date.now(); view.hidden=false; $('waiting').hidden=true;
  await new Promise((resolve,reject)=>{ const timeout=setTimeout(()=>reject(Error('画面预览加载超时')),25000); const check=()=>{ if (view.contentWindow.ready) {clearTimeout(timeout);resolve();} else if (view.contentWindow.renderError) {clearTimeout(timeout);reject(Error(view.contentWindow.renderError));} else if (!stopped) setTimeout(check,80); }; check(); });
  renderer = view.contentWindow.courseRenderer; currentDoc = state.document;
  frame = displayFrame(state.document.scenes[0].sourceStartFrame,currentDoc.holds,currentDoc.cuts);
  $('seek').max=totalFrames(currentDoc)-1; $('play').disabled=false;
  if (state.document.media.audio) audio.src='/api/audio?revision='+state.document.revision;
  await updatePreview();
}
async function boot() {
  try {
    state = await api('/api/editor'); savedText=state.text; $('title').textContent = state.title; $('script').value = state.text;
    if (state.base_changed) error('AI 已更新正式逐字稿。当前编辑草稿已保留，请先核对后合并。');
    status(); updatePreview(); announce(); showRender(state.render_request);
    await loadRenderer();
    if (['preparing','rendering'].includes(state.render_request?.status)) pollRender();
  } catch(e) { error(e.message); }
}
boot();
