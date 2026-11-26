/* Lightweight reusable HTML5 Canvas visual-metaphor primitives for 1-Beat-1-Visual rendering.
 * Keeps screen text minimal and renders concrete action metaphors instead of PPT card walls.
 */
(function (global) {
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const easeOut = t => 1 - Math.pow(1 - clamp(t), 3);
  const easeInOut = t => { const u = clamp(t); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
  const easeOutExpo = t => { const u = clamp(t); return u >= 1 ? 1 : 1 - Math.pow(2, -10 * u); };
  const easeOutQuint = t => 1 - Math.pow(1 - clamp(t), 5);
  const easeInOutQuart = t => { const u = clamp(t); return u < 0.5 ? 8 * u * u * u * u : 1 - Math.pow(-2 * u + 2, 4) / 2; };
  const easeOutBack = (t, s = 1.65) => { const u = clamp(t) - 1; return 1 + (s + 1) * u * u * u + s * u * u; };
  const spring = (sec, dur = 0.36, bounce = 0.22) => {
    const u = clamp(sec / Math.max(0.05, dur));
    if (u <= 0) return 0;
    if (u >= 1) return 1;
    const freq = Math.PI * (1.25 + bounce * 2.2);
    return 1 - Math.exp(-7.2 * u) * Math.cos(freq * u);
  };
  const win = (sec, startSec, durSec) => clamp((sec - startSec) / Math.max(0.01, durSec));
  const lerp = (a, b, t) => a + (b - a) * t;

  function roundRect(ctx, x, y, w, h, r, fill, stroke, lw = 2, shadow = false) {
    ctx.save();
    if (shadow) {
      ctx.shadowColor = 'rgba(20, 30, 52, 0.10)';
      ctx.shadowBlur = 26;
      ctx.shadowOffsetY = 10;
    }
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    ctx.restore();
    if (stroke) {
      ctx.save();
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, r);
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lw;
      ctx.stroke();
      ctx.restore();
    }
  }

  function drawDocumentSheet(ctx, cx, cy, w, h, progress, pal, opts = {}) {
    const u = easeOut(progress);
    const fold = opts.foldSize ?? 34;
    ctx.save();
    ctx.translate(cx, cy + (1 - u) * 50);
    ctx.scale(0.92 + 0.08 * u, 0.92 + 0.08 * u);
    ctx.globalAlpha = u;
    ctx.shadowColor = 'rgba(20, 30, 52, 0.12)';
    ctx.shadowBlur = 24;
    ctx.shadowOffsetY = 8;
    const x = -w / 2, y = -h / 2;
    ctx.beginPath();
    ctx.moveTo(x + 14, y);
    ctx.lineTo(x + w - fold, y);
    ctx.lineTo(x + w, y + fold);
    ctx.lineTo(x + w, y + h - 14);
    ctx.quadraticCurveTo(x + w, y + h, x + w - 14, y + h);
    ctx.lineTo(x + 14, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - 14);
    ctx.lineTo(x, y + 14);
    ctx.quadraticCurveTo(x, y, x + 14, y);
    ctx.closePath();
    ctx.fillStyle = opts.fill || '#FFFFFF';
    ctx.fill();
    ctx.shadowColor = 'transparent';
    ctx.strokeStyle = opts.stroke || pal.stroke;
    ctx.lineWidth = 2.5;
    ctx.stroke();
    // Fold corner
    ctx.beginPath();
    ctx.moveTo(x + w - fold, y);
    ctx.lineTo(x + w - fold, y + fold);
    ctx.lineTo(x + w, y + fold);
    ctx.closePath();
    ctx.fillStyle = pal.soft;
    ctx.fill();
    ctx.stroke();

    // Abstract content bars + optional highlight sweep
    const rows = opts.rows ?? 5;
    const hlRow = opts.highlightRow ?? -1;
    const hlProg = clamp(opts.highlightProgress ?? 0);
    for (let i = 0; i < rows; i++) {
      const ry = y + 48 + i * ((h - 84) / rows);
      const rw = (w - 64) * (i === rows - 1 ? 0.62 : 0.85 - (i % 2) * 0.14);
      if (i === hlRow && hlProg > 0) {
        ctx.fillStyle = opts.highlightColor || '#FFE58F';
        ctx.fillRect(x + 28, ry - 6, rw * easeOut(hlProg), 26);
      }
      ctx.fillStyle = i === 0 ? pal.accent : (i === hlRow ? pal.ink : '#D6DCE8');
      ctx.beginPath();
      ctx.roundRect(x + 32, ry, rw, i === 0 ? 16 : 12, 6);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawStrikeThrough(ctx, x1, y1, x2, y2, progress, color = '#D9303E', lw = 7) {
    const u = easeOut(progress);
    if (u <= 0) return;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = lw;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(lerp(x1, x2, u), lerp(y1, y2, u));
    ctx.stroke();
    ctx.restore();
  }

  function draw3DWireCube(ctx, cx, cy, size, yaw, pitch, pal) {
    const s = size * 0.5;
    const verts = [
      [-s, -s, -s], [s, -s, -s], [s, s, -s], [-s, s, -s],
      [-s, -s, s], [s, -s, s], [s, s, s], [-s, s, s],
    ];
    const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
    const cpit = Math.cos(pitch), spit = Math.sin(pitch);
    const proj = verts.map(([vx, vy, vz]) => {
      const x1 = vx * cyaw - vz * syaw;
      const z1 = vx * syaw + vz * cyaw;
      const y2 = vy * cpit - z1 * spit;
      const z2 = vy * spit + z1 * cpit;
      const k = 620 / (620 - z2);
      return [cx + x1 * k, cy + y2 * k, z2];
    });
    const faces = [
      { idx: [0, 1, 2, 3], col: pal.soft },
      { idx: [4, 5, 6, 7], col: '#FFFFFF' },
      { idx: [0, 1, 5, 4], col: pal.surface },
      { idx: [2, 3, 7, 6], col: pal.canvas },
      { idx: [1, 2, 6, 5], col: '#E8EEF8' },
      { idx: [0, 3, 7, 4], col: '#F6ECE9' },
    ];
    faces.sort((a, b) => {
      const za = a.idx.reduce((acc, i) => acc + proj[i][2], 0);
      const zb = b.idx.reduce((acc, i) => acc + proj[i][2], 0);
      return za - zb;
    });
    ctx.save();
    faces.forEach(f => {
      ctx.beginPath();
      f.idx.forEach((vi, k) => (k === 0 ? ctx.moveTo(proj[vi][0], proj[vi][1]) : ctx.lineTo(proj[vi][0], proj[vi][1])));
      ctx.closePath();
      ctx.fillStyle = f.col;
      ctx.globalAlpha = 0.86;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = 3;
      ctx.lineJoin = 'round';
      ctx.stroke();
    });
    ctx.restore();
  }

  function drawAudioEnvelopeBars(ctx, cx, cy, count, width, maxH, color, phase, energy) {
    const gap = width / count;
    const bw = Math.max(8, gap * 0.58);
    const x0 = cx - width / 2;
    ctx.save();
    ctx.fillStyle = color;
    for (let i = 0; i < count; i++) {
      const norm = Math.abs(Math.sin(phase * 1.4 + i * 0.85) * 0.55 + Math.cos(phase * 2.3 - i * 0.45) * 0.45);
      const h = 10 + norm * maxH * clamp(energy, 0.1, 1);
      ctx.beginPath();
      ctx.roundRect(x0 + i * gap, cy - h / 2, bw, h, bw / 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawCleanCaption(ctx, text, y = 996) {
    const cleanTxt = String(text || '')
      .replace(/[，。！？；：、“”""''(),.!?;:\-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (!cleanTxt) return;
    ctx.save();
    ctx.font = '900 36px CourseHeavy, CourseHan, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(18, 24, 38, 0.92)';
    ctx.lineWidth = 9;
    ctx.strokeText(cleanTxt, 960, y);
    ctx.fillStyle = '#FFFFFF';
    ctx.fillText(cleanTxt, 960, y);
    ctx.restore();
  }

  function withCamera(ctx, cam, drawFn) {
    const cx = cam?.x || 0;
    const cy = cam?.y || 0;
    const zoom = cam?.zoom || 1;
    const rot = cam?.rot || 0;
    ctx.save();
    ctx.translate(960, 540);
    if (rot) ctx.rotate(rot);
    if (zoom !== 1) ctx.scale(zoom, zoom);
    ctx.translate(-960 - cx, -540 - cy);
    drawFn();
    ctx.restore();
  }

  function drawStudioBackdrop(ctx, pal, cam = {}, opts = {}) {
    ctx.fillStyle = pal.canvas;
    ctx.fillRect(0, 0, 1920, 1080);

    const px = -(cam.x || 0) * 0.25;
    const py = -(cam.y || 0) * 0.25;

    // Soft ambient radial glow (gives depth without dark clutter)
    ctx.save();
    const g1 = ctx.createRadialGradient(1560 + px * 0.6, 220 + py * 0.6, 40, 1560 + px * 0.6, 220 + py * 0.6, 680);
    g1.addColorStop(0, pal.soft);
    g1.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.globalAlpha = 0.72;
    ctx.fillStyle = g1;
    ctx.fillRect(0, 0, 1920, 1080);

    const g2 = ctx.createRadialGradient(320 + px * 0.4, 880 + py * 0.4, 30, 320 + px * 0.4, 880 + py * 0.4, 560);
    g2.addColorStop(0, pal.soft);
    g2.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.globalAlpha = 0.48;
    ctx.fillStyle = g2;
    ctx.fillRect(0, 0, 1920, 1080);
    ctx.restore();

    // Subtle parallax architectural dot grid
    if (opts.grid !== false) {
      const step = opts.gridStep || 64;
      const ox = ((px % step) + step) % step;
      const oy = ((py % step) + step) % step;
      ctx.save();
      ctx.fillStyle = pal.stroke;
      ctx.globalAlpha = opts.gridAlpha ?? 0.42;
      for (let gx = ox; gx < 1920; gx += step) {
        for (let gy = oy; gy < 1080; gy += step) {
          ctx.fillRect(gx - 1.5, gy - 1.5, 3, 3);
        }
      }
      ctx.restore();
    }
  }

  function drawFocusBrackets(ctx, x, y, w, h, color, size = 26, lw = 4, alpha = 1) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = lw;
    ctx.lineCap = 'round';
    ctx.beginPath();
    // TL
    ctx.moveTo(x, y + size); ctx.lineTo(x, y); ctx.lineTo(x + size, y);
    // TR
    ctx.moveTo(x + w - size, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + size);
    // BL
    ctx.moveTo(x, y + h - size); ctx.lineTo(x, y + h); ctx.lineTo(x + size, y + h);
    // BR
    ctx.moveTo(x + w - size, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - size);
    ctx.stroke();
    ctx.restore();
  }

  function drawSpeedLines(ctx, progress, dir = -1, color = '#D9303E', count = 9) {
    if (typeof progress !== 'number' || !Number.isFinite(progress) || progress > 2 || progress < -1) {
      throw new Error(
        `VisualMetaphors.drawSpeedLines: progress must be a normalized number in [0, 1] (got ${progress}). Signature: drawSpeedLines(ctx, progress, dir, color, count)`
      );
    }
    const p = clamp(progress);
    if (p <= 0 || p >= 1) return;
    const alpha = Math.sin(p * Math.PI) * 0.55;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineCap = 'round';
    ctx.globalAlpha = alpha;
    for (let i = 0; i < count; i++) {
      const y = 170 + i * 86 + ((i * 37) % 30);
      const len = 180 + (i % 3) * 140;
      const base = lerp(dir < 0 ? 1850 : 70, dir < 0 ? 80 : 1850, easeOutExpo(p));
      const x1 = base + ((i * 173) % 240 - 120);
      ctx.lineWidth = 3 + (i % 3) * 2;
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x1 - dir * len, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawRipple(ctx, cx, cy, r0, r1, progress, color, lw = 6) {
    const p = clamp(progress);
    if (p <= 0 || p >= 1) return;
    ctx.save();
    ctx.globalAlpha = (1 - p) * 0.85;
    ctx.beginPath();
    ctx.arc(cx, cy, lerp(r0, r1, easeOutExpo(p)), 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(1.5, lw * (1 - p * 0.7));
    ctx.stroke();
    ctx.restore();
  }

  function drawStampBadge(ctx, cx, cy, text, bg, fg, progress, angle = -0.07, fontSize = 24) {
    const p = clamp(progress);
    if (p <= 0) return;
    const s = lerp(1.55, 1.0, easeOutBack(p, 1.8));
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.scale(s, s);
    ctx.globalAlpha = clamp(p * 3.5);
    ctx.font = `900 ${fontSize}px CourseHeavy, CourseHan, sans-serif`;
    const tw = ctx.measureText(text).width;
    const w = tw + 44, h = fontSize + 24;
    roundRect(ctx, -w / 2, -h / 2, w, h, 14, bg, fg, 3.5, true);
    ctx.fillStyle = fg;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 0, 1);
    ctx.restore();
  }

  function drawRetailStoreBackdrop(ctx, x, y, w, h, pal, opts = {}) {
    const floorY = opts.floorY ?? (y + h - 102);
    const parallax = opts.parallax || 0;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 30);
    ctx.clip();

    // Warm architectural wall gradient
    const wg = ctx.createLinearGradient(x, y, x, floorY);
    wg.addColorStop(0, '#FBF9F4');
    wg.addColorStop(1, '#F2ECE1');
    ctx.fillStyle = wg;
    ctx.fillRect(x, y, w, floorY - y);

    // Ceiling recessed LED light strip
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(x + 120 + parallax * 0.2, y + 26, w - 240, 10);
    const lg = ctx.createLinearGradient(x, y + 36, x, y + 210);
    lg.addColorStop(0, 'rgba(255,255,255,0.65)');
    lg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = lg;
    ctx.fillRect(x + 90 + parallax * 0.2, y + 36, w - 180, 174);

    // Back wall oak vertical paneling + subtle brand wall lightboxes
    ctx.strokeStyle = 'rgba(180, 162, 134, 0.26)';
    ctx.lineWidth = 2;
    for (let px = x + 80 + (parallax * 0.35); px < x + w; px += 110) {
      ctx.beginPath(); ctx.moveTo(px, y + 48); ctx.lineTo(px, floorY); ctx.stroke();
    }

    // Two clean Apple-retail-style illuminated poster frames on back wall
    const frames = [
      { fx: x + 110 + parallax * 0.4, fw: 250, fh: 185, accent: pal.soft, stripe: pal.secondary },
      { fx: x + w - 360 + parallax * 0.4, fw: 250, fh: 185, accent: '#FCEAE8', stripe: pal.accent },
    ];
    frames.forEach(fr => {
      roundRect(ctx, fr.fx, y + 84, fr.fw, fr.fh, 14, '#FFFFFF', '#DFD6C5', 2, false);
      ctx.fillStyle = fr.accent;
      ctx.fillRect(fr.fx + 14, y + 98, fr.fw - 28, fr.fh - 28);
      // Minimal abstract device silhouette inside poster
      roundRect(ctx, fr.fx + fr.fw / 2 - 28, y + 126, 56, 98, 10, '#FFFFFF', fr.stripe, 2, false);
      ctx.fillStyle = fr.stripe;
      ctx.fillRect(fr.fx + fr.fw / 2 - 14, y + 138, 28, 14);
    });

    // Midground oak display table with minimalist device stands (behind characters)
    const tableX = x + w / 2 - 250 + parallax * 0.55;
    const tableY = floorY - 142;
    // Table shadow
    ctx.fillStyle = 'rgba(120, 102, 78, 0.10)';
    ctx.beginPath(); ctx.ellipse(tableX + 250, floorY - 2, 260, 16, 0, 0, Math.PI * 2); ctx.fill();
    // Table legs
    ctx.fillStyle = '#C9B292';
    ctx.fillRect(tableX + 22, tableY + 26, 16, 116);
    ctx.fillRect(tableX + 462, tableY + 26, 16, 116);
    // Table top
    roundRect(ctx, tableX, tableY, 500, 30, 8, '#E4CFAF', '#C6AC85', 2, false);
    // Tiny angled display phones on table
    for (let i = 0; i < 4; i++) {
      const dx = tableX + 74 + i * 110;
      ctx.fillStyle = '#334155';
      ctx.beginPath(); ctx.roundRect(dx, tableY - 26, 22, 26, 4); ctx.fill();
      ctx.fillStyle = '#94A3B8';
      ctx.fillRect(dx + 4, tableY - 22, 14, 16);
    }

    // Grounded floor band
    const fg = ctx.createLinearGradient(x, floorY, x, y + h);
    fg.addColorStop(0, '#E8E0D2');
    fg.addColorStop(1, '#DDD3C2');
    ctx.fillStyle = fg;
    ctx.fillRect(x, floorY, w, y + h - floorY);
    ctx.fillStyle = '#CFC3AE';
    ctx.fillRect(x, floorY, w, 4);

    ctx.restore();
    // Crisp outer stage border
    roundRect(ctx, x, y, w, h, 30, null, pal.stroke, 2.5, false);
  }

  function drawFScanOverlay(ctx, x, y, w, h, progress, pal) {
    const p = clamp(progress);
    ctx.save();
    roundRect(ctx, x, y, w, h, 24, '#FFFFFF', pal.secondary, 2.5, true);

    const pad = 34;
    const innerW = w - pad * 2;
    const topY = y + 72;
    const midY = y + 206;
    const row3Y = y + 306;
    const row4Y = y + 382;

    // 3 phase progress values for the F-shape scan
    const pTop = clamp(p / 0.36);           // Top horizontal bar of F
    const pMid = clamp((p - 0.36) / 0.34);  // Middle horizontal bar of F
    const pVert = clamp((p - 0.70) / 0.30); // Left vertical stem of F

    // Page wireframe content blocks (structured for F-pattern reading)
    // 1. Top Conclusion Bar (lights up as pTop sweeps)
    const topLit = easeOutExpo(pTop);
    roundRect(ctx, x + pad, topY, innerW, 74, 14, topLit > 0.08 ? pal.soft : '#F1F5F9', topLit > 0.08 ? pal.secondary : '#CBD5E1', 2.5, false);
    ctx.fillStyle = pal.secondary;
    ctx.font = '900 22px CourseHeavy, CourseHan, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText('结论前置 · 一眼看懂核心动作', x + pad + 20, topY + 37);

    // 2. Middle Action + Red Exception Row (lights up as pMid sweeps)
    const midLit = easeOutExpo(pMid);
    roundRect(ctx, x + pad, midY, innerW * 0.56, 62, 12, midLit > 0.08 ? '#EEF6FF' : '#F8FAFC', midLit > 0.08 ? pal.secondary : '#E2E8F0', 2, false);
    ctx.fillStyle = pal.ink;
    ctx.font = '900 20px CourseHeavy, CourseHan, sans-serif';
    ctx.fillText('动作词放行首', x + pad + 18, midY + 31);

    roundRect(ctx, x + pad + innerW * 0.60, midY, innerW * 0.40, 62, 12, midLit > 0.5 ? '#FFF1F2' : '#F8FAFC', midLit > 0.5 ? pal.accent : '#E2E8F0', 2.5, false);
    ctx.fillStyle = midLit > 0.5 ? pal.accent : '#94A3B8';
    ctx.fillText('⚠ 例外标红', x + pad + innerW * 0.60 + 16, midY + 31);

    // 3. Lower left-anchored scan items (light up as pVert sweeps down)
    const lowerRows = [
      { ry: row3Y, label: '01 先核对凭证', rw: innerW * 0.46, thr: 0.25 },
      { ry: row4Y, label: '02 再操作登记', rw: innerW * 0.40, thr: 0.72 },
    ];
    lowerRows.forEach(row => {
      const active = pVert >= row.thr;
      roundRect(ctx, x + pad, row.ry, row.rw, 52, 10, active ? pal.soft : '#F8FAFC', active ? pal.accent : '#E2E8F0', 2, false);
      ctx.fillStyle = active ? pal.ink : '#94A3B8';
      ctx.font = '900 18px CourseHeavy, CourseHan, sans-serif';
      ctx.fillText(row.label, x + pad + 16, row.ry + 26);
      // Muted right filler bars showing peripheral zone
      ctx.fillStyle = '#E2E8F0';
      ctx.beginPath(); ctx.roundRect(x + pad + row.rw + 18, row.ry + 16, innerW - row.rw - 24, 18, 6); ctx.fill();
    });

    // F-Scan Eye-Tracking Trajectory & Glowing Heatmap Beam (runs cleanly along gutter & underline tracks — zero text crossing!)
    const xL = x + pad - 10;
    const xR1 = x + pad + innerW - 14;
    const xR2 = x + pad + innerW * 0.90;
    const y1 = topY + 64;
    const y2 = midY + 54;
    const y3 = row4Y + 42;

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Draw accumulated translucent F-letter heat silhouette
    ctx.strokeStyle = 'rgba(217, 48, 62, 0.24)';
    ctx.lineWidth = 22;
    if (pTop > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y1);
      ctx.lineTo(lerp(xL, xR1, easeOutExpo(pTop)), y1);
      ctx.stroke();
    }
    if (pMid > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y2);
      ctx.lineTo(lerp(xL, xR2, easeOutExpo(pMid)), y2);
      ctx.stroke();
    }
    if (pVert > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y1);
      ctx.lineTo(xL, lerp(y1, y3, easeOutExpo(pVert)));
      ctx.stroke();
    }

    // Crisp core F-vector path
    ctx.strokeStyle = pal.accent;
    ctx.lineWidth = 5;
    if (pTop > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y1);
      ctx.lineTo(lerp(xL, xR1, easeOutExpo(pTop)), y1);
      ctx.stroke();
    }
    if (pMid > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y2);
      ctx.lineTo(lerp(xL, xR2, easeOutExpo(pMid)), y2);
      ctx.stroke();
    }
    if (pVert > 0) {
      ctx.beginPath();
      ctx.moveTo(xL, y1);
      ctx.lineTo(xL, lerp(y1, y3, easeOutExpo(pVert)));
      ctx.stroke();
    }

    // Active eye-tracking fixation dot + radial heatmap halo
    let bx = xL, by = y1;
    if (p < 0.36) {
      bx = lerp(xL, xR1, easeOutExpo(pTop)); by = y1;
    } else if (p < 0.70) {
      bx = lerp(xL, xR2, easeOutExpo(pMid)); by = y2;
    } else {
      bx = xL; by = lerp(y1, y3, easeOutExpo(pVert));
    }

    const halo = ctx.createRadialGradient(bx, by, 4, bx, by, 38);
    halo.addColorStop(0, 'rgba(217, 48, 62, 0.72)');
    halo.addColorStop(0.5, 'rgba(251, 191, 36, 0.38)');
    halo.addColorStop(1, 'rgba(217, 48, 62, 0)');
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(bx, by, 38, 0, Math.PI * 2); ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath(); ctx.arc(bx, by, 10, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = pal.accent;
    ctx.lineWidth = 4;
    ctx.stroke();

    // Fixation anchor dots at key F-nodes
    const nodes = [
      [xL, y1, pTop > 0.02],
      [xR1, y1, pTop > 0.92],
      [xL, y2, pMid > 0.02],
      [xR2, y2, pMid > 0.92],
      [xL, y3, pVert > 0.92],
    ];
    nodes.forEach(([nx, ny, show]) => {
      if (!show) return;
      ctx.fillStyle = pal.accent;
      ctx.beginPath(); ctx.arc(nx, ny, 7, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2.5;
      ctx.stroke();
    });

    ctx.restore();
  }

  function draw3DPhoneProp(ctx, cx, cy, scale, yaw, pitch, t, pal) {
    // True 3D perspective-projected iPhone 18 Pro (Glacier Blue — 71.9 x 150.0 x 8.75 mm)
    // Uses true 3D projected rounded rectangles & 3D projected lens circles so foreshortening is 100% physically accurate at every angle!
    const W = 136 * scale;
    const H = W * (150.0 / 71.9);
    const D = W * (8.75 / 71.9);
    const hw = W / 2, hh = H / 2, hd = D / 2;
    const R = 20 * scale;

    // Glacier-Blue official palette from workbench/device_models.py
    const finish = { edge: '#b3c4dd', plate: '#9faec4', glass: '#afbed4', dark: '#6d7f99' };

    const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
    const cpit = Math.cos(pitch), spit = Math.sin(pitch);

    const project = (vx, vy, vz) => {
      const x1 = vx * cyaw - vz * syaw;
      const z1 = vx * syaw + vz * cyaw;
      const y2 = vy * cpit - z1 * spit;
      const z2 = vy * spit + z1 * cpit;
      const k = 980 / (980 - z2);
      return [cx + x1 * k, cy + y2 * k, z2, k];
    };

    // Generate 2D rounded-rect perimeter points (in phone local plane)
    const roundedRectPts = (x0, y0, rw, rh, rad, segs = 5) => {
      const pts = [];
      const r = Math.min(rad, rw / 2, rh / 2);
      const corners = [
        [x0 + rw - r, y0 + r, -Math.PI / 2, 0],
        [x0 + rw - r, y0 + rh - r, 0, Math.PI / 2],
        [x0 + r, y0 + rh - r, Math.PI / 2, Math.PI],
        [x0 + r, y0 + r, Math.PI, Math.PI * 1.5],
      ];
      corners.forEach(([ccx, ccy, a0, a1]) => {
        for (let i = 0; i <= segs; i++) {
          const a = lerp(a0, a1, i / segs);
          pts.push([ccx + Math.cos(a) * r, ccy + Math.sin(a) * r]);
        }
      });
      return pts;
    };

    const drawPoly3 = (pts3, fill, stroke, lw = 2) => {
      const pts2 = pts3.map(([x, y, z]) => project(x, y, z));
      ctx.beginPath();
      pts2.forEach(([px, py], i) => (i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)));
      ctx.closePath();
      if (fill) { ctx.fillStyle = fill; ctx.fill(); }
      if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.lineJoin = 'round'; ctx.stroke(); }
      return pts2;
    };

    const drawCircle3 = (lx, ly, lz, rad, fill, stroke, lw = 2, segs = 22) => {
      const pts3 = [];
      for (let i = 0; i < segs; i++) {
        const a = (i / segs) * Math.PI * 2;
        pts3.push([lx + Math.cos(a) * rad, ly + Math.sin(a) * rad, lz]);
      }
      return drawPoly3(pts3, fill, stroke, lw);
    };

    // Determine which main face is visible (front normal = +Z, back normal = -Z)
    const frontNormalZ = cyaw * cpit;
    const showFront = frontNormalZ >= 0;

    ctx.save();
    // Soft grounded shadow
    ctx.fillStyle = 'rgba(20, 32, 58, 0.13)';
    ctx.beginPath();
    ctx.ellipse(cx, cy + hh + 38 * scale, W * 0.92, 20 * scale, 0, 0, Math.PI * 2);
    ctx.fill();

    // Technical CAD orbit ring (behind phone)
    ctx.strokeStyle = pal.secondary;
    ctx.globalAlpha = 0.25;
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 8]);
    ctx.beginPath();
    ctx.ellipse(cx, cy + 16 * scale, W * 1.48, 48 * scale, -0.10, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // 1. Extruded rounded titanium side band (sorted back-to-front by quad Z)
    const perim = roundedRectPts(-hw, -hh, W, H, R, 4);
    const quads = [];
    for (let i = 0; i < perim.length; i++) {
      const [x1, y1] = perim[i];
      const [x2, y2] = perim[(i + 1) % perim.length];
      const q3 = [[x1, y1, -hd], [x2, y2, -hd], [x2, y2, hd], [x1, y1, hd]];
      const zAvg = q3.reduce((s, p) => s + project(...p)[2], 0) / 4;
      // Subtle directional metallic shading along perimeter
      const nx = (y2 - y1), ny = -(x2 - x1);
      const len = Math.hypot(nx, ny) || 1;
      const shade = 0.5 + 0.5 * ((nx / len) * 0.65 - (ny / len) * 0.35);
      quads.push({ q3, zAvg, shade });
    }
    quads.sort((a, b) => a.zAvg - b.zAvg);
    quads.forEach(q => {
      const col = q.shade > 0.65 ? '#c6d4e8' : (q.shade > 0.35 ? finish.edge : finish.dark);
      drawPoly3(q.q3, col, finish.dark, 0.9);
    });

    // Side tactile buttons (Power & Camera Control on +X edge)
    if (syaw < 0.85) {
      drawPoly3([[hw + 1, -hh * 0.44, -hd * 0.45], [hw + 1, -hh * 0.22, -hd * 0.45], [hw + 1, -hh * 0.22, hd * 0.45], [hw + 1, -hh * 0.44, hd * 0.45]], finish.dark, null, 0);
      drawPoly3([[hw + 1, hh * 0.28, -hd * 0.45], [hw + 1, hh * 0.48, -hd * 0.45], [hw + 1, hh * 0.48, hd * 0.45], [hw + 1, hh * 0.28, hd * 0.45]], '#4b5a70', null, 0);
    }

    // 2. Render visible main face (Back = iPhone 18 Pro full-width plateau + 3 lenses + Flash + LiDAR; Front = OLED + Dynamic Island)
    if (!showFront) {
      // Back outer titanium rim & frosted glacier-blue glass
      const backRim = perim.map(([x, y]) => [x, y, -hd]);
      drawPoly3(backRim, finish.plate, finish.dark, 2.2);

      const glassInset = roundedRectPts(-hw + 7 * scale, -hh + 7 * scale, W - 14 * scale, H - 14 * scale, R - 4 * scale, 4).map(([x, y]) => [x, y, -hd - 0.5]);
      drawPoly3(glassInset, finish.glass, finish.edge, 1.4);

      // Subtle Apple-style lower back matte panel
      const lowerGlass = roundedRectPts(-hw + 10 * scale, -hh + H * 0.34, W - 20 * scale, H * 0.62, 14 * scale, 3).map(([x, y]) => [x, y, -hd - 0.8]);
      drawPoly3(lowerGlass, '#b7c6db', 'rgba(255,255,255,0.45)', 1.2);

      // Iconic iPhone 18 Pro Full-Width Horizontal Camera Plateau (extruded along -Z!)
      const pX = -hw + 5 * scale, pY = -hh + 5 * scale, pW = W - 10 * scale, pH = H * 0.295;
      const pDepth = 6.5 * scale;
      const pBase = roundedRectPts(pX, pY, pW, pH, 16 * scale, 3);
      // Plateau extruded rim
      for (let i = 0; i < pBase.length; i++) {
        const [x1, y1] = pBase[i], [x2, y2] = pBase[(i + 1) % pBase.length];
        drawPoly3([[x1, y1, -hd], [x2, y2, -hd], [x2, y2, -hd - pDepth], [x1, y1, -hd - pDepth]], finish.dark, null, 0);
      }
      // Plateau top face
      const pTop = pBase.map(([x, y]) => [x, y, -hd - pDepth]);
      drawPoly3(pTop, finish.edge, finish.dark, 1.8);

      // 3 Pro Lenses (exact device_models.py triangle on left of wide plateau, truly 3D perspective-projected!)
      const sx = W / 274, sy = H / 571.6;
      const lenses = [
        [-hw + 57 * sx, -hh + 55 * sy],
        [-hw + 57 * sx, -hh + 127 * sy],
        [-hw + 132 * sx, -hh + 91 * sy],
      ];
      const lensZ = -hd - pDepth - 4.2 * scale;
      lenses.forEach(([lx, ly]) => {
        // Metallic lens cylinder wall (short extrusion)
        drawCircle3(lx, ly, -hd - pDepth - 1.5 * scale, 29 * sx, finish.dark, null, 0, 20);
        // Outer metallic ring
        drawCircle3(lx, ly, lensZ, 28 * sx, finish.edge, finish.dark, 1.5, 20);
        // Dark sapphire glass
        drawCircle3(lx, ly, lensZ - 0.5, 23 * sx, '#0a101d', '#334155', 1.2, 20);
        // Deep blue optical coating
        drawCircle3(lx, ly, lensZ - 1.0, 12.5 * sx, '#172554', null, 0, 16);
        // Specular lens glint
        drawCircle3(lx - 4 * sx, ly - 4 * sy, lensZ - 1.3, 4.2 * sx, 'rgba(191, 219, 254, 0.72)', null, 0, 10);
      });

      // Right vertical column inside wide plateau: Flash + Mic + LiDAR (truly 3D projected!)
      const colX = hw - 44 * sx;
      drawCircle3(colX, -hh + 48 * sy, -hd - pDepth - 0.8, 11 * sx, '#f3f2e8', finish.dark, 1.2, 16);
      drawCircle3(colX, -hh + 92 * sy, -hd - pDepth - 0.8, 3.2 * sx, '#1e293b', null, 0, 10);
      drawCircle3(colX, -hh + 133 * sy, -hd - pDepth - 0.8, 11 * sx, '#090d16', '#475569', 1.2, 16);
    } else {
      // Front Face: Black OLED bezel + vibrant screen + diagonal specular sweep + Dynamic Island
      const frontRim = perim.map(([x, y]) => [x, y, hd]);
      drawPoly3(frontRim, '#0d1118', finish.edge, 2.2);

      const scrPts = roundedRectPts(-hw + 6 * scale, -hh + 6 * scale, W - 12 * scale, H - 12 * scale, R - 4 * scale, 4).map(([x, y]) => [x, y, hd + 0.5]);
      const scr2 = drawPoly3(scrPts, '#0f172a', '#334155', 1.2);

      ctx.save();
      ctx.beginPath();
      scr2.forEach(([px, py], i) => (i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)));
      ctx.closePath();
      ctx.clip();

      // Clean iOS 27 glacier-blue aurora gradient
      const sg = ctx.createLinearGradient(cx - W, cy - H, cx + W, cy + H);
      sg.addColorStop(0, '#1e3a8a');
      sg.addColorStop(0.5, '#3b82f6');
      sg.addColorStop(1, '#93c5fd');
      ctx.fillStyle = sg;
      ctx.fillRect(cx - W * 1.5, cy - H * 1.5, W * 3, H * 3);

      // Animated glass specular sweep
      const sweep = ((t * 0.8) % 1.8) - 0.4;
      const sx = cx + (sweep - 0.5) * W * 2.4;
      ctx.fillStyle = 'rgba(255,255,255,0.22)';
      ctx.beginPath();
      ctx.moveTo(sx, cy - H); ctx.lineTo(sx + 44 * scale, cy - H);
      ctx.lineTo(sx - 64 * scale, cy + H); ctx.lineTo(sx - 108 * scale, cy + H);
      ctx.closePath(); ctx.fill();
      ctx.restore();

      // Dynamic Island (truly 3D projected pill)
      const diPts = roundedRectPts(-22 * scale, -hh + 14 * scale, 44 * scale, 12 * scale, 6 * scale, 3).map(([x, y]) => [x, y, hd + 1.2]);
      drawPoly3(diPts, '#020617', null, 0);
    }
    ctx.restore();
  }

  function drawAmbientBackdrop(ctx, pal, cam = {}, tint = 'warm') {
    const g = ctx.createLinearGradient(0, 0, 1920, 1080);
    if (tint === 'warm') {
      g.addColorStop(0, '#FDFBF7'); g.addColorStop(0.5, '#F6F3EC'); g.addColorStop(1, '#EEF2F9');
    } else if (tint === 'contrast') {
      g.addColorStop(0, '#F3F5FA'); g.addColorStop(0.5, '#FBF8F4'); g.addColorStop(1, '#FDF2F2');
    } else {
      g.addColorStop(0, '#FBF9F5'); g.addColorStop(1, '#EBF0FA');
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 1920, 1080);
    const px = -(cam?.x || 0) * 0.3;
    ctx.save();
    [[340, 260, 320, 'rgba(37,76,153,0.06)'], [1560, 760, 380, 'rgba(217,138,43,0.08)'], [1420, 220, 240, 'rgba(74,127,224,0.06)']].forEach(([ox, oy, r, col]) => {
      const rg = ctx.createRadialGradient(ox + px, oy, 20, ox + px, oy, r);
      rg.addColorStop(0, col); rg.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(ox + px, oy, r, 0, Math.PI * 2); ctx.fill();
    });
    ctx.restore();
  }

  function drawCinematicAppleStore(ctx, pal, cam = {}, opts = {}) {
    const px = -(cam?.x || 0);
    const floorY = opts.floorY ?? 850;
    const coolMood = opts.coolMood || 0;
    const logoImg = opts.logoImg || null;

    const wallGrad = ctx.createLinearGradient(0, 0, 0, floorY + 10);
    wallGrad.addColorStop(0, '#FBF9F4');
    wallGrad.addColorStop(0.65, '#F4EEE4');
    wallGrad.addColorStop(1, '#EBE2D4');
    ctx.fillStyle = wallGrad;
    ctx.fillRect(-240, -120, 2400, floorY + 180);

    // Far Layer (0.22x parallax): Mall Glass Curtain Wall + Accessory Wall + Lightbox + Planter
    ctx.save();
    ctx.translate(px * 0.22, 0);
    const glassX = 1480, glassW = 540, glassY = 70, glassH = floorY - 70;
    const skyG = ctx.createLinearGradient(glassX, glassY, glassX + glassW, glassY + glassH);
    skyG.addColorStop(0, '#EAF2FB'); skyG.addColorStop(0.55, '#F5F8FC'); skyG.addColorStop(1, '#E5ECF5');
    ctx.fillStyle = skyG; ctx.fillRect(glassX, glassY, glassW, glassH);
    ctx.fillStyle = 'rgba(170, 186, 208, 0.22)';
    ctx.fillRect(glassX + 70, glassY + 40, 56, glassH - 40);
    ctx.fillRect(glassX + 270, glassY + 20, 72, glassH - 20);
    ctx.strokeStyle = '#C9D3DF'; ctx.lineWidth = 4;
    ctx.strokeRect(glassX, glassY, glassW, glassH);
    ctx.beginPath();
    ctx.moveTo(glassX + 210, glassY); ctx.lineTo(glassX + 210, glassY + glassH);
    ctx.moveTo(glassX + 420, glassY); ctx.lineTo(glassX + 420, glassY + glassH);
    ctx.stroke();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.beginPath();
    ctx.moveTo(glassX + 20, glassY); ctx.lineTo(glassX + 140, glassY);
    ctx.lineTo(glassX - 180, glassY + glassH); ctx.lineTo(glassX - 300, glassY + glassH);
    ctx.closePath(); ctx.fill();

    ctx.strokeStyle = 'rgba(176, 156, 128, 0.22)'; ctx.lineWidth = 2;
    for (let x = -120; x < 1470; x += 92) {
      ctx.beginPath(); ctx.moveTo(x, 60); ctx.lineTo(x, floorY); ctx.stroke();
    }

    // Left MagSafe / AirPods Accessory Wall
    roundRect(ctx, 70, 175, 360, 490, 16, '#F7F3EC', '#DED5C6', 2, false);
    for (let row = 0; row < 3; row++) {
      const sy = 285 + row * 124;
      ctx.fillStyle = '#D5BC99'; ctx.fillRect(96, sy, 308, 12);
      const colors = [['#3B6FD4', '#944A18', '#526074', '#C45B4D'], ['#E5E9F0', '#2E62BC', '#D9A76A', '#3B4252'], ['#FFFFFF', '#FFFFFF', '#E9EEF6', '#F4ECE1']][row];
      colors.forEach((col, i) => {
        const ix = 114 + i * 72;
        if (row < 2) {
          roundRect(ctx, ix, sy - 64, 44, 62, 10, col, 'rgba(34,38,48,0.18)', 1.5);
          ctx.strokeStyle = 'rgba(255,255,255,0.45)'; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(ix + 22, sy - 33, 10, 0, Math.PI * 2); ctx.stroke();
        } else {
          roundRect(ctx, ix - 4, sy - 54, 52, 52, 8, col, '#CFD6E0', 1.5);
        }
      });
    }

    // Center Flagship Illuminated Lightbox
    roundRect(ctx, 520, 155, 860, 310, 18, '#FFFFFF', '#DFD6C7', 2, true);
    const lbGrad = ctx.createLinearGradient(536, 171, 1364, 449);
    lbGrad.addColorStop(0, '#EEF4FC'); lbGrad.addColorStop(0.5, '#FBF9F5'); lbGrad.addColorStop(1, '#F5EFE6');
    ctx.fillStyle = lbGrad; ctx.fillRect(536, 171, 828, 278);
    ctx.strokeStyle = 'rgba(37, 76, 153, 0.14)'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(950, 310, 180, -0.4, 2.8); ctx.stroke();
    ctx.beginPath(); ctx.arc(950, 310, 120, 0.6, 3.8); ctx.stroke();
    if (logoImg && logoImg.complete && logoImg.naturalWidth) {
      const h = 54, w = h * (logoImg.naturalWidth / logoImg.naturalHeight);
      ctx.drawImage(logoImg, 950 - w / 2, 310 - h / 2, w, h);
    }

    // Ceramic Planter
    const potX = 1410, potY = floorY - 8;
    ctx.fillStyle = '#E6DFD3'; ctx.strokeStyle = '#C7BDAE'; ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(potX - 38, potY - 96); ctx.lineTo(potX + 38, potY - 96);
    ctx.lineTo(potX + 28, potY); ctx.lineTo(potX - 28, potY); ctx.closePath();
    ctx.fill(); ctx.stroke();
    ctx.strokeStyle = '#736555'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.moveTo(potX, potY - 96); ctx.lineTo(potX - 6, potY - 210); ctx.stroke();
    [[-26, -155, -0.5], [22, -165, 0.45], [-18, -205, -0.35], [16, -218, 0.3], [0, -238, 0]].forEach(([dx, dy, r]) => {
      ctx.save(); ctx.translate(potX + dx, potY + dy); ctx.rotate(r);
      ctx.fillStyle = '#7E8E85';
      ctx.beginPath(); ctx.ellipse(0, 0, 26, 14, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    });
    ctx.restore();

    // Ceiling Linear LED Cones (0.4x parallax)
    ctx.save();
    ctx.translate(px * 0.4, 0);
    [260, 860, 1460].forEach(lx => {
      ctx.fillStyle = '#FFFFFF'; ctx.fillRect(lx, 86, 360, 10);
      const cone = ctx.createLinearGradient(lx, 96, lx, 440);
      cone.addColorStop(0, 'rgba(255,255,255,0.48)'); cone.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = cone;
      ctx.beginPath();
      ctx.moveTo(lx, 96); ctx.lineTo(lx + 360, 96); ctx.lineTo(lx + 460, 440); ctx.lineTo(lx - 100, 440);
      ctx.closePath(); ctx.fill();
    });
    ctx.restore();

    // Terrazzo Floor
    const fg = ctx.createLinearGradient(0, floorY, 0, 1080);
    fg.addColorStop(0, '#E7DFD2'); fg.addColorStop(0.5, '#DED4C4'); fg.addColorStop(1, '#D3C7B4');
    ctx.fillStyle = fg; ctx.fillRect(-240, floorY, 2400, 300);
    ctx.fillStyle = '#C9BDA9'; ctx.fillRect(-240, floorY, 2400, 4);

    // Mid Layer (0.62x parallax): Perspective Oak Experience Table
    if (opts.showTable !== false) {
      ctx.save();
      ctx.translate(px * 0.62, 0);
      const tx = opts.tableX ?? 650, tw = opts.tableW ?? 620, ty = floorY - 154;
      ctx.fillStyle = 'rgba(84, 70, 52, 0.13)';
      ctx.beginPath(); ctx.ellipse(tx + tw / 2, floorY + 2, tw * 0.54, 18, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#C7AE8B';
      ctx.fillRect(tx + 28, ty + 30, 18, floorY - (ty + 30));
      ctx.fillRect(tx + tw - 46, ty + 30, 18, floorY - (ty + 30));
      ctx.fillStyle = '#EEDCC0';
      ctx.beginPath();
      ctx.moveTo(tx + 22, ty - 16); ctx.lineTo(tx + tw - 22, ty - 16);
      ctx.lineTo(tx + tw, ty + 4); ctx.lineTo(tx, ty + 4); ctx.closePath(); ctx.fill();
      roundRect(ctx, tx, ty, tw, 32, 6, '#DFC6A1', '#BFA37B', 2, false);
      const count = Math.max(2, Math.floor((tw - 100) / 140));
      for (let i = 0; i < count; i++) {
        const dx = tx + 80 + i * ((tw - 180) / Math.max(1, count - 1));
        ctx.fillStyle = '#CBD5E1'; ctx.fillRect(dx - 8, ty - 6, 36, 6);
        ctx.fillStyle = '#1E293B'; ctx.beginPath(); ctx.roundRect(dx, ty - 42, 24, 36, 4); ctx.fill();
        const scr = ctx.createLinearGradient(dx, ty - 40, dx + 20, ty - 10);
        scr.addColorStop(0, '#3B82F6'); scr.addColorStop(1, '#93C5FD');
        ctx.fillStyle = scr; ctx.fillRect(dx + 3, ty - 38, 18, 28);
        ctx.fillStyle = '#FFFFFF'; ctx.fillRect(dx + 30, ty - 14, 18, 10);
      }
      ctx.restore();
    }

    if (coolMood > 0.01) {
      ctx.fillStyle = `rgba(186, 206, 236, ${0.22 * coolMood})`;
      ctx.fillRect(-240, -120, 2400, 1320);
    }
  }

  function rectOverlapArea(a, b) {
    if (!a || !b) return 0;
    const x1 = Math.max(a.x, b.x);
    const y1 = Math.max(a.y, b.y);
    const x2 = Math.min(a.x + a.w, b.x + b.w);
    const y2 = Math.min(a.y + a.h, b.y + b.h);
    return (x2 > x1 && y2 > y1) ? (x2 - x1) * (y2 - y1) : 0;
  }

  /**
   * Shift a candidate box (bubble, danmaku pill, badge) out of all exclusion rects
   * (e.g., actor headRect/bodyRect, lightbox logo) while staying within safeBounds.
   */
  function placeAvoidingActors(rect, exclusionRects = [], safeBounds = null) {
    const safe = safeBounds || { minX: 56, maxX: 1864, minY: 102, maxY: 928 };
    const pad = 12;
    const clampRect = r => ({
      x: clamp(r.x, safe.minX, Math.max(safe.minX, safe.maxX - r.w)),
      y: clamp(r.y, safe.minY, Math.max(safe.minY, safe.maxY - r.h)),
      w: r.w,
      h: r.h,
    });
    const base = clampRect(rect);
    const obs = (exclusionRects || []).filter(Boolean);
    const totalOverlap = r => obs.reduce((acc, o) => acc + rectOverlapArea(r, o), 0);
    if (totalOverlap(base) <= 0) return base;

    const candidates = [base];
    for (const o of obs) {
      candidates.push(
        clampRect({ ...base, y: o.y - base.h - pad }),
        clampRect({ ...base, x: o.x - base.w - pad }),
        clampRect({ ...base, x: o.x + o.w + pad }),
        clampRect({ ...base, y: o.y + o.h + pad }),
      );
    }
    let best = base;
    let bestScore = Infinity;
    for (const c of candidates) {
      const ov = totalOverlap(c);
      const dist = Math.hypot(c.x - base.x, c.y - base.y);
      const score = ov * 1000 + dist;
      if (score < bestScore) {
        bestScore = score;
        best = c;
      }
    }
    return best;
  }

  function _wrapBubbleLines(ctx, text, maxW, fontSize, fontFamily) {
    ctx.font = `700 ${fontSize}px ${fontFamily}`;
    const tokens = String(text || '').match(/[A-Za-z0-9.+%×−]+|[\u4e00-\u9fa5][，。！？；：、]?|./g) || [''];
    const lines = [];
    let cur = '';
    for (const tok of tokens) {
      if (ctx.measureText(cur + tok).width > maxW && cur) { lines.push(cur.trim()); cur = tok; }
      else cur += tok;
    }
    if (cur) lines.push(cur.trim());
    return lines;
  }

  /**
   * Collision-safe speaker bubble anchored to CourseActorsCute.getActorBounds() output.
   * Returns final rendered rect { x, y, w, h } for DirectorStage frame auditing.
   */
  function drawSmartSpeakerBubble(ctx, actorBounds, text, opts = {}) {
    if (!text || !actorBounds) return null;
    const p = clamp(opts.progress ?? 1);
    if (p <= 0.01) return null;
    const fontFamily = opts.font || '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    const fontSize = opts.fontSize || 25;
    const maxW = opts.maxW || 500;
    const bg = opts.bg || '#FFFFFF';
    const border = opts.border || '#254C99';
    const fg = opts.fg || '#1E232E';
    const s = lerp(0.86, 1, easeOutBack(p, 1.4));

    ctx.save();
    const lines = _wrapBubbleLines(ctx, text, maxW - 48, fontSize, fontFamily);
    ctx.font = `700 ${fontSize}px ${fontFamily}`;
    const textW = Math.max(...lines.map(l => ctx.measureText(l).width));
    const bw = Math.max(180, textW + 48);
    const lh = fontSize * 1.38;
    const bh = lines.length * lh + 26;
    const speakerX = actorBounds.headX ?? actorBounds.rootX ?? 960;
    const headY = actorBounds.headY ?? (actorBounds.footY - 400);
    const safe = opts.safeBounds || { minX: opts.minX ?? 56, maxX: opts.maxX ?? 1864, minY: 102, maxY: 928 };
    const ideal = { x: speakerX - bw / 2, y: headY - bh - 26, w: bw, h: bh };
    const exclusions = (opts.exclusionRects || []).slice();
    if (actorBounds.headRect) exclusions.push(actorBounds.headRect);
    const placed = placeAvoidingActors(ideal, exclusions, safe);
    const tailX = clamp(speakerX, placed.x + 26, placed.x + placed.w - 26);

    ctx.translate(tailX, placed.y + placed.h + 12);
    ctx.scale(s, s);
    ctx.translate(-tailX, -(placed.y + placed.h + 12));
    ctx.globalAlpha = clamp(p * 3);
    roundRect(ctx, placed.x, placed.y, placed.w, placed.h, 20, bg, border, 3, true);
    ctx.beginPath();
    ctx.moveTo(tailX - 12, placed.y + placed.h - 2);
    ctx.lineTo(tailX, placed.y + placed.h + 14);
    ctx.lineTo(tailX + 12, placed.y + placed.h - 2);
    ctx.closePath();
    ctx.fillStyle = bg; ctx.fill();
    ctx.strokeStyle = border; ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(tailX - 12, placed.y + placed.h);
    ctx.lineTo(tailX, placed.y + placed.h + 14);
    ctx.lineTo(tailX + 12, placed.y + placed.h);
    ctx.stroke();
    ctx.fillStyle = fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    lines.forEach((ln, i) => ctx.fillText(ln, placed.x + placed.w / 2, placed.y + 13 + lh * (i + 0.5)));
    ctx.restore();
    return placed;
  }

  global.VisualMetaphors = {
    clamp, easeOut, easeInOut, easeOutExpo, easeOutQuint, easeInOutQuart, easeOutBack, spring, win, lerp,
    roundRect, drawDocumentSheet, drawStrikeThrough,
    draw3DWireCube, draw3DPhoneProp, drawAudioEnvelopeBars, drawCleanCaption,
    withCamera, drawStudioBackdrop, drawAmbientBackdrop, drawFocusBrackets, drawSpeedLines, drawRipple, drawStampBadge,
    drawRetailStoreBackdrop, drawCinematicAppleStore, drawFScanOverlay,
    rectOverlapArea, placeAvoidingActors, drawSmartSpeakerBubble,
  };
})(window);
