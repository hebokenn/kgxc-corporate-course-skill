#!/usr/bin/env node
/**
 * DirectorStage v9.0.0 Incremental & Parallel Scene Render Engine.
 *
 * Key capabilities:
 * 1. Integer-frame scene partitioning (`DirectorStage.partitionSceneFrames`) so every
 *    scene maps to an exact, non-overlapping `[startFrame, endFrame)` span.
 * 2. Automatic per-scene cache invalidation via SHA-256 over shared libraries/helpers,
 *    the specific scene's renderer source, its beats/subtitles, and timeline metadata.
 * 3. Parallel multi-tab headless Chrome CDP rendering (`--workers N`, default 3).
 * 4. Lossless H.264 segment concatenation (`ffmpeg -f concat -c:v copy`) + audio/SFX mux
 *    + exact merged `render_audit.json` (`DirectorStage.mergeFrameAudits`) with 100% Gate A parity.
 *
 * CLI usage:
 *   node render_director_incremental.mjs \
 *     --html ep_director.html \
 *     --audio-dir ./audio/ep06 \
 *     --out-dir ./delivery/ep06 \
 *     --tmp-dir ./work/ep06_tmp \
 *     --meta-json ./work/ep06_meta.json \
 *     [--intro intro.mp4 --outro outro.mp4] \
 *     [--logo kgxc-logo.png] [--workers 3] [--port 9388] [--force] [--skip-cover]
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { spawn, execFileSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SKILL_DIR = path.resolve(__dirname, '..');

const DEFAULT_CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);

function findChromePath(explicitPath) {
  if (explicitPath && fs.existsSync(explicitPath)) return explicitPath;
  for (const p of DEFAULT_CHROME_CANDIDATES) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error('Could not find Chrome/Chromium binary. Pass --chrome or set CHROME_PATH.');
}

function sha256(input) {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function safeSlug(s) {
  return String(s || 'scene').replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 48);
}

/**
 * Extract named scene renderer functions (e.g. `function renderSc07(...) { ... }`)
 * and explicit `// @scene:start <name>` ... `// @scene:end <name>` blocks from HTML/JS
 * so editing 1 scene only invalidates that scene's cache hash while any edit to shared
 * helpers, libraries, or config invalidates `sharedBase` for all scenes.
 */
export function extractSceneSourceBlocks(htmlText) {
  const sceneBlocks = {};
  const ranges = [];

  // 1. Explicit marker blocks: // @scene:start <name> ... // @scene:end <name>
  const markerRe = /\/\/\s*@scene:start\s+([A-Za-z0-9_$-]+)[\s\S]*?\/\/\s*@scene:end\s+\1/g;
  let m;
  while ((m = markerRe.exec(htmlText)) !== null) {
    const name = m[1];
    ranges.push({ start: m.index, end: m.index + m[0].length, name });
    sceneBlocks[name] = m[0];
  }

  // 2. Named top-level scene functions: `function renderScXX(...) { ... }` or `function scene_XX(...) { ... }`
  const fnHeadRe = /\bfunction\s+((?:renderSc|render_sc|scene_)[A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g;
  while ((m = fnHeadRe.exec(htmlText)) !== null) {
    const start = m.index;
    if (ranges.some(r => start >= r.start && start < r.end)) continue;
    const name = m[1];
    const openBraceIdx = m.index + m[0].length - 1;
    let depth = 0;
    let i = openBraceIdx;
    let inSingle = false;
    let inDouble = false;
    let inTemplate = false;
    let inLineComment = false;
    let inBlockComment = false;
    let escaped = false;
    let end = -1;

    for (; i < htmlText.length; i++) {
      const ch = htmlText[i];
      const next = htmlText[i + 1];
      if (inLineComment) {
        if (ch === '\n') inLineComment = false;
        continue;
      }
      if (inBlockComment) {
        if (ch === '*' && next === '/') { inBlockComment = false; i++; }
        continue;
      }
      if (inSingle) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === "'") inSingle = false;
        continue;
      }
      if (inDouble) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === '"') inDouble = false;
        continue;
      }
      if (inTemplate) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === '`') inTemplate = false;
        continue;
      }
      if (ch === '/' && next === '/') { inLineComment = true; i++; continue; }
      if (ch === '/' && next === '*') { inBlockComment = true; i++; continue; }
      if (ch === "'") { inSingle = true; continue; }
      if (ch === '"') { inDouble = true; continue; }
      if (ch === '`') { inTemplate = true; continue; }
      if (ch === '{') depth++;
      else if (ch === '}') {
        depth--;
        if (depth === 0) { end = i + 1; break; }
      }
    }
    if (end > start) {
      ranges.push({ start, end, name });
      sceneBlocks[name] = htmlText.slice(start, end);
    }
  }

  ranges.sort((a, b) => a.start - b.start);
  let sharedBase = '';
  let cursor = 0;
  for (const r of ranges) {
    if (r.start < cursor) continue;
    sharedBase += htmlText.slice(cursor, r.start);
    sharedBase += `/* SCENE_BLOCK:${r.name} */`;
    cursor = r.end;
  }
  sharedBase += htmlText.slice(cursor);

  // 3. Static mapping fallback for IIFE-scoped `SCENE_RENDERERS = { scene_id: renderScXX, ... }`
  const staticSceneFnMap = {};
  const regRe = /\bSCENE_RENDERERS\s*=\s*\{([\s\S]*?)\}/g;
  while ((m = regRe.exec(sharedBase)) !== null) {
    const body = m[1];
    const entryRe = /['"]?([A-Za-z0-9_$-]+)['"]?\s*:\s*([A-Za-z0-9_$]+)\b/g;
    let em;
    while ((em = entryRe.exec(body)) !== null) {
      staticSceneFnMap[em[1]] = em[2];
    }
  }

  return { sharedBase, sceneBlocks, staticSceneFnMap };
}

function loadDirectorStageInNode(directorJsCode) {
  const sandbox = { console, Math, Object, Array, Number, String, Boolean, Error, Map, Set, RegExp, Infinity, JSON };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.runInNewContext(directorJsCode, sandbox, { filename: 'director_stage.js' });
  return sandbox.DirectorStage;
}

function probeDuration(file) {
  return parseFloat(execFileSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', file,
  ], { encoding: 'utf8' }).trim());
}

function parseSrt(srtPath) {
  if (!srtPath || !fs.existsSync(srtPath)) return [];
  const txt = fs.readFileSync(srtPath, 'utf8').replace(/^\uFEFF/, '').trim();
  if (!txt) return [];
  const toSec = ts => {
    const [h, m, s, ms] = ts.split(/[:,]/).map(Number);
    return h * 3600 + m * 60 + s + ms / 1000;
  };
  return txt.split(/\n\s*\n/).map(block => {
    const lines = block.split(/\r?\n/);
    if (lines.length < 2 || !lines[1].includes(' --> ')) return null;
    const [a, b] = lines[1].split(' --> ');
    return { start: toSec(a), end: toSec(b), text: lines.slice(2).join(' ') };
  }).filter(Boolean);
}

function fmtSrt(sec) {
  const ms = Math.max(0, Math.round(sec * 1000));
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms % 3600000 / 60000)).padStart(2, '0')}:${String(Math.floor(ms % 60000 / 1000)).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
}

function mixBodyAudio(manifest, outWav, skillDir) {
  const dingWav = path.join(skillDir, 'assets/sfx/teaching-native-v1/ding.wav');
  const dudongWav = path.join(skillDir, 'assets/sfx/teaching-native-v1/dudong.wav');
  const args = ['-v', 'error', '-y', '-i', manifest.mix_wav];
  const filters = ['[0:a]aresample=48000,aformat=channel_layouts=stereo[base]'];
  const mixInputs = ['[base]'];
  let idx = 1;
  for (const ln of manifest.lines || []) {
    const sfx = ln.sfx || 'none';
    if ((sfx === 'ding' && fs.existsSync(dingWav)) || (sfx === 'dudong' && fs.existsSync(dudongWav))) {
      args.push('-i', sfx === 'ding' ? dingWav : dudongWav);
      const ms = Math.max(0, Math.round((ln.speech_start ?? ln.start ?? 0) * 1000));
      filters.push(`[${idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume=${sfx === 'ding' ? 0.24 : 0.28},adelay=${ms}|${ms}[s${idx}]`);
      mixInputs.push(`[s${idx}]`);
      idx++;
    }
  }
  filters.push(`${mixInputs.join('')}amix=inputs=${mixInputs.length}:duration=first:normalize=0,alimiter=limit=0.95[out]`);
  args.push(
    '-filter_complex', filters.join(';'),
    '-map', '[out]',
    '-t', Number(manifest.total_duration).toFixed(3),
    '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', outWav,
  );
  execFileSync('ffmpeg', args, { stdio: 'inherit' });
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.ready = new Promise((res, rej) => {
      this.ws.onopen = res;
      this.ws.onerror = rej;
    });
    this.ws.onmessage = ev => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { res, rej } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) rej(new Error(msg.error.message));
        else res(msg.result);
      }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  close() {
    try { this.ws.close(); } catch {}
  }
}

async function launchChrome(chromePath, port, userDir) {
  fs.mkdirSync(userDir, { recursive: true });
  const proc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDir}`,
    '--window-size=1920,1080',
    '--disable-gpu-sandbox',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    'about:blank',
  ], { stdio: 'ignore' });
  for (let i = 0; i < 60; i++) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return { proc, firstPage: page };
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  proc.kill('SIGKILL');
  throw new Error(`Failed to start Chrome CDP on port ${port}`);
}

async function initWorkerTab(wsUrl, inlinedHtmlPath, renderData) {
  const cdp = new CDPClient(wsUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false,
  });
  await cdp.send('Page.navigate', { url: 'file://' + encodeURI(inlinedHtmlPath) });
  // Wait until document is fully loaded and webfonts/images are ready
  for (let i = 0; i < 60; i++) {
    const ev = await cdp.send('Runtime.evaluate', {
      expression: 'document.readyState === "complete" && typeof window.renderFrame === "function"',
      returnByValue: true,
    });
    if (ev?.result?.value === true) break;
    await new Promise(r => setTimeout(r, 100));
  }
  await cdp.send('Runtime.evaluate', {
    expression: 'document.fonts ? document.fonts.ready.then(() => true) : true',
    awaitPromise: true,
    returnByValue: true,
  });
  await new Promise(r => setTimeout(r, 150));
  const injectEv = await cdp.send('Runtime.evaluate', {
    expression: `window.__DATA__ = ${JSON.stringify(renderData)}; true;`,
    returnByValue: true,
  });
  if (injectEv.exceptionDetails) {
    throw new Error(`Failed to inject __DATA__: ${injectEv.exceptionDetails.text}`);
  }
  return cdp;
}

async function renderSceneSegment(cdp, seg, outMp4, outAuditJson, fps, jpegQuality, logPrefix) {
  const t0 = Date.now();
  const tmpMp4 = `${outMp4}.tmp.${process.pid}.${seg.index}.mp4`;
  const tmpAudit = `${outAuditJson}.tmp.${process.pid}.${seg.index}.json`;

  const initEv = await cdp.send('Runtime.evaluate', {
    expression: 'if (typeof window.initAudit === "function") window.initAudit(); true;',
    returnByValue: true,
  });
  if (initEv.exceptionDetails) {
    throw new Error(`${seg.scene_id} initAudit failed: ${initEv.exceptionDetails.exception?.description || initEv.exceptionDetails.text}`);
  }

  const ff = spawn('ffmpeg', [
    '-v', 'error', '-y',
    '-f', 'image2pipe', '-vcodec', 'mjpeg', '-r', String(fps), '-i', '-',
    '-vf', 'scale=1920:1080:in_range=full:out_range=tv,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
    '-pix_fmt', 'yuv420p', '-color_range', 'tv',
    '-r', String(fps), '-video_track_timescale', String(fps * 1000),
    '-an', tmpMp4,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((res, rej) => {
    ff.on('error', rej);
    ff.on('close', code => (code === 0 ? res() : rej(new Error(`ffmpeg segment ${seg.scene_id} exit ${code}`))));
  });

  try {
    for (let f = seg.startFrame; f < seg.endFrame; f++) {
      const t = f / fps;
      const ev = await cdp.send('Runtime.evaluate', {
        expression: `window.renderFrame(${f}, ${t.toFixed(6)}, window.__DATA__); true;`,
      });
      if (ev.exceptionDetails) {
        throw new Error(`${seg.scene_id} f=${f}: ${ev.exceptionDetails.exception?.description || ev.exceptionDetails.text}`);
      }
      const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: jpegQuality });
      if (!ff.stdin.write(Buffer.from(shot.data, 'base64'))) {
        await new Promise(r => ff.stdin.once('drain', r));
      }
    }
    ff.stdin.end();
    await ffDone;

    const auditEv = await cdp.send('Runtime.evaluate', {
      expression: 'typeof window.finalizeAudit === "function" ? JSON.stringify(window.finalizeAudit()) : "null"',
      returnByValue: true,
    });
    if (auditEv.exceptionDetails) {
      throw new Error(`${seg.scene_id} finalizeAudit failed: ${auditEv.exceptionDetails.exception?.description || auditEv.exceptionDetails.text}`);
    }
    const auditObj = JSON.parse(auditEv.result.value);
    fs.writeFileSync(tmpAudit, JSON.stringify(auditObj, null, 2), 'utf8');
    fs.renameSync(tmpMp4, outMp4);
    fs.renameSync(tmpAudit, outAuditJson);

    const elapsedSec = Number(((Date.now() - t0) / 1000).toFixed(2));
    console.log(`[${logPrefix}] Rendered scene #${seg.index} ${seg.scene_id} (${seg.frameCount}f, [${seg.startFrame}..${seg.endFrame})) in ${elapsedSec}s`);
    return { audit: auditObj, elapsedSec };
  } catch (err) {
    try { ff.stdin.end(); } catch {}
    try { if (fs.existsSync(tmpMp4)) fs.unlinkSync(tmpMp4); } catch {}
    try { if (fs.existsSync(tmpAudit)) fs.unlinkSync(tmpAudit); } catch {}
    throw err;
  }
}

export async function renderDirectorIncremental(options) {
  const {
    htmlPath,
    audioDir,
    outDir,
    tmpDir,
    epMeta,
    skillDir = SKILL_DIR,
    logoPath = path.join(SKILL_DIR, 'assets/brand/kgxc/kgxc-logo.png'),
    kgOrigPath = path.join(SKILL_DIR, 'assets/profiles/kgxc/kg-original.png'),
    introMp4 = null,
    outroMp4 = null,
    fps = 24,
    jpegQuality = 94,
    workers = 3,
    port = 9388,
    force = false,
    skipCover = false,
    chromePath = null,
  } = options;

  const tStart = Date.now();
  const chrome = findChromePath(chromePath);
  fs.mkdirSync(outDir, { recursive: true });
  fs.mkdirSync(tmpDir, { recursive: true });
  const cacheDir = path.join(tmpDir, 'scene_cache');
  fs.mkdirSync(cacheDir, { recursive: true });

  const epId = epMeta?.ep_id || 'ep';
  const stem = epMeta?.stem || epId;

  // 1. Inline motion libraries & brand assets if placeholders are present
  const actorsJs = fs.readFileSync(path.join(skillDir, 'workbench/motion/actors_v3_cute.js'), 'utf8');
  const metaphorsJs = fs.readFileSync(path.join(skillDir, 'workbench/motion/visual_metaphors.js'), 'utf8');
  const directorJs = fs.readFileSync(path.join(skillDir, 'workbench/motion/director_stage.js'), 'utf8');
  const DS = loadDirectorStageInNode(directorJs);

  let inlinedHtml = fs.readFileSync(htmlPath, 'utf8');
  inlinedHtml = inlinedHtml
    .replace('__ACTORS_CUTE_JS__', () => actorsJs)
    .replace('__VISUAL_METAPHORS_JS__', () => metaphorsJs)
    .replace('__DIRECTOR_STAGE_JS__', () => directorJs);
  if (inlinedHtml.includes('__LOGO_DATA_URI__') && logoPath && fs.existsSync(logoPath)) {
    const b64 = fs.readFileSync(logoPath).toString('base64');
    inlinedHtml = inlinedHtml.replace('__LOGO_DATA_URI__', `data:image/png;base64,${b64}`);
  }
  if (inlinedHtml.includes('__KG_ORIG_DATA_URI__') && kgOrigPath && fs.existsSync(kgOrigPath)) {
    const b64 = fs.readFileSync(kgOrigPath).toString('base64');
    inlinedHtml = inlinedHtml.replace('__KG_ORIG_DATA_URI__', `data:image/png;base64,${b64}`);
  }
  const inlinedHtmlPath = path.join(tmpDir, `${epId}_director_inlined.html`);
  fs.writeFileSync(inlinedHtmlPath, inlinedHtml, 'utf8');

  // 2. Load audio manifest & subtitles, partition into exact integer-frame scenes
  const manifest = JSON.parse(fs.readFileSync(path.join(audioDir, 'audio_manifest.json'), 'utf8'));
  const subs = parseSrt(path.join(audioDir, 'body.srt'));
  const renderData = {
    epMeta,
    totalDuration: manifest.total_duration,
    lines: manifest.lines,
    subs,
  };
  const partition = DS.partitionSceneFrames(manifest.lines, manifest.total_duration, fps);
  const { segments, totalFrames } = partition;

  // 3. Mix narration + native SFX audio
  const mixedWav = path.join(tmpDir, `${epId}_mixed.wav`);
  mixBodyAudio(manifest, mixedWav, skillDir);

  // 4. Launch headless Chrome & probe SCENE_RENDERERS mapping on tab 0
  const userDir = path.join(tmpDir, `chrome_pool_${port}`);
  const { proc, firstPage } = await launchChrome(chrome, port, userDir);
  const workerTabs = [];

  try {
    const tab0 = await initWorkerTab(firstPage.webSocketDebuggerUrl, inlinedHtmlPath, renderData);
    workerTabs.push(tab0);

    // Probe scene_id -> renderer function name mapping (supports both `const SCENE_RENDERERS` and `window.SCENE_RENDERERS`)
    const probeEv = await tab0.send('Runtime.evaluate', {
      expression: `(() => {
        try {
          const reg = (typeof SCENE_RENDERERS !== 'undefined' && SCENE_RENDERERS) || window.SCENE_RENDERERS || null;
          if (!reg || typeof reg !== 'object') return {};
          const out = {};
          for (const [k, fn] of Object.entries(reg)) {
            out[k] = typeof fn === 'function' ? (fn.name || '') : '';
          }
          return out;
        } catch { return {}; }
      })()`,
      returnByValue: true,
    });
    const sceneFnMap = (probeEv?.result?.value && typeof probeEv.result.value === 'object')
      ? probeEv.result.value
      : {};

    // 5. Compute deterministic per-scene cache hashes
    const { sharedBase, sceneBlocks, staticSceneFnMap } = extractSceneSourceBlocks(inlinedHtml);
    const mergedSceneFnMap = { ...staticSceneFnMap, ...sceneFnMap };
    const sharedBaseHash = sha256(sharedBase);
    const fullHtmlHash = sha256(inlinedHtml);
    const globalMetaHash = sha256(JSON.stringify({
      version: DS.VERSION,
      fps,
      jpegQuality,
      totalDuration: manifest.total_duration,
      totalFrames,
      epMeta,
      // Include scene timing boundaries so progress bar segment shifts always invalidate cleanly
      sceneBoundaries: segments.map(s => [s.scene_id, s.startFrame, s.endFrame]),
    }));

    const plan = segments.map(seg => {
      const fnName = mergedSceneFnMap[seg.scene_id] || '';
      const hasIsolatedBlock = Boolean(
        (fnName && Object.prototype.hasOwnProperty.call(sceneBlocks, fnName))
        || Object.prototype.hasOwnProperty.call(sceneBlocks, seg.scene_id),
      );
      const blockKey = (fnName && Object.prototype.hasOwnProperty.call(sceneBlocks, fnName))
        ? fnName
        : seg.scene_id;
      const codeHash = hasIsolatedBlock
        ? sha256(`${sharedBaseHash}:${blockKey}:${sceneBlocks[blockKey]}`)
        : fullHtmlHash;

      const sceneLines = seg.beatIndices.map(bi => manifest.lines[bi]);
      const sceneSubs = subs.filter(s => s.end >= seg.startTime - 0.1 && s.start <= seg.endTime + 0.1);
      const sceneHash = sha256(JSON.stringify({
        codeHash,
        globalMetaHash,
        scene_id: seg.scene_id,
        startFrame: seg.startFrame,
        endFrame: seg.endFrame,
        sceneLines,
        sceneSubs,
      }));
      const hash16 = sceneHash.slice(0, 16);
      const baseName = `${String(seg.index).padStart(2, '0')}_${safeSlug(seg.scene_id)}_${hash16}`;
      const mp4Path = path.join(cacheDir, `${baseName}.mp4`);
      const auditPath = path.join(cacheDir, `${baseName}.audit.json`);
      const isHit = !force && fs.existsSync(mp4Path) && fs.statSync(mp4Path).size > 0 && fs.existsSync(auditPath);
      return { seg, hash: sceneHash, hash16, mp4Path, auditPath, isHit, isolated: hasIsolatedBlock };
    });

    const dirtyItems = plan.filter(item => !item.isHit);
    const hitItems = plan.filter(item => item.isHit);
    console.log(
      `[${epId}] Scene cache plan: ${hitItems.length} hit(s), ${dirtyItems.length} miss(es) ` +
      `(${dirtyItems.reduce((s, x) => s + x.seg.frameCount, 0)}/${totalFrames} frames to render, workers=${workers})`,
    );

    // 6. Render cover PNG on tab 0 (if enabled)
    let coverOut = null;
    if (!skipCover) {
      coverOut = path.join(outDir, `${stem}-封面.png`);
      const covEv = await tab0.send('Runtime.evaluate', {
        expression: `typeof window.renderCover === "function" ? (window.renderCover(${JSON.stringify(epMeta)}), true) : false`,
        returnByValue: true,
      });
      if (covEv.exceptionDetails) {
        throw new Error(`renderCover failed: ${covEv.exceptionDetails.exception?.description || covEv.exceptionDetails.text}`);
      }
      if (covEv.result.value === true) {
        const covShot = await tab0.send('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(coverOut, Buffer.from(covShot.data, 'base64'));
        console.log(`[${epId}] Cover saved -> ${coverOut}`);
      } else {
        coverOut = null;
      }
    }

    // 7. Spawn extra worker tabs (up to min(workers, dirtyItems.length)) and render dirty scenes in parallel
    const targetWorkers = Math.max(1, Math.min(Number(workers) || 1, Math.max(1, dirtyItems.length)));
    if (targetWorkers > 1) {
      const createdIds = [];
      for (let w = 1; w < targetWorkers; w++) {
        const res = await tab0.send('Target.createTarget', { url: 'about:blank' });
        createdIds.push(res.targetId);
      }
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const extraTabs = await Promise.all(createdIds.map(tid => {
        const target = targets.find(t => t.id === tid && t.webSocketDebuggerUrl);
        if (!target) throw new Error(`Worker target ${tid} missing webSocketDebuggerUrl`);
        return initWorkerTab(target.webSocketDebuggerUrl, inlinedHtmlPath, renderData);
      }));
      workerTabs.push(...extraTabs);
    }

    const sceneResults = new Map();
    for (const hit of hitItems) {
      sceneResults.set(hit.seg.index, {
        status: 'hit',
        elapsed_sec: 0,
        audit: JSON.parse(fs.readFileSync(hit.auditPath, 'utf8')),
      });
    }

    if (dirtyItems.length > 0) {
      let nextIdx = 0;
      const runWorker = async tab => {
        while (true) {
          const i = nextIdx++;
          if (i >= dirtyItems.length) break;
          const item = dirtyItems[i];
          const res = await renderSceneSegment(
            tab, item.seg, item.mp4Path, item.auditPath, fps, jpegQuality, epId,
          );
          sceneResults.set(item.seg.index, {
            status: 'miss',
            elapsed_sec: res.elapsedSec,
            audit: res.audit,
          });
        }
      };
      await Promise.all(workerTabs.slice(0, targetWorkers).map(runWorker));
    }

    // 8. Merge per-scene render audits into canonical single-pass-equivalent render_audit.json
    const orderedAudits = plan.map(item => sceneResults.get(item.seg.index)?.audit).filter(Boolean);
    const mergedAudit = orderedAudits.length ? DS.mergeFrameAudits(orderedAudits) : null;
    const auditPath = path.join(tmpDir, `${epId}_render_audit.json`);
    if (mergedAudit) {
      fs.writeFileSync(auditPath, JSON.stringify(mergedAudit, null, 2), 'utf8');
    }

    // 9. Losslessly concat scene MP4 segments + mux mixed audio into bodyMp4
    const concatListPath = path.join(tmpDir, `${epId}_scenes_concat.txt`);
    fs.writeFileSync(
      concatListPath,
      plan.map(item => `file '${item.mp4Path.replace(/'/g, "'\\''")}'`).join('\n') + '\n',
      'utf8',
    );
    const bodyMp4 = path.join(tmpDir, `${epId}_body.mp4`);
    execFileSync('ffmpeg', [
      '-v', 'error', '-y',
      '-f', 'concat', '-safe', '0', '-i', concatListPath,
      '-i', mixedWav,
      '-map', '0:v:0', '-map', '1:a:0',
      '-c:v', 'copy',
      '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k',
      '-shortest', '-movflags', '+faststart', bodyMp4,
    ], { stdio: 'inherit' });

    // 10. Package final video (optional frame0 cover + intro/outro bookends + attached_pic)
    const hasBookends = Boolean(introMp4 && outroMp4 && fs.existsSync(introMp4) && fs.existsSync(outroMp4));
    const frame0Dur = 1 / fps;
    let bodyOffset = 0;
    const finalMp4 = path.join(outDir, `${stem}.mp4`);

    if (hasBookends && coverOut) {
      const introDur = probeDuration(introMp4);
      const outroDur = probeDuration(outroMp4);
      bodyOffset = frame0Dur + introDur;
      const outroFadeStart = Math.max(0.5, outroDur - 0.36);

      const frame0Mp4 = path.join(tmpDir, `${epId}_frame0.mp4`);
      execFileSync('ffmpeg', [
        '-v', 'error', '-y', '-loop', '1', '-i', coverOut,
        '-f', 'lavfi', '-i', `anullsrc=r=48000:cl=stereo:d=${frame0Dur.toFixed(6)}`,
        '-frames:v', '1', '-r', String(fps),
        '-vf', 'scale=1920:1080:in_range=full:out_range=tv,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-color_range', 'tv',
        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k', '-shortest', frame0Mp4,
      ], { stdio: 'inherit' });

      const concatMp4 = path.join(tmpDir, `${epId}_concat.mp4`);
      execFileSync('ffmpeg', [
        '-v', 'error', '-y', '-i', frame0Mp4, '-i', introMp4, '-i', bodyMp4, '-i', outroMp4,
        '-filter_complex',
        `[0:v]fps=${fps},scale=1920:1080:out_range=tv,setsar=1,format=yuv420p[v0];` +
        `[1:v]fps=${fps},scale=1920:1080:out_range=tv,setsar=1,format=yuv420p[v1];` +
        `[2:v]fps=${fps},scale=1920:1080:out_range=tv,setsar=1,format=yuv420p[v2];` +
        `[3:v]fps=${fps},scale=1920:1080:out_range=tv,setsar=1,format=yuv420p[v3];` +
        '[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];' +
        '[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];' +
        '[2:a]aresample=48000,aformat=channel_layouts=stereo[a2];' +
        `[3:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=out:st=${outroFadeStart.toFixed(2)}:d=0.36[a3];` +
        '[v0][a0][v1][a1][v2][a2][v3][a3]concat=n=4:v=1:a=1[v][a]',
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-r', String(fps),
        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k', '-movflags', '+faststart', concatMp4,
      ], { stdio: 'inherit' });

      execFileSync('ffmpeg', [
        '-v', 'error', '-y', '-i', concatMp4, '-i', coverOut,
        '-map', '0:v:0', '-map', '0:a:0', '-map', '1:v:0',
        '-c:v:0', 'copy', '-c:a:0', 'copy', '-c:v:1', 'png',
        '-disposition:v:1', 'attached_pic', '-movflags', '+faststart', finalMp4,
      ], { stdio: 'inherit' });
    } else if (coverOut) {
      execFileSync('ffmpeg', [
        '-v', 'error', '-y', '-i', bodyMp4, '-i', coverOut,
        '-map', '0:v:0', '-map', '0:a:0', '-map', '1:v:0',
        '-c:v:0', 'copy', '-c:a:0', 'copy', '-c:v:1', 'png',
        '-disposition:v:1', 'attached_pic', '-movflags', '+faststart', finalMp4,
      ], { stdio: 'inherit' });
    } else {
      fs.copyFileSync(bodyMp4, finalMp4);
    }

    // 11. Write final SRT, timeline.json, and render_cache_report.json
    const finalSrt = path.join(outDir, `${stem}.srt`);
    fs.writeFileSync(
      finalSrt,
      subs.map((s, i) => `${i + 1}\n${fmtSrt(s.start + bodyOffset)} --> ${fmtSrt(s.end + bodyOffset)}\n${s.text}\n\n`).join(''),
      'utf8',
    );

    const timelinePath = path.join(tmpDir, `${epId}_timeline.json`);
    fs.writeFileSync(timelinePath, JSON.stringify({
      ep_id: epId,
      body_offset: bodyOffset,
      timeline: manifest.lines.map(l => ({
        id: l.id,
        scene_id: l.scene_id,
        layout_kind: l.layout_kind,
        start: Number((Number(l.start) + bodyOffset).toFixed(3)),
        end: Number((Number(l.end) + bodyOffset).toFixed(3)),
        text: l.text,
      })),
    }, null, 2), 'utf8');

    const totalElapsedSec = Number(((Date.now() - tStart) / 1000).toFixed(2));
    const cacheReport = {
      schema: 'kgxc-render-cache-report/1',
      version: DS.VERSION,
      ep_id: epId,
      workers: targetWorkers,
      total_scenes: plan.length,
      cache_hits: hitItems.length,
      cache_misses: dirtyItems.length,
      cached_frames: hitItems.reduce((s, x) => s + x.seg.frameCount, 0),
      rendered_frames: dirtyItems.reduce((s, x) => s + x.seg.frameCount, 0),
      total_frames: totalFrames,
      elapsed_sec: totalElapsedSec,
      output_mp4: finalMp4,
      render_audit: auditPath,
      timeline: timelinePath,
      scenes: plan.map(item => {
        const res = sceneResults.get(item.seg.index);
        return {
          index: item.seg.index,
          scene_id: item.seg.scene_id,
          start_frame: item.seg.startFrame,
          end_frame: item.seg.endFrame,
          frames: item.seg.frameCount,
          hash: item.hash16,
          isolated_source: item.isolated,
          status: res?.status || 'miss',
          elapsed_sec: res?.elapsed_sec ?? 0,
        };
      }),
    };
    const cacheReportPath = path.join(tmpDir, `${epId}_render_cache_report.json`);
    fs.writeFileSync(cacheReportPath, JSON.stringify(cacheReport, null, 2), 'utf8');
    console.log(
      `[${epId}] COMPLETE in ${totalElapsedSec}s (${hitItems.length} cached / ${dirtyItems.length} rendered) -> ${finalMp4}`,
    );
    return cacheReport;
  } finally {
    for (const tab of workerTabs) tab.close();
    try { proc.kill('SIGTERM'); } catch {}
  }
}

function parseCliArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--html') opts.htmlPath = argv[++i];
    else if (a === '--audio-dir') opts.audioDir = argv[++i];
    else if (a === '--out-dir') opts.outDir = argv[++i];
    else if (a === '--tmp-dir') opts.tmpDir = argv[++i];
    else if (a === '--meta-json') opts.metaJson = argv[++i];
    else if (a === '--intro') opts.introMp4 = argv[++i];
    else if (a === '--outro') opts.outroMp4 = argv[++i];
    else if (a === '--logo') opts.logoPath = argv[++i];
    else if (a === '--kg-orig') opts.kgOrigPath = argv[++i];
    else if (a === '--chrome') opts.chromePath = argv[++i];
    else if (a === '--workers') opts.workers = parseInt(argv[++i], 10);
    else if (a === '--port') opts.port = parseInt(argv[++i], 10);
    else if (a === '--fps') opts.fps = parseInt(argv[++i], 10);
    else if (a === '--quality') opts.jpegQuality = parseInt(argv[++i], 10);
    else if (a === '--force') opts.force = true;
    else if (a === '--skip-cover') opts.skipCover = true;
  }
  return opts;
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  const cli = parseCliArgs(process.argv.slice(2));
  if (!cli.htmlPath || !cli.audioDir || !cli.outDir || !cli.tmpDir) {
    console.error('Usage: node render_director_incremental.mjs --html <file> --audio-dir <dir> --out-dir <dir> --tmp-dir <dir> [--meta-json <file>] [--intro <mp4> --outro <mp4>] [--workers 3] [--port 9388] [--force] [--skip-cover]');
    process.exit(2);
  }
  const epMeta = cli.metaJson ? JSON.parse(fs.readFileSync(cli.metaJson, 'utf8')) : { ep_id: 'ep', stem: 'episode' };
  renderDirectorIncremental({ ...cli, epMeta }).catch(err => {
    console.error(err);
    process.exit(1);
  });
}
