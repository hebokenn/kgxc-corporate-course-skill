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
      if (t >= lines[i].start && t <= lines[i].end) { beatIdx = i; break; }
      if (t >= lines[i].start) beatIdx = i;
    }
    const beat = lines[beatIdx];
    const scene = scenes[beatToScene[beatIdx]];
    const beatDur = Math.max(0.1, Number(beat.end) - Number(beat.start));
    const beatT = Math.max(0, t - Number(beat.start));
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
   * Evaluate a multi-keyframe cinematic camera track at `sceneT`.
   * Keyframe shape: { at: seconds, x, y, zoom, rot?, ease?, shakeAmp?, shakeFreq? }
   */
  function evalCamera(keyframes = [], sceneT = 0, globalT = sceneT) {
    if (!Array.isArray(keyframes) || keyframes.length === 0) {
      return { x: 0, y: 0, zoom: 1, rot: 0 };
    }
    const sorted = keyframes.slice().sort((a, b) => (a.at || 0) - (b.at || 0));
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
   * Runtime frame auditor: collects actor motion, text-actor collisions, layout mix,
   * and camera trajectory telemetry for verify_delivery.py --render-audit.
   */
  function createFrameAuditor(opts = {}) {
    const overlapTolerancePx2 = opts.overlapTolerancePx2 ?? 64;
    const floatingMovePx = opts.floatingMovePx ?? 10;
    const captionTopY = opts.captionTopY ?? 950;
    let cur = null;
    const prevActorsByScene = new Map();
    const floatingViolations = [];
    const overlapViolations = [];
    const replayViolations = [];
    const beatLayouts = new Map();
    const beatOrder = [];
    const sceneCameras = new Map();
    const lastSceneTByScene = new Map();
    let totalFrames = 0;

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

      // 2. Check text-actor overlap & caption-zone intrusion
      for (const txt of cur.texts) {
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
        const sc = sceneCameras.get(sceneId) || {
          scene_id: sceneId,
          layout_kind: lk,
          minX: cam.x || 0, maxX: cam.x || 0,
          minY: cam.y || 0, maxY: cam.y || 0,
          minZoom: cam.zoom ?? 1, maxZoom: cam.zoom ?? 1,
          frames: 0,
        };
        sc.minX = Math.min(sc.minX, cam.x || 0);
        sc.maxX = Math.max(sc.maxX, cam.x || 0);
        sc.minY = Math.min(sc.minY, cam.y || 0);
        sc.maxY = Math.max(sc.maxY, cam.y || 0);
        sc.minZoom = Math.min(sc.minZoom, cam.zoom ?? 1);
        sc.maxZoom = Math.max(sc.maxZoom, cam.zoom ?? 1);
        sc.frames++;
        sceneCameras.set(sceneId, sc);
      }

      cur = { frame: frameIndex, t, sceneId, beatId, layoutKind: lk, actors: [], texts: [] };
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
      const cameraSummary = Array.from(sceneCameras.values()).map(sc => ({
        scene_id: sc.scene_id,
        layout_kind: sc.layout_kind,
        pan_span_px: Number(Math.hypot(sc.maxX - sc.minX, sc.maxY - sc.minY).toFixed(1)),
        zoom_span: Number((sc.maxZoom - sc.minZoom).toFixed(4)),
        frames: sc.frames,
      }));
      return {
        schema: 'kgxc-director-audit/1',
        total_frames: totalFrames,
        total_beats: beatOrder.length,
        layout_kind_counts: layoutCounts,
        card_box_ratio: cardBoxRatio,
        max_consecutive_card_box: maxConsecCard,
        floating_walk_violations: floatingViolations,
        text_actor_overlap_violations: overlapViolations,
        scene_replay_violations: replayViolations,
        camera_summary: cameraSummary,
      };
    }

    return { beginFrame, recordActor, recordText, finalize };
  }

  global.DirectorStage = {
    VERSION: '8.0.0',
    buildSceneIndex,
    resolveTimeline,
    evalCamera,
    createFrameAuditor,
    overlapArea,
  };
})(window);
