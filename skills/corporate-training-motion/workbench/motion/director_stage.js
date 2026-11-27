/**
 * DirectorStage v8.0.0 — Shared Cinematic Director Engine for Pilots & Full Episodes.
 *
 * Solves 5 structural failure modes:
 * 1. Dual-Layer Timeline (Scene vs Beat): continuous `sceneT` never resets across sub-beats,
 *    eliminating animation replay/reset loops when a sentence spans multiple beats.
 * 2. Multi-Keyframe Cinematic Camera: real push/pull/pan/shake choreography across a scene
 *    instead of static slides or fake ±12px camera wiggle.
 * 3. Runtime Grounding & Collision Telemetry: records every actor & text/bubble/danmaku rect
 *    per frame so verify_delivery.py --render-audit blocks floating walk, text-over-actor overlap,
 *    PPT box overload (>25%), and dead cameras before delivery.
 */
(function (global) {
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * clamp(t);
  const EASERS = {
    linear: t => clamp(t),
    easeOut: t => 1 - Math.pow(1 - clamp(t), 3),
    easeInOut: t => { const u = clamp(t); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; },
    easeOutExpo: t => { const u = clamp(t); return u >= 1 ? 1 : 1 - Math.pow(2, -10 * u); },
  };

  function overlapArea(a, b) {
    if (!a || !b) return 0;
    const x1 = Math.max(a.x, b.x);
    const y1 = Math.max(a.y, b.y);
    const x2 = Math.min(a.x + a.w, b.x + b.w);
    const y2 = Math.min(a.y + a.h, b.y + b.h);
    return (x2 > x1 && y2 > y1) ? (x2 - x1) * (y2 - y1) : 0;
  }

  /**
   * Group consecutive beats that share the same `scene_id` into continuous scene spans.
   * Each beat retains its own `beatT`, while `sceneT` advances monotonically across the whole scene.
   */
  function buildSceneIndex(lines = []) {
    const scenes = [];
    const beatToScene = new Array(lines.length);
    let cur = null;
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      const sid = ln.scene_id || `${ln.scene || 'scene'}_${i}`;
      if (!cur || cur.scene_id !== sid) {
        cur = {
          scene_id: sid,
          scene: ln.scene || '',
          layout_kind: ln.layout_kind || 'kinetic_metaphor',
          start: Number(ln.start || 0),
          end: Number(ln.end || 0),
          firstBeatIdx: i,
          lastBeatIdx: i,
          beatIndices: [i],
        };
        scenes.push(cur);
      } else {
        cur.end = Math.max(cur.end, Number(ln.end || 0));
        cur.lastBeatIdx = i;
        cur.beatIndices.push(i);
      }
      beatToScene[i] = scenes.length - 1;
    }
    return { scenes, beatToScene };
  }

  /**
   * Resolve current timestamp `t` into both Beat-level and continuous Scene-level timing.
   */
  function resolveTimeline(lines = [], t = 0) {
    if (!lines.length) {
      throw new Error('DirectorStage.resolveTimeline: lines array is empty.');
    }
    const { scenes, beatToScene } = buildSceneIndex(lines);
    let beatIdx = 0;
    for (let i = 0; i < lines.length; i++) {
      const inSpan = i === lines.length - 1 ? (t >= lines[i].start && t <= lines[i].end) : (t >= lines[i].start && t < lines[i].end);
      if (inSpan) { beatIdx = i; break; }
      if (t >= lines[i].start) beatIdx = i;
    }
    const beat = lines[beatIdx];
    const scene = scenes[beatToScene[beatIdx]];
    const beatStart = Number(beat.start || 0);
    const beatEnd = Number(beat.end || beatStart + 0.1);
    const beatDur = Math.max(0.1, beatEnd - beatStart);
    const beatT = Math.max(0, t - beatStart);
    const speechStart = Number(beat.speech_start ?? beatStart);
    const speechEnd = Math.max(speechStart + 0.08, Number(beat.speech_end ?? beatEnd));
    const speechT = Math.max(0, t - speechStart);
    const speechDur = Math.max(0.08, speechEnd - speechStart);
    const sceneDur = Math.max(0.1, scene.end - scene.start);
    const sceneT = Math.max(0, t - scene.start);
    const sceneBeatIndex = beatIdx - scene.firstBeatIdx;
    return {
      t,
      beatIdx,
      beat,
      beatId: beat.id || `beat_${beatIdx}`,
      beatT,
      beatDur,
      beatU: clamp(beatT / beatDur),
      speechStart,
      speechEnd,
      speechT,
      speechDur,
      speechU: clamp(speechT / speechDur),
      sceneId: scene.scene_id,
      sceneName: scene.scene,
      layoutKind: beat.layout_kind || scene.layout_kind || 'kinetic_metaphor',
      sceneStart: scene.start,
      sceneEnd: scene.end,
      sceneT,
      sceneDur,
      sceneU: clamp(sceneT / sceneDur),
      isSceneEntry: sceneBeatIndex === 0,
      sceneBeatIndex,
      sceneBeatCount: scene.beatIndices.length,
    };
  }

  /**
   * Locate the speaking timestamp of `phrase` inside `beat` (in sceneT coordinates when sceneStart > 0).
   * Guarantees the returned trigger is never earlier than the beat's actual vocal onset (`speech_start`).
   */
  function phraseTime(beat, phrase = '', sceneStart = 0, leadPad = 0) {
    if (!beat) return 0;
    const sStart = Number(beat.speech_start ?? beat.start ?? 0);
    const sEnd = Math.max(sStart + 0.08, Number(beat.speech_end ?? beat.end ?? sStart + 0.5));
    const floorT = Math.max(0, sStart - sceneStart);
    const ph = String(phrase || '').trim();
    if (!ph) return Math.max(floorT, sStart - sceneStart + leadPad);
    if (beat.anchors && beat.anchors[ph] != null) {
      return Math.max(floorT, Number(beat.anchors[ph]) - sceneStart + leadPad);
    }
    const raw = String(beat.text || '');
    const weights = [];
    const cleanChars = [];
    const cleanToRaw = [];
    const majorPunct = new Set(['，', '。', '！', '？', '；', '：', '—', ',', '.', '!', '?', ';', ':']);
    const punctRe = /[\p{P}\p{S}]/u;
    for (let i = 0; i < raw.length; i++) {
      const ch = raw[i];
      if (/\s/.test(ch)) {
        weights.push(0.15);
      } else if (punctRe.test(ch)) {
        weights.push(majorPunct.has(ch) ? 0.75 : 0.25);
      } else {
        weights.push(1.0);
        cleanChars.push(ch.toLowerCase());
        cleanToRaw.push(i);
      }
    }
    const totalW = weights.reduce((a, b) => a + b, 0) || 1;
    const cum = [];
    let acc = 0;
    for (const w of weights) {
      cum.push(acc / totalW);
      acc += w;
    }
    const cleanPh = ph.replace(/[\s\p{P}\p{S}]/gu, '').toLowerCase();
    const pos = cleanPh ? cleanChars.join('').indexOf(cleanPh) : -1;
    if (pos < 0) return Math.max(floorT, sStart - sceneStart + leadPad);
    const rawIdx = cleanToRaw[pos];
    const absT = sStart + (sEnd - sStart) * cum[rawIdx] + leadPad;
    return Math.max(floorT, absT - sceneStart);
  }

  /**
   * Explicit rock-steady camera for summary_board / reading boards (zero sway, zero drift).
   */
  function steadyCamera() {
    return { x: 0, y: 0, zoom: 1, rot: 0, steady: true };
  }

  /**
   * Evaluate a multi-keyframe cinematic camera track at `sceneT`.
   * Keyframe shape: { at: seconds, x, y, zoom, rot?, ease?, hold?, holdUntil?, shakeAmp?, shakeFreq? }
   * Use `hold` or `holdUntil` so the camera glides purposefully into place and then locks steady during reading.
   */
  function evalCamera(keyframes = [], sceneT = 0, globalT = sceneT) {
    if (!Array.isArray(keyframes) || keyframes.length === 0) {
      return { x: 0, y: 0, zoom: 1, rot: 0 };
    }
    const rawSorted = keyframes.slice().sort((a, b) => (a.at || 0) - (b.at || 0));
    const sorted = [];
    for (let i = 0; i < rawSorted.length; i++) {
      const k = rawSorted[i];
      const at = Number(k.at || 0);
      sorted.push(k);
      let holdEnd = null;
      if (k.holdUntil != null && Number(k.holdUntil) > at + 0.001) {
        holdEnd = Number(k.holdUntil);
      } else if (k.hold != null && Number(k.hold) > 0.001) {
        holdEnd = at + Number(k.hold);
      }
      if (holdEnd != null) {
        const nextAt = i + 1 < rawSorted.length ? Number(rawSorted[i + 1].at || 0) : Infinity;
        const clampedEnd = Math.min(holdEnd, nextAt - 0.001);
        if (clampedEnd > at + 0.001) {
          sorted.push({
            at: clampedEnd,
            x: k.x || 0,
            y: k.y || 0,
            zoom: k.zoom ?? 1,
            rot: k.rot || 0,
            ease: 'linear',
            shakeAmp: 0,
          });
        }
      }
    }
    if (sceneT <= (sorted[0].at || 0)) {
      const k = sorted[0];
      return { x: k.x || 0, y: k.y || 0, zoom: k.zoom ?? 1, rot: k.rot || 0 };
    }
    const last = sorted[sorted.length - 1];
    if (sceneT >= (last.at || 0)) {
      return { x: last.x || 0, y: last.y || 0, zoom: last.zoom ?? 1, rot: last.rot || 0 };
    }
    let a = sorted[0], b = sorted[1];
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sceneT >= (sorted[i].at || 0) && sceneT <= (sorted[i + 1].at || 0)) {
        a = sorted[i];
        b = sorted[i + 1];
        break;
      }
    }
    const span = Math.max(0.001, (b.at || 0) - (a.at || 0));
    const easeFn = EASERS[b.ease || 'easeInOut'] || EASERS.easeInOut;
    const u = easeFn((sceneT - (a.at || 0)) / span);
    const shakeAmp = b.shakeAmp || 0;
    const shake = shakeAmp > 0 ? Math.sin(globalT * (b.shakeFreq || 26)) * shakeAmp * Math.sin(u * Math.PI) : 0;
    return {
      x: lerp(a.x || 0, b.x || 0, u) + shake,
      y: lerp(a.y || 0, b.y || 0, u),
      zoom: lerp(a.zoom ?? 1, b.zoom ?? 1, u),
      rot: lerp(a.rot || 0, b.rot || 0, u),
    };
  }

  /**
   * Build continuous chapter navigation segments directly from `lines` audio timeline.
   * Each spec: { id?, label, scenes: ['sc01_...', ...] } (or explicit start/end).
   * Eliminates hardcoded percentages or mismatched segment boundaries.
   */
  function buildNavSegments(lines = [], chapterSpecs = [], totalDuration = null) {
    if (!Array.isArray(chapterSpecs) || chapterSpecs.length < 2) {
      throw new Error('DirectorStage.buildNavSegments: chapterSpecs must contain at least 2 chapter segments.');
    }
    const { scenes } = buildSceneIndex(lines);
    const byScene = new Map(scenes.map(sc => [sc.scene_id, sc]));
    const lastLineEnd = lines.length ? Number(lines[lines.length - 1].end || 0) : 0;
    const total = Number(totalDuration ?? lastLineEnd) || lastLineEnd || 1;
    const raw = chapterSpecs.map((spec, idx) => {
      let start = spec.start != null ? Number(spec.start) : Infinity;
      let end = spec.end != null ? Number(spec.end) : -Infinity;
      if (Array.isArray(spec.scenes) && spec.scenes.length) {
        for (const sid of spec.scenes) {
          const sc = byScene.get(sid);
          if (sc) {
            start = Math.min(start, sc.start);
            end = Math.max(end, sc.end);
          }
        }
      }
      if (!Number.isFinite(start) || !Number.isFinite(end)) {
        throw new Error(`DirectorStage.buildNavSegments: segment "${spec.label || idx}" matched no scenes in lines.`);
      }
      return {
        id: spec.id || `seg_${idx + 1}`,
        label: String(spec.label || `第${idx + 1}段`),
        start: Number(start.toFixed(3)),
        end: Number(end.toFixed(3)),
      };
    });
    // Stitch small inter-scene gaps cleanly so `t` always belongs unambiguously to one segment
    raw[0].start = 0;
    for (let i = 1; i < raw.length; i++) {
      raw[i - 1].end = raw[i].start;
    }
    raw[raw.length - 1].end = Math.max(raw[raw.length - 1].end, total);
    return raw;
  }

  /**
   * Runtime frame auditor: collects actor motion, text-actor collisions, layout mix,
   * segmented progress bar telemetry, and camera trajectory for verify_delivery.py --render-audit.
   */
  function createFrameAuditor(opts = {}) {
    const overlapTolerancePx2 = opts.overlapTolerancePx2 ?? 64;
    const floatingMovePx = opts.floatingMovePx ?? 10;
    const captionTopY = opts.captionTopY ?? 942;
    const revealLeadToleranceSec = opts.revealLeadToleranceSec ?? 0.08;
    let cur = null;
    const prevActorsByScene = new Map();
    const floatingViolations = [];
    const overlapViolations = [];
    const replayViolations = [];
    const prematureRevealViolations = [];
    const seenPrematureKeys = new Set();
    const beatLayouts = new Map();
    const beatOrder = [];
    const sceneCameras = new Map();
    const lastSceneTByScene = new Map();
    let totalFrames = 0;
    let progressBarInfo = null;
    const visitedNavSegments = new Set();

    function flushFrame() {
      if (!cur) return;
      // 1. Check floating walk (horizontal displacement within same scene without grounded walkState)
      const prevMap = prevActorsByScene.get(cur.sceneId) || new Map();
      const nextMap = new Map();
      for (const act of cur.actors) {
        const prev = prevMap.get(act.id);
        if (prev) {
          const dx = Math.abs(act.x - prev.x);
          if (dx > floatingMovePx && !act.groundedWalk && !prev.groundedWalk) {
            floatingViolations.push({
              frame: cur.frame,
              t: Number(cur.t.toFixed(3)),
              scene_id: cur.sceneId,
              beat_id: cur.beatId,
              actor: act.id,
              dx: Number(dx.toFixed(1)),
              reason: 'Actor moved horizontally without grounded walkState (floating walk)',
            });
          }
        }
        nextMap.set(act.id, act);
      }
      prevActorsByScene.set(cur.sceneId, nextMap);

      // 2. Check text-actor overlap, caption-zone intrusion & bubble vocal-onset sync
      for (const txt of cur.texts) {
        if (txt.kind === 'bubble' && cur.speechStart != null && cur.t < cur.speechStart - revealLeadToleranceSec) {
          const key = `${cur.sceneId}|${cur.beatId}|bubble|${txt.id}`;
          if (!seenPrematureKeys.has(key)) {
            seenPrematureKeys.add(key);
            prematureRevealViolations.push({
              frame: cur.frame,
              t: Number(cur.t.toFixed(3)),
              target_t: Number(cur.speechStart.toFixed(3)),
              lead_sec: Number((cur.speechStart - cur.t).toFixed(3)),
              scene_id: cur.sceneId,
              beat_id: cur.beatId,
              item_id: txt.id,
              reason: 'Speaker bubble appeared before actual vocal onset (speech_start)',
            });
          }
        }
        for (const act of cur.actors) {
          const hitHead = overlapArea(txt.rect, act.headRect);
          const hitBody = overlapArea(txt.rect, act.bodyRect);
          if (hitHead > overlapTolerancePx2 || hitBody > overlapTolerancePx2) {
            overlapViolations.push({
              frame: cur.frame,
              t: Number(cur.t.toFixed(3)),
              scene_id: cur.sceneId,
              beat_id: cur.beatId,
              text_id: txt.id,
              text_kind: txt.kind,
              actor: act.id,
              overlap_px2: Math.round(Math.max(hitHead, hitBody)),
            });
          }
        }
        if (txt.kind !== 'caption' && txt.kind !== 'progress' && (txt.rect.y + txt.rect.h) > captionTopY) {
          overlapViolations.push({
            frame: cur.frame,
            t: Number(cur.t.toFixed(3)),
            scene_id: cur.sceneId,
            beat_id: cur.beatId,
            text_id: txt.id,
            text_kind: txt.kind,
            actor: 'caption_safe_zone',
            overlap_px2: Math.round((txt.rect.y + txt.rect.h - captionTopY) * txt.rect.w),
          });
        }
      }
      cur = null;
    }

    function beginFrame(frameIndex, t, resolved, layoutKind, cam = null) {
      flushFrame();
      totalFrames++;
      const sceneId = resolved.sceneId;
      const beatId = resolved.beatId;
      const lk = layoutKind || resolved.layoutKind || 'kinetic_metaphor';

      // Detect sceneT resetting backward inside the same scene_id
      if (lastSceneTByScene.has(sceneId) && resolved.sceneT + 0.05 < lastSceneTByScene.get(sceneId)) {
        replayViolations.push({
          frame: frameIndex,
          t: Number(t.toFixed(3)),
          scene_id: sceneId,
          beat_id: beatId,
          reason: 'sceneT reset backward inside same scene_id (animation replay)',
        });
      }
      lastSceneTByScene.set(sceneId, resolved.sceneT);

      if (!beatLayouts.has(beatId)) {
        beatLayouts.set(beatId, lk);
        beatOrder.push({ beat_id: beatId, scene_id: sceneId, layout_kind: lk });
      }

      if (cam) {
        const cx = cam.x || 0;
        const cy = cam.y || 0;
        const cz = cam.zoom ?? 1;
        const sc = sceneCameras.get(sceneId) || {
          scene_id: sceneId,
          layout_kind: lk,
          minX: cx, maxX: cx,
          minY: cy, maxY: cy,
          minZoom: cz, maxZoom: cz,
          frames: 0,
          movingFrames: 0,
          prevX: cx, prevY: cy, prevZ: cz,
          anchorX: cx, dirX: 0, xReversals: 0,
          anchorY: cy, dirY: 0, yReversals: 0,
        };
        sc.minX = Math.min(sc.minX, cx);
        sc.maxX = Math.max(sc.maxX, cx);
        sc.minY = Math.min(sc.minY, cy);
        sc.maxY = Math.max(sc.maxY, cy);
        sc.minZoom = Math.min(sc.minZoom, cz);
        sc.maxZoom = Math.max(sc.maxZoom, cz);
        if (sc.frames > 0) {
          const dx = cx - sc.prevX;
          const dy = cy - sc.prevY;
          const dz = cz - sc.prevZ;
          if (Math.abs(dx) > 0.25 || Math.abs(dy) > 0.25 || Math.abs(dz) > 0.0004) {
            sc.movingFrames++;
          }
          // Count meaningful direction reversals (>= 8px travel before reversing) to catch aimless swaying
          if (sc.dirX === 0) {
            if (Math.abs(cx - sc.anchorX) >= 8) { sc.dirX = cx > sc.anchorX ? 1 : -1; sc.anchorX = cx; }
          } else if (sc.dirX > 0) {
            if (cx > sc.anchorX) sc.anchorX = cx;
            else if (sc.anchorX - cx >= 8) { sc.xReversals++; sc.dirX = -1; sc.anchorX = cx; }
          } else {
            if (cx < sc.anchorX) sc.anchorX = cx;
            else if (cx - sc.anchorX >= 8) { sc.xReversals++; sc.dirX = 1; sc.anchorX = cx; }
          }
          if (sc.dirY === 0) {
            if (Math.abs(cy - sc.anchorY) >= 8) { sc.dirY = cy > sc.anchorY ? 1 : -1; sc.anchorY = cy; }
          } else if (sc.dirY > 0) {
            if (cy > sc.anchorY) sc.anchorY = cy;
            else if (sc.anchorY - cy >= 8) { sc.yReversals++; sc.dirY = -1; sc.anchorY = cy; }
          } else {
            if (cy < sc.anchorY) sc.anchorY = cy;
            else if (cy - sc.anchorY >= 8) { sc.yReversals++; sc.dirY = 1; sc.anchorY = cy; }
          }
        }
        sc.prevX = cx; sc.prevY = cy; sc.prevZ = cz;
        sc.frames++;
        sceneCameras.set(sceneId, sc);
      }

      cur = {
        frame: frameIndex,
        t,
        speechStart: resolved.speechStart ?? null,
        sceneId,
        beatId,
        layoutKind: lk,
        actors: [],
        texts: [],
      };
    }

    function recordActor(id, bounds, walkState = null) {
      if (!cur || !bounds) return;
      cur.actors.push({
        id: String(id),
        x: bounds.rootX,
        footY: bounds.footY,
        headRect: bounds.headRect,
        bodyRect: bounds.bodyRect,
        groundedWalk: Boolean(walkState && (walkState.walking || walkState.walkWeight > 0)),
      });
    }

    function recordText(id, rect, kind = 'label') {
      if (!cur || !rect) return;
      cur.texts.push({ id: String(id), rect, kind });
    }

    /**
     * Record a spoken-reveal item so the auditor blocks visual elements appearing ahead of narration.
     * Pass `targetAbsTime` (or `resolved.sceneStart + targetSceneT`) when the item becomes visible.
     */
    function recordReveal(id, targetAbsTime, isVisible = true) {
      if (!cur || !isVisible || targetAbsTime == null) return;
      const target = Number(targetAbsTime);
      if (Number.isFinite(target) && cur.t < target - revealLeadToleranceSec) {
        const key = `${cur.sceneId}|reveal|${id}`;
        if (!seenPrematureKeys.has(key)) {
          seenPrematureKeys.add(key);
          prematureRevealViolations.push({
            frame: cur.frame,
            t: Number(cur.t.toFixed(3)),
            target_t: Number(target.toFixed(3)),
            lead_sec: Number((target - cur.t).toFixed(3)),
            scene_id: cur.sceneId,
            beat_id: cur.beatId,
            item_id: String(id),
            reason: 'Visual element revealed ahead of narration anchor',
          });
        }
      }
    }

    function recordProgressBar(navInfo) {
      if (!navInfo) return;
      if (!progressBarInfo) {
        progressBarInfo = {
          mode: navInfo.mode || 'segmented',
          style: navInfo.style || 'inline_pill',
          segment_count: Number(navInfo.segment_count || 0),
          labels: Array.isArray(navInfo.labels) ? navInfo.labels.slice() : [],
          bar_top_y: navInfo.barTopY ?? null,
        };
      }
      if (navInfo.activeIdx != null) {
        visitedNavSegments.add(Number(navInfo.activeIdx));
      }
    }

    function finalize() {
      flushFrame();
      const layoutCounts = {};
      let maxConsecCard = 0, curConsecCard = 0;
      for (const b of beatOrder) {
        layoutCounts[b.layout_kind] = (layoutCounts[b.layout_kind] || 0) + 1;
        if (b.layout_kind === 'card_box') {
          curConsecCard++;
          if (curConsecCard > maxConsecCard) maxConsecCard = curConsecCard;
        } else {
          curConsecCard = 0;
        }
      }
      const totalBeats = Math.max(1, beatOrder.length);
      const cardBoxRatio = Number(((layoutCounts.card_box || 0) / totalBeats).toFixed(3));
      const summaryBoardRatio = Number(((layoutCounts.summary_board || 0) / totalBeats).toFixed(3));
      const cameraSwayViolations = [];
      const cameraSummary = Array.from(sceneCameras.values()).map(sc => {
        const panSpan = Number(Math.hypot(sc.maxX - sc.minX, sc.maxY - sc.minY).toFixed(1));
        const zoomSpan = Number((sc.maxZoom - sc.minZoom).toFixed(4));
        const movingRatio = Number((sc.movingFrames / Math.max(1, sc.frames - 1)).toFixed(3));
        const reversals = sc.xReversals + sc.yReversals;
        if (sc.layout_kind === 'summary_board' || sc.layout_kind === 'card_box') {
          if (panSpan > 12 || zoomSpan > 0.025) {
            cameraSwayViolations.push({
              scene_id: sc.scene_id,
              layout_kind: sc.layout_kind,
              pan_span_px: panSpan,
              zoom_span: zoomSpan,
              reason: 'summary_board/card_box 信息总结板书禁止缩放平移晃动，请保持定机位并靠逐条揭示推进',
            });
          }
        } else if (
          (sc.layout_kind === 'kinetic_metaphor' || sc.layout_kind === 'data_sculpture')
          && sc.frames >= 144
          && movingRatio > 0.85
          && reversals >= 2
        ) {
          cameraSwayViolations.push({
            scene_id: sc.scene_id,
            layout_kind: sc.layout_kind,
            moving_ratio: movingRatio,
            direction_reversals: reversals,
            pan_span_px: panSpan,
            zoom_span: zoomSpan,
            reason: '知识场景镜头全程漂移且反复折返摇摆，请为关键帧添加 hold/holdUntil 停稳区间',
          });
        }
        return {
          scene_id: sc.scene_id,
          layout_kind: sc.layout_kind,
          pan_span_px: panSpan,
          zoom_span: zoomSpan,
          moving_ratio: movingRatio,
          direction_reversals: reversals,
          frames: sc.frames,
        };
      });
      return {
        schema: 'kgxc-director-audit/1',
        total_frames: totalFrames,
        total_beats: beatOrder.length,
        layout_kind_counts: layoutCounts,
        card_box_ratio: cardBoxRatio,
        summary_board_ratio: summaryBoardRatio,
        max_consecutive_card_box: maxConsecCard,
        floating_walk_violations: floatingViolations,
        text_actor_overlap_violations: overlapViolations,
        scene_replay_violations: replayViolations,
        camera_sway_violations: cameraSwayViolations,
        premature_reveal_violations: prematureRevealViolations,
        progress_bar_summary: progressBarInfo ? {
          ...progressBarInfo,
          visited_segments: visitedNavSegments.size,
        } : null,
        camera_summary: cameraSummary,
      };
    }

    return { beginFrame, recordActor, recordText, recordReveal, recordProgressBar, finalize };
  }

  global.DirectorStage = {
    VERSION: '8.1.0',
    buildSceneIndex,
    buildNavSegments,
    resolveTimeline,
    phraseTime,
    steadyCamera,
    evalCamera,
    createFrameAuditor,
    overlapArea,
  };
})(window);
