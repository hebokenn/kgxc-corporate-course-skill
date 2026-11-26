/**
 * CourseActors v3 (Cute & Simple Editorial Style — Pro Zero-Foot-Slide Grounded Gait)
 * - Approved 3.3-head cute friendly proportions & authentic kg-original.png chest mark
 * - True world-space grounded footsteps (stance foot planted solidly on floor, ZERO foot-sliding!)
 * - Soft 2-segment knee bend + ankle/shoe pitch (heel-strike & toe-off)
 * - Natural 4-deg forward walk lean, counter-phase arm swing, subtle ponytail bounce
 */
window.CourseActorsCute = (() => {
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * clamp(t);
  const smooth = t => { const x = clamp(t); return x * x * (3 - 2 * x); };

  function solveIK2D(px, py, qx, qy, l1, l2, bendForward = 1) {
    const dx = qx - px, dy = qy - py;
    const rawD = Math.hypot(dx, dy) || 0.001;
    const d = clamp(rawD, Math.abs(l1 - l2) + 0.5, l1 + l2 - 0.3);
    const ux = dx / rawD, uy = dy / rawD;
    const along = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
    const h = Math.sqrt(Math.max(0, l1 * l1 - along * along));
    // bendForward = +1 bends knee toward +X (facing right in local space)
    return [px + ux * along + uy * h * bendForward, py + uy * along - ux * h * bendForward];
  }

  /**
   * Compute zero-foot-slide world-space foot positions for a cute Q-style walk segment.
   * - Compact stride & low ground-clearing lift suited for 3.3-head cute proportions
   * - Asymmetric 4-beat weight curve (Contact -> Down cushion -> Passing -> Up push)
   * - Each stance foot stays strictly planted on the floor (ZERO foot-sliding!)
   */
  function computeGroundedWalk(fromX, toX, t, startT, endT, scale = 1.72, stepLenWorld = 78) {
    const dir = Math.sign(toX - fromX) || 1;
    const dist = Math.abs(toX - fromX);
    const stanceSpread = 9.5 * scale;
    const effStep = Math.min(stepLenWorld, 31 * scale);

    if (t <= startT || dist < 1) {
      return {
        x: fromX, walking: false, walkWeight: 0, phase: 0, stepU: 0,
        bobOffset: 0, squashX: 1, squashY: 1, dir,
        feet: [
          { wx: fromX - dir * stanceSpread, lift: 0, pitch: 0 },
          { wx: fromX + dir * stanceSpread, lift: 0, pitch: 0 },
        ]
      };
    }
    if (t >= endT) {
      return {
        x: toX, walking: false, walkWeight: 0, phase: 0, stepU: 0,
        bobOffset: 0, squashX: 1, squashY: 1, dir,
        feet: [
          { wx: toX - dir * stanceSpread, lift: 0, pitch: 0 },
          { wx: toX + dir * stanceSpread, lift: 0, pitch: 0 },
        ]
      };
    }

    const dur = Math.max(0.01, endT - startT);
    const uTotal = clamp((t - startT) / dur);
    // Smooth acceleration/deceleration at start & end of walk
    const easeU = uTotal < 0.12 ? (uTotal * uTotal) / (2 * 0.12 * 0.88)
      : (uTotal > 0.88 ? 1 - ((1 - uTotal) * (1 - uTotal)) / (2 * 0.12 * 0.88) : (uTotal - 0.06) / 0.88);
    const curX = lerp(fromX, toX, easeU);

    const numSteps = Math.max(2, Math.round(dist / effStep));
    const stepDur = dur / numSteps;
    const localT = t - startT;
    const stepIdx = Math.min(numSteps - 1, Math.floor(localT / stepDur));
    const stepU = clamp((localT - stepIdx * stepDur) / stepDur);

    // Precompute planted world X targets for each step so stance foot NEVER slides!
    // Index 0 = trailing/far hip side (-dir * stanceSpread), Index 1 = leading/near hip side (+dir * stanceSpread)
    const pos = [fromX - dir * stanceSpread, fromX + dir * stanceSpread];
    const firstLeg = 1; // lead leg swings first symmetrically regardless of dir (+1 or -1)
    const steps = [];
    for (let i = 0; i < numSteps; i++) {
      const leg = (firstLeg + i) % 2;
      const landU = (i + 0.92) / numSteps;
      const landRoot = lerp(fromX, toX, clamp(landU));
      const targetX = (i >= numSteps - 2)
        ? toX + dir * (leg === 1 ? stanceSpread : -stanceSpread)
        : landRoot + dir * (effStep * 0.28);
      steps.push({ leg, from: pos[leg], to: targetX });
      pos[leg] = targetX;
    }

    // Reconstruct foot world positions at current stepIdx
    const feet = [
      { wx: fromX - dir * stanceSpread, lift: 0, pitch: 0 },
      { wx: fromX + dir * stanceSpread, lift: 0, pitch: 0 },
    ];
    for (let i = 0; i < stepIdx; i++) {
      feet[steps[i].leg] = { wx: steps[i].to, lift: 0, pitch: 0 };
    }
    const curStep = steps[stepIdx];
    // Swing phase: 0..0.14 toe push-off, 0.14..0.86 low cute swing arc, 0.86..1.0 heel settle
    let swingX = curStep.from, lift = 0, pitch = 0;
    if (stepU < 0.14) {
      const q = smooth(stepU / 0.14);
      swingX = curStep.from;
      lift = q * 1.4 * scale;
      pitch = dir * 0.16 * q; // toe push-off
    } else if (stepU < 0.86) {
      const q = (stepU - 0.14) / 0.72;
      const sq = smooth(q);
      swingX = lerp(curStep.from, curStep.to, sq);
      lift = Math.sin(Math.PI * q) * 5.2 * scale;
      pitch = dir * lerp(0.16, -0.10, sq); // low glide to gentle heel touch
    } else {
      const q = smooth((stepU - 0.86) / 0.14);
      swingX = curStep.to;
      lift = (1 - q) * 1.2 * scale;
      pitch = dir * -0.10 * (1 - q); // settle flat
    }
    feet[curStep.leg] = { wx: swingX, lift, pitch };

    // Asymmetric 4-beat vertical bounce (+ = Down cushion, - = Up push)
    let bobOffset = 0;
    if (stepU < 0.20) {
      bobOffset = lerp(0, 3.2, smooth(stepU / 0.20));
    } else if (stepU < 0.60) {
      bobOffset = lerp(3.2, -3.6, smooth((stepU - 0.20) / 0.40));
    } else {
      bobOffset = lerp(-3.6, 0, smooth((stepU - 0.60) / 0.40));
    }

    const walkWeight = Math.min(smooth(uTotal / 0.14), smooth((1 - uTotal) / 0.14));
    const sqAmt = (bobOffset >= 0 ? -bobOffset / 3.2 * 0.025 : (-bobOffset / 3.6) * 0.015) * walkWeight;
    const squashY = 1 + sqAmt;
    const squashX = 1 - sqAmt * 0.75;
    const phase = (stepIdx + stepU) * Math.PI;
    return { x: curX, walking: true, walkWeight, phase, stepU, bobOffset, squashX, squashY, dir, feet };
  }

  function pillLimb(ctx, x1, y1, x2, y2, r, fill, stroke = null) {
    ctx.save();
    ctx.lineCap = 'round';
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = r * 2 + 4.4;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    ctx.strokeStyle = fill;
    ctx.lineWidth = r * 2;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    ctx.restore();
  }

  function drawBentLeg(ctx, hx, hy, kx, ky, ax, ay, r, fill, stroke) {
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = r * 2 + 4.4;
      ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(kx, ky); ctx.lineTo(ax, ay); ctx.stroke();
    }
    ctx.strokeStyle = fill;
    ctx.lineWidth = r * 2;
    ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(kx, ky); ctx.lineTo(ax, ay); ctx.stroke();
    ctx.restore();
  }

  function drawCuteShoe(ctx, x, y, pitch, color = '#FFFFFF', sole = '#CBD5E1', outline = '#3A3438') {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(pitch);
    ctx.beginPath();
    ctx.moveTo(-14, -14);
    ctx.quadraticCurveTo(0, -18, 12, -12);
    ctx.quadraticCurveTo(25, -10, 26, -3);
    ctx.quadraticCurveTo(26, 0, 20, 0);
    ctx.lineTo(-12, 0);
    ctx.quadraticCurveTo(-18, 0, -16, -8);
    ctx.closePath();
    ctx.fillStyle = color; ctx.fill();
    ctx.strokeStyle = outline; ctx.lineWidth = 2.2; ctx.stroke();
    ctx.strokeStyle = sole; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(-13, -2.5); ctx.lineTo(22, -2.5); ctx.stroke();
    ctx.restore();
  }

  function drawCuteHead(ctx, cfg, st) {
    const {
      skin = '#FFE0CC', hairStyle = 'bun_pony', hairColor = '#3A2E31',
      hairLight = '#5C4B4F', glasses = false, glassesStyle = 'round', accessory = ''
    } = cfg;
    const { t = 0, speaking = false, mood = 'happy', blink = 0, hairBounce = 0, turn = 0 } = st;
    const ink = '#3A3438';
    const shift = turn * 9.0;
    const farEyeScale = lerp(1.0, 0.70, turn);

    ctx.save();

    // 1. Back hair with subtle secondary bounce during walk
    ctx.fillStyle = hairColor;
    ctx.strokeStyle = ink; ctx.lineWidth = 2.4;
    if (hairStyle === 'bun_pony') {
      ctx.save();
      ctx.translate(-34 - turn * 4, -4);
      ctx.rotate(hairBounce * 0.14);
      ctx.beginPath();
      ctx.ellipse(-10, 10, 17, 25, 0.35, 0, Math.PI * 2);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#4B7FD6';
      ctx.beginPath(); ctx.ellipse(0, -4, 6, 8, -0.4, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    } else if (hairStyle === 'high_pony') {
      ctx.save();
      ctx.translate(-34 - turn * 4, -22);
      ctx.rotate(hairBounce * 0.16 + 0.15);
      ctx.beginPath();
      ctx.moveTo(0, -2);
      ctx.bezierCurveTo(-18, -24, -44, -10, -34, 24);
      ctx.bezierCurveTo(-26, 36, -12, 32, -8, 12);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#E67A66';
      ctx.beginPath(); ctx.ellipse(-1, -1, 6.5, 5.5, -0.4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.restore();
    } else if (hairStyle === 'fluffy_bob') {
      ctx.beginPath(); ctx.roundRect(-48 + turn * 2, -32, 96 - turn * 6, 72, 34); ctx.fill(); ctx.stroke();
    } else if (hairStyle === 'long_straight') {
      ctx.beginPath();
      ctx.roundRect(-47 + turn * 4, -26, 92 - turn * 14, 68, 24);
      ctx.fill(); ctx.stroke();
    } else if (hairStyle === 'wavy_part') {
      ctx.beginPath();
      ctx.moveTo(-48 + turn * 4, -18);
      ctx.bezierCurveTo(-54 + turn * 4, 14, -49 + turn * 4, 34, -36 + turn * 4, 42);
      ctx.quadraticCurveTo(-20 + turn * 2, 46, -6, 40);
      ctx.lineTo(24 - turn * 10, 40);
      ctx.bezierCurveTo(44 - turn * 14, 36, 50 - turn * 14, 12, 44 - turn * 10, -18);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    }

    // 2. Cute little round ear (shifts slightly back/center as head turns toward walk dir)
    const earX = -41 + turn * 12;
    ctx.fillStyle = skin; ctx.strokeStyle = ink; ctx.lineWidth = 2.2;
    ctx.beginPath(); ctx.arc(earX, 4, 9.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

    // 3. Soft Chubby-Round Cute Face
    ctx.fillStyle = skin;
    ctx.beginPath(); ctx.ellipse(0, 0, 44 - turn * 3, 41, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = ink; ctx.lineWidth = 2.4; ctx.stroke();

    // Soft rosy peach cheeks
    ctx.fillStyle = 'rgba(248, 138, 132, 0.34)';
    ctx.beginPath(); ctx.ellipse(-10 + shift * 0.8, 12, 10, 6, 0, 0, Math.PI * 2); ctx.fill();
    if (turn < 0.85) {
      ctx.save();
      ctx.globalAlpha = 1 - turn * 0.75;
      ctx.beginPath(); ctx.ellipse(28 + shift * 0.45, 12, 8.5 * farEyeScale, 5.5, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }

    // 4. Sparkling Simple Cute Eyes
    const drawCuteEye = (ex, ey, sx = 1) => {
      ctx.save();
      ctx.translate(ex, ey);
      ctx.scale(sx, 1);
      if (mood === 'happy' && !speaking) {
        ctx.strokeStyle = ink; ctx.lineWidth = 3.2; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.arc(0, 3, 7, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
      } else if (blink > 0.5) {
        ctx.strokeStyle = ink; ctx.lineWidth = 3.0; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(-6, 0); ctx.lineTo(6, 0); ctx.stroke();
      } else {
        ctx.fillStyle = ink;
        ctx.beginPath(); ctx.ellipse(0, 0, 5.6, 6.6, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath(); ctx.arc(2.0, -2.2, 2.2, 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
    };
    const e1x = -2 + shift, e2x = 22 + shift * 0.70;
    drawCuteEye(e1x, 0, 1);
    drawCuteEye(e2x, 0, farEyeScale);

    // 5. Simple Expressive Tiny Brows
    ctx.strokeStyle = hairColor; ctx.lineWidth = 2.4; ctx.lineCap = 'round';
    ctx.beginPath();
    if (mood === 'tense' || mood === 'confused') {
      ctx.moveTo(e1x - 6, -14); ctx.lineTo(e1x + 5, -17);
      ctx.moveTo(e2x - 5, -17); ctx.lineTo(e2x + 6, -13);
    } else if (mood === 'cold') {
      ctx.moveTo(e1x - 6, -15); ctx.lineTo(e1x + 6, -15);
      ctx.moveTo(e2x - 6, -15); ctx.lineTo(e2x + 6, -15);
    } else {
      ctx.moveTo(e1x - 6, -15); ctx.quadraticCurveTo(e1x, -18, e1x + 6, -15);
      ctx.moveTo(e2x - 6, -15); ctx.quadraticCurveTo(e2x, -18, e2x + 6, -15);
    }
    ctx.stroke();

    // 6. Cute Minimalist Mouth
    const mx = 10 + shift * 0.95, my = 16;
    if (speaking) {
      const open = 4 + Math.abs(Math.sin(t * 14)) * 5.5;
      ctx.fillStyle = '#E06D6B';
      ctx.beginPath(); ctx.ellipse(mx, my, 6.8 * lerp(1, 0.88, turn), open, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = ink; ctx.lineWidth = 2.0; ctx.stroke();
    } else if (mood === 'happy') {
      ctx.strokeStyle = ink; ctx.lineWidth = 2.6; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.arc(mx, my - 3, 7, 0.2, Math.PI - 0.2); ctx.stroke();
    } else if (mood === 'tense' || mood === 'confused') {
      ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.arc(mx, my + 5, 5.5, Math.PI + 0.3, -0.3); ctx.stroke();
    } else {
      ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(mx - 5, my); ctx.quadraticCurveTo(mx, my + 2.5, mx + 5, my); ctx.stroke();
    }

    // 7. Cute Glasses (round or square)
    if (glasses) {
      ctx.save();
      ctx.strokeStyle = '#4A5160'; ctx.lineWidth = 2.2;
      ctx.fillStyle = 'rgba(225, 240, 255, 0.25)';
      if (glassesStyle === 'square') {
        ctx.beginPath(); ctx.roundRect(e1x - 12, -10, 23, 19, 5); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.roundRect(e2x - 11 * farEyeScale, -10, 22 * farEyeScale, 19, 5); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(e1x + 11, -1); ctx.lineTo(e2x - 11 * farEyeScale, -1);
        ctx.moveTo(e1x - 12, -2); ctx.lineTo(earX + 1, 2); ctx.stroke();
      } else {
        ctx.beginPath(); ctx.arc(e1x, 0, 12, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.ellipse(e2x, 0, 11.5 * farEyeScale, 11.5, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(e1x + 12, -1); ctx.lineTo(e2x - 11.5 * farEyeScale, -1);
        ctx.moveTo(e1x - 12, -2); ctx.lineTo(earX + 1, 2); ctx.stroke();
      }
      ctx.restore();
    }

    // 8. Soft Rounded Front Hair & Highlight
    ctx.save();
    ctx.scale(1 - turn * 0.07, 1);
    ctx.fillStyle = hairColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.4;
    if (hairStyle === 'bun_pony' || hairStyle === 'fluffy_bob' || hairStyle === 'high_pony' || hairStyle === 'long_straight') {
      ctx.beginPath();
      ctx.moveTo(-45, -2);
      ctx.bezierCurveTo(-48, -36, -24, -52, 6, -50);
      ctx.bezierCurveTo(34, -48, 48, -28, 43, -8);
      ctx.bezierCurveTo(32, -22, 16, -26, -6, -20);
      ctx.bezierCurveTo(-24, -15, -32, -4, -36, 8);
      ctx.bezierCurveTo(-42, 6, -44, 2, -45, -2);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else if (hairStyle === 'wavy_part') {
      ctx.beginPath();
      ctx.moveTo(-46, 2);
      ctx.bezierCurveTo(-49, -35, -24, -53, 5, -51);
      ctx.bezierCurveTo(34, -49, 49, -28, 45, -6);
      ctx.bezierCurveTo(36, -18, 22, -22, 10, -29);
      ctx.bezierCurveTo(-4, -20, -24, -14, -36, 10);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else if (hairStyle === 'manager_short' || hairStyle === 'silver_neat') {
      ctx.beginPath();
      ctx.moveTo(-44, -2);
      ctx.bezierCurveTo(-48, -36, -22, -53, 8, -51);
      ctx.bezierCurveTo(34, -49, 48, -30, 44, -12);
      ctx.bezierCurveTo(32, -24, 14, -24, -8, -26);
      ctx.bezierCurveTo(-24, -22, -32, -10, -37, 4);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      if (hairStyle === 'manager_short') {
        ctx.beginPath(); ctx.moveTo(-4, -49); ctx.quadraticCurveTo(4, -60, 14, -51); ctx.fill(); ctx.stroke();
      }
    } else if (hairStyle === 'side_part') {
      ctx.beginPath();
      ctx.moveTo(-45, -1);
      ctx.bezierCurveTo(-48, -37, -22, -53, 8, -51);
      ctx.bezierCurveTo(35, -49, 48, -28, 43, -10);
      ctx.bezierCurveTo(30, -24, 16, -30, -4, -24);
      ctx.bezierCurveTo(-20, -18, -32, -10, -38, 5);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else if (hairStyle === 'curly_short') {
      ctx.beginPath();
      ctx.moveTo(-45, 2);
      ctx.bezierCurveTo(-49, -20, -40, -40, -22, -46);
      ctx.quadraticCurveTo(-10, -56, 4, -51);
      ctx.quadraticCurveTo(22, -55, 34, -42);
      ctx.bezierCurveTo(46, -34, 48, -18, 43, -8);
      ctx.bezierCurveTo(32, -20, 20, -18, 8, -24);
      ctx.bezierCurveTo(-6, -16, -24, -18, -37, 6);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.moveTo(-45, 0);
      ctx.bezierCurveTo(-49, -36, -24, -52, 6, -51);
      ctx.bezierCurveTo(34, -50, 48, -30, 44, -10);
      ctx.bezierCurveTo(32, -22, 18, -20, 4, -28);
      ctx.bezierCurveTo(-12, -18, -28, -14, -38, 6);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    }

    ctx.strokeStyle = hairLight; ctx.lineWidth = 3.2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(-20 + shift * 0.4, -34); ctx.quadraticCurveTo(2 + shift * 0.4, -43, 22 + shift * 0.4, -33); ctx.stroke();

    if (accessory === 'hairclip') {
      ctx.fillStyle = '#F2B84B'; ctx.strokeStyle = ink; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.roundRect(-24 + shift * 0.3, -27, 13, 5, 2.5); ctx.fill(); ctx.stroke();
    }
    ctx.restore();

    if (accessory === 'earring') {
      ctx.fillStyle = '#F2B84B';
      ctx.beginPath(); ctx.arc(earX, 14, 3.6, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  function paint(ctx, cfg, st, images = {}) {
    const {
      x = 0, footY = 820, scale = 1.35, facing = 1,
      walkState = null, // from computeGroundedWalk (ZERO foot-sliding!)
      speaking = false, t = 0, mood = 'happy', gesture = 'idle', blink = 0
    } = st;
    const {
      role = 'staff', skin = '#FFE0CC',
      shirtColor = '#3E74C9', collarColor = '#6696DF', innerColor = '#D5E1EE',
      pantsColor = '#343C4C', shoeColor = '#FFFFFF', showKG = false
    } = cfg;
    const ink = '#3A3438';

    const rootX = walkState ? walkState.x : x;
    const wWeight = walkState ? walkState.walkWeight : 0;
    const phase = walkState ? walkState.phase : 0;
    const sqX = walkState?.squashX ?? 1;
    const sqY = walkState?.squashY ?? 1;
    // Plan B: smoothly turn body & head toward walking direction (0 = 3/4 front, ~0.92 = side walk), turn back on stop!
    const turn = 0.92 * wWeight;

    ctx.save();
    ctx.translate(rootX, footY);

    // Ground contact shadow
    ctx.fillStyle = 'rgba(58, 52, 56, 0.12)';
    ctx.beginPath(); ctx.ellipse(0, 0, lerp(44, 34, turn) * scale, 9 * scale, 0, 0, Math.PI * 2); ctx.fill();

    ctx.scale(facing * scale * sqX, scale * sqY);

    // Asymmetric 4-beat bounce (Contact -> Down cushion -> Passing/Up -> Contact)
    const walkBob = walkState?.bobOffset !== undefined
      ? walkState.bobOffset * wWeight
      : -Math.abs(Math.sin(phase)) * 4.5 * wWeight;
    const bob = walkBob + Math.sin(t * 2.8) * 1.3 * (1 - wWeight);
    const hipY = -78 + bob * 0.5;

    // Convert world-space planted feet into local facing-right coordinates (+ subtle depth lift on far leg)
    const localFeet = walkState ? walkState.feet.map((ft, idx) => ({
      lx: ((ft.wx - rootX) / scale) * facing,
      ly: -(ft.lift / scale) - (idx === 0 ? 1.6 * wWeight : 0),
      pitch: ft.pitch * facing
    })) : [
      { lx: -10, ly: 0, pitch: 0 },
      { lx: 10, ly: 0, pitch: 0 },
    ];

    // Hips converge toward side-profile centerline as body turns sideways during walk
    const hipHalf = lerp(8, 2, turn);

    // Continuous 2-segment IK on BOTH legs (no swing-threshold knee pop)
    const drawLeg = (hipX, foot, color) => {
      const ankleX = foot.lx - 2 * lerp(0.5, 1.0, turn);
      const ankleY = foot.ly - 10;
      const ikKnee = solveIK2D(hipX, hipY, ankleX, ankleY, 34.3, 34.3, 1);
      const straightKnee = [lerp(hipX, ankleX, 0.5), lerp(hipY, ankleY, 0.5)];
      const knee = [
        lerp(straightKnee[0], ikKnee[0], wWeight),
        lerp(straightKnee[1], ikKnee[1], wWeight)
      ];
      drawBentLeg(ctx, hipX, hipY, knee[0], knee[1], ankleX, ankleY, 9.4, color, ink);
      drawCuteShoe(ctx, foot.lx, foot.ly, foot.pitch, shoeColor, '#CBD5E1', ink);
    };

    // Draw far leg first, then near leg
    drawLeg(-hipHalf, localFeet[0], '#2A313E');
    drawLeg(hipHalf, localFeet[1], pantsColor);

    // Upper body with natural ~2.5-deg forward walk lean when turned sideways
    ctx.save();
    ctx.translate(0, hipY);
    ctx.rotate(wWeight * 0.045);
    ctx.translate(0, -hipY + bob * 0.5);

    const shY = -146;
    const strideDiff = clamp((localFeet[1].lx - localFeet[0].lx) / 20, -1, 1);
    const swingAmt = strideDiff * 14 * wWeight;

    const drawWalkArm = (sx, sy, hx, hy, armColor, bendWeight) => {
      const forwardAmt = clamp((hx - sx) / 14, 0, 1);
      const elbowLag = (1.5 + forwardAmt * 3.5) * bendWeight;
      const ex = lerp(sx, hx, 0.52) - elbowLag;
      const ey = lerp(sy, hy, 0.52) + 1.0 * bendWeight;
      drawBentLeg(ctx, sx, sy, ex, ey, hx, hy, 8.0, armColor, ink);
      if (role === 'staff' || role === 'manager') {
        pillLimb(ctx, sx, sy, lerp(sx, ex, 0.85), lerp(sy, ey, 0.85), 9.4, shirtColor, ink);
      }
      ctx.fillStyle = skin; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath(); ctx.arc(hx, hy, 8.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    };

    // Torso narrows smoothly to side-profile width when walking (60 -> 42)
    const torsoW = lerp(60, 42, turn);
    const torsoX = -torsoW / 2 + 2 * turn;
    const torsoR = lerp(22, 19, turn);

    const isUniform = (role === 'staff' || role === 'manager');
    const isShortSleeve = isUniform || Boolean(cfg.shortSleeve);
    const armFill = isShortSleeve ? skin : (role === 'cust_vest' ? innerColor : shirtColor);
    const sleeveFill = (role === 'cust_vest') ? innerColor : shirtColor;

    // Far arm (behind torso): when idle/walking it sits on far (+X) edge; when gesturing it stays on trailing (-X) side
    if (gesture === 'idle') {
      const farSx = lerp(22, 10, turn);
      const farHx = farSx + 2 + swingAmt;
      const farHy = shY + 55 - Math.abs(swingAmt) * 0.25;
      drawWalkArm(farSx, shY + 10, farHx, farHy, armFill, wWeight);
    } else {
      const bAx = -26 - swingAmt * 0.5, bAy = shY + 56;
      pillLimb(ctx, -22, shY + 8, bAx, bAy, 8.0, armFill, ink);
      if (isShortSleeve) {
        pillLimb(ctx, -22, shY + 8, lerp(-22, bAx, 0.45), lerp(shY + 8, bAy, 0.45), 9.4, sleeveFill, ink);
      }
    }

    // Back hoodie hood behind neck (drawn before torso & head)
    if (role === 'cust_hoodie') {
      ctx.fillStyle = shirtColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.ellipse(-6 - turn * 8, shY + 2, 19, 10, -0.2, 0, Math.PI * 2);
      ctx.fill(); ctx.stroke();
    }

    // Cute Rounded Torso (fill first, clip interior details inside torso silhouette, then crisp outline on top!)
    ctx.fillStyle = shirtColor;
    ctx.beginPath(); ctx.roundRect(torsoX, shY - 2, torsoW, 76, torsoR); ctx.fill();
    ctx.save();
    ctx.clip();

    if (role === 'cust_jacket') {
      const zipW = lerp(22, 12, turn);
      const zipX = lerp(-7, torsoX + torsoW - zipW, turn);
      ctx.fillStyle = innerColor;
      ctx.beginPath(); ctx.roundRect(zipX, shY - 2, zipW, 76, 4); ctx.fill();
      ctx.strokeStyle = ink; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(zipX, shY - 2); ctx.lineTo(zipX, shY + 74);
      if (turn < 0.7) { ctx.moveTo(zipX + zipW, shY - 2); ctx.lineTo(zipX + zipW, shY + 74); }
      ctx.stroke();
    } else if (role === 'cust_cardigan') {
      // V-neck cardigan with contrasting inner tee & buttons
      const cx = 4 + turn * 11;
      ctx.fillStyle = innerColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.moveTo(cx - 14, shY - 2); ctx.lineTo(cx, shY + 28); ctx.lineTo(cx + 14, shY - 2);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, shY + 28); ctx.lineTo(cx, shY + 74); ctx.stroke();
      ctx.fillStyle = ink;
      for (const by of [shY + 38, shY + 52, shY + 64]) {
        ctx.beginPath(); ctx.arc(cx + 4, by, 1.8, 0, Math.PI * 2); ctx.fill();
      }
    } else if (role === 'cust_vest') {
      // Layered vest over collared inner shirt (innerColor)
      const cx = 4 + turn * 11;
      ctx.fillStyle = innerColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.moveTo(cx - 15, shY - 2); ctx.lineTo(cx, shY + 22); ctx.lineTo(cx + 15, shY - 2);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.28)'; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.moveTo(torsoX, shY + 58); ctx.lineTo(torsoX + torsoW, shY + 58); ctx.stroke();
    } else if (role === 'cust_hoodie') {
      // Drawstrings & kangaroo pocket arc
      const cx = 4 + turn * 11;
      ctx.strokeStyle = innerColor || '#D5E1EE'; ctx.lineWidth = 2.6; ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(cx - 5, shY + 4); ctx.lineTo(cx - 6, shY + 24);
      ctx.moveTo(cx + 5, shY + 4); ctx.lineTo(cx + 6, shY + 22);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(58,52,56,0.38)'; ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.roundRect(cx - 18, shY + 40, 36, 26, 8);
      ctx.stroke();
    } else if (role === 'cust_shirt') {
      // Casual collared shirt + placket & buttons
      const cOff = turn * 10;
      ctx.fillStyle = collarColor || innerColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath(); ctx.moveTo(-13 + cOff, shY - 2); ctx.lineTo(4 + cOff, shY + 13); ctx.lineTo(-7 + cOff, shY + 19); ctx.lineTo(-20 + cOff, shY + 3); ctx.closePath(); ctx.fill(); ctx.stroke();
      if (turn < 0.7) {
        ctx.beginPath(); ctx.moveTo(18 + cOff * 0.5, shY - 2); ctx.lineTo(5 + cOff, shY + 13); ctx.lineTo(15 + cOff * 0.6, shY + 18); ctx.lineTo(24 + cOff * 0.3, shY + 3); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      const px = 4 + turn * 11;
      ctx.strokeStyle = 'rgba(58,52,56,0.35)'; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.moveTo(px, shY + 14); ctx.lineTo(px, shY + 72); ctx.stroke();
      ctx.fillStyle = ink;
      for (const by of [shY + 26, shY + 42, shY + 58]) {
        ctx.beginPath(); ctx.arc(px + 2.5, by, 1.6, 0, Math.PI * 2); ctx.fill();
      }
    } else if (isUniform) {
      const cOff = turn * 10;
      ctx.fillStyle = collarColor; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath(); ctx.moveTo(-14 + cOff, shY - 2); ctx.lineTo(4 + cOff, shY + 13); ctx.lineTo(-8 + cOff, shY + 19); ctx.lineTo(-21 + cOff, shY + 3); ctx.closePath(); ctx.fill(); ctx.stroke();
      if (turn < 0.7) {
        ctx.beginPath(); ctx.moveTo(19 + cOff * 0.5, shY - 2); ctx.lineTo(5 + cOff, shY + 13); ctx.lineTo(16 + cOff * 0.6, shY + 18); ctx.lineTo(25 + cOff * 0.3, shY + 3); ctx.closePath(); ctx.fill(); ctx.stroke();
      }

      if (showKG && images.kgOriginal && images.kgOriginal.complete) {
        ctx.save();
        ctx.translate(lerp(16, torsoX + torsoW - 10, turn), shY + 30);
        if (facing < 0) ctx.scale(-1, 1);
        const w = 18 * lerp(1, 0.78, turn), h = 18 * (images.kgOriginal.naturalHeight / images.kgOriginal.naturalWidth);
        ctx.drawImage(images.kgOriginal, -w / 2, -h / 2, w, h);
        ctx.restore();
      }
    } else {
      ctx.strokeStyle = 'rgba(255,255,255,0.45)'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(4 + turn * 8, shY + 1, 12, 0.2, Math.PI - 0.2); ctx.stroke();
    }
    ctx.restore();

    // Re-stroke torso outline on top so inner shirt / collar never breaks silhouette against light backgrounds!
    ctx.strokeStyle = ink; ctx.lineWidth = 2.4;
    ctx.beginPath(); ctx.roundRect(torsoX, shY - 2, torsoW, 76, torsoR); ctx.stroke();

    // Head (turns smoothly with torso, counter-rotates slightly so gaze stays level)
    ctx.save();
    ctx.translate(2 + turn * 2, shY - 40);
    ctx.rotate(-wWeight * 0.035);
    drawCuteHead(ctx, cfg, { t, speaking, mood, blink, hairBounce: wWeight * (bob * 0.25), turn });
    ctx.restore();

    // Near / Front Arm
    if (gesture === 'idle') {
      const nearSx = lerp(-22, -2, turn);
      const nearHx = nearSx - 2 - swingAmt;
      const nearHy = shY + 55 - Math.abs(swingAmt) * 0.25;
      drawWalkArm(nearSx, shY + 8, nearHx, nearHy, armFill, wWeight);
    } else {
      let fx = 24, fy = shY + 55;
      if (gesture === 'welcome') { fx = 66; fy = shY + 18 + Math.sin(t * 5) * 5; }
      else if (gesture === 'point') { fx = 72; fy = shY + 12; }
      else if (gesture === 'wave') { fx = 62; fy = shY - 8 + Math.sin(t * 7) * 7; }
      else if (gesture === 'push_away') { fx = 56; fy = shY + 16; }

      const gSx = lerp(22, 6, turn);
      pillLimb(ctx, gSx, shY + 10, fx, fy, 8.0, armFill, ink);
      if (isShortSleeve) {
        pillLimb(ctx, gSx, shY + 10, lerp(gSx, fx, 0.45), lerp(shY + 10, fy, 0.45), 9.4, sleeveFill, ink);
      }
      ctx.fillStyle = skin; ctx.strokeStyle = ink; ctx.lineWidth = 2.0;
      ctx.beginPath(); ctx.arc(fx, fy, 8.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }

    ctx.restore();
    ctx.restore();
  }

  // Ready-to-call cast library (7 staff/manager + 7 casual customers, zero background-color clash)
  const PRESETS = {
    // --- 店员 & 店长（统一蓝衣/黑衣 + 原版 KG 胸标） ---
    staff_bun: {
      id: 'staff_bun', category: 'staff', label: '蓝衣女店员（低丸子马尾）',
      role: 'staff', skin: '#FFE0CC', hairStyle: 'bun_pony', hairColor: '#3A2E31', hairLight: '#614E52',
      shirtColor: '#3B71C6', collarColor: '#6998E0', pantsColor: '#31394A', shoeColor: '#FFFFFF', showKG: true
    },
    staff_pony: {
      id: 'staff_pony', category: 'staff', label: '蓝衣女店员（高马尾活力款）',
      role: 'staff', skin: '#FFE3D1', hairStyle: 'high_pony', hairColor: '#4A342E', hairLight: '#73534A',
      accessory: 'hairclip', shirtColor: '#3B71C6', collarColor: '#6998E0', pantsColor: '#31394A', shoeColor: '#FFFFFF', showKG: true
    },
    staff_long: {
      id: 'staff_long', category: 'staff', label: '蓝衣女店员（披肩直发+方框眼镜）',
      role: 'staff', skin: '#FCDAC2', hairStyle: 'long_straight', hairColor: '#4E3730', hairLight: '#77564C',
      glasses: true, glassesStyle: 'square', shirtColor: '#3B71C6', collarColor: '#6998E0', pantsColor: '#31394A', shoeColor: '#FFFFFF', showKG: true
    },
    staff_male_part: {
      id: 'staff_male_part', category: 'staff', label: '蓝衣男店员（利落偏分短发）',
      role: 'staff', skin: '#F8D4B8', hairStyle: 'side_part', hairColor: '#2B2A2F', hairLight: '#52505A',
      shirtColor: '#3B71C6', collarColor: '#6998E0', pantsColor: '#2E3646', shoeColor: '#FFFFFF', showKG: true
    },
    staff_male_curl: {
      id: 'staff_male_curl', category: 'staff', label: '蓝衣男店员（微卷短发+圆框眼镜）',
      role: 'staff', skin: '#FFE0CC', hairStyle: 'curly_short', hairColor: '#3F322D', hairLight: '#68544C',
      glasses: true, glassesStyle: 'round', shirtColor: '#3B71C6', collarColor: '#6998E0', pantsColor: '#31394A', shoeColor: '#FFFFFF', showKG: true
    },
    manager_male: {
      id: 'manager_male', category: 'manager', label: '黑衣男店长（原版 KG）',
      role: 'manager', skin: '#FBD8C0', hairStyle: 'manager_short', hairColor: '#2B2A2F', hairLight: '#514F58',
      shirtColor: '#2C313C', collarColor: '#474F60', pantsColor: '#343B49', shoeColor: '#2E3440', showKG: true
    },
    manager_female: {
      id: 'manager_female', category: 'manager', label: '黑衣女店长（偏分干练款）',
      role: 'manager', skin: '#FFE0CC', hairStyle: 'wavy_part', hairColor: '#32292B', hairLight: '#594A4D',
      accessory: 'earring', shirtColor: '#2C313C', collarColor: '#474F60', pantsColor: '#343B49', shoeColor: '#2E3440', showKG: true
    },

    // --- 便装顾客（无 KG 标，不同发型与穿搭，严禁顺色） ---
    cust_male_glasses: {
      id: 'cust_male_glasses', category: 'customer', label: '男顾客（灰蓝外套+圆框眼镜）',
      role: 'cust_jacket', skin: '#FCDAC2', hairStyle: 'casual_short', hairColor: '#4D3B35', hairLight: '#745B53',
      glasses: true, glassesStyle: 'round', shirtColor: '#8392A6', innerColor: '#D5E1EE', pantsColor: '#3A4354', shoeColor: '#FFFFFF', showKG: false
    },
    cust_female_bob: {
      id: 'cust_female_bob', category: 'customer', label: '女顾客（橘棕针织+微卷短发）',
      role: 'cust_knit', skin: '#FFE3D1', hairStyle: 'fluffy_bob', hairColor: '#5E3D36', hairLight: '#875B52',
      accessory: 'earring', shirtColor: '#D48063', pantsColor: '#454B5C', shoeColor: '#FAF5EC', showKG: false
    },
    cust_female_wave: {
      id: 'cust_female_wave', category: 'customer', label: '女顾客（法式长卷发+豆沙紫开衫）',
      role: 'cust_cardigan', skin: '#FFE0CC', hairStyle: 'wavy_part', hairColor: '#4E362F', hairLight: '#78564B',
      accessory: 'earring', shirtColor: '#8A6B8E', innerColor: '#DDE4EE', pantsColor: '#3C4252', shoeColor: '#F3ECE2', showKG: false
    },
    cust_student_hoodie: {
      id: 'cust_student_hoodie', category: 'customer', label: '年轻男顾客（钴蓝卫衣+小卷发）',
      role: 'cust_hoodie', skin: '#F9D6BC', hairStyle: 'curly_short', hairColor: '#3A2E2B', hairLight: '#624E49',
      shirtColor: '#4F7AA6', innerColor: '#DCE6F2', pantsColor: '#3A404D', shoeColor: '#FFFFFF', showKG: false
    },
    cust_female_hoodie: {
      id: 'cust_female_hoodie', category: 'customer', label: '年轻女顾客（姜黄卫衣+高马尾）',
      role: 'cust_hoodie', skin: '#FFE4D4', hairStyle: 'high_pony', hairColor: '#47332C', hairLight: '#705247',
      shirtColor: '#D99B3C', innerColor: '#F7EBD5', pantsColor: '#434959', shoeColor: '#FFFFFF', showKG: false
    },
    cust_biz_shirt: {
      id: 'cust_biz_shirt', category: 'customer', label: '商务男顾客（雾霾蓝衬衫+方框眼镜）',
      role: 'cust_shirt', skin: '#F5CEB2', hairStyle: 'side_part', hairColor: '#2E2B2E', hairLight: '#544F54',
      glasses: true, glassesStyle: 'square', shirtColor: '#6B8CAE', collarColor: '#8CA8C7', innerColor: '#4D6B8B', pantsColor: '#313744', shoeColor: '#3D3735', showKG: false
    },
    cust_senior_vest: {
      id: 'cust_senior_vest', category: 'customer', label: '长辈顾客（暖咖针织马甲+银灰短发）',
      role: 'cust_vest', skin: '#F6CFB4', hairStyle: 'silver_neat', hairColor: '#8C919B', hairLight: '#B4B9C2',
      glasses: true, glassesStyle: 'round', shirtColor: '#8D6E5A', innerColor: '#B8C7D9', pantsColor: '#444650', shoeColor: '#4A433F', showKG: false
    }
  };

  function getPreset(id, overrides = {}) {
    const base = PRESETS[id];
    if (!base) throw new Error('未知角色预设: ' + id);
    return { ...base, ...overrides, showKG: base.category === 'customer' ? false : (overrides.showKG ?? base.showKG) };
  }

  function listPresets(category = null) {
    return Object.values(PRESETS).filter(p => !category || p.category === category);
  }

  /**
   * Emotion-driven variable-speed grounded walk presets (stroll / brisk / rush / cold_exit).
   * Automatically computes realistic duration from distance/speed, forward lean, and braking settle.
   */
  const GAIT_PRESETS = {
    stroll:    { speedPx: 145, stepLen: 68, leanDeg: 1.5, brakeSec: 0.15 },
    brisk:     { speedPx: 265, stepLen: 82, leanDeg: 4.5, brakeSec: 0.14 },
    rush:      { speedPx: 470, stepLen: 96, leanDeg: 9.5, brakeSec: 0.24 },
    cold_exit: { speedPx: 310, stepLen: 86, leanDeg: 5.5, brakeSec: 0.12 },
  };

  function computeMoodWalk(fromX, toX, t, startT, mode = 'stroll', scale = 1.72) {
    const preset = GAIT_PRESETS[mode] || GAIT_PRESETS.stroll;
    const dist = Math.abs(toX - fromX);
    const dur = Math.max(0.45, dist / preset.speedPx);
    const endT = startT + dur;
    const ws = computeGroundedWalk(fromX, toX, t, startT, endT, scale, preset.stepLen);
    const dir = Math.sign(toX - fromX) || 1;
    let leanRad = 0;
    if (t >= startT && t < endT) {
      const u = clamp((t - startT) / dur);
      const env = Math.min(u / 0.15, (1 - u) / 0.18, 1);
      leanRad = dir * (preset.leanDeg * Math.PI / 180) * env;
    } else if (t >= endT && t < endT + preset.brakeSec) {
      const bu = (t - endT) / preset.brakeSec;
      leanRad = -dir * (preset.leanDeg * 0.35 * Math.PI / 180) * Math.sin(bu * Math.PI);
    }
    return { ...ws, endT, dur, leanRad, speedMode: mode };
  }

  function paintExpressive(ctx, cfg, st, images = {}, extraLeanRad = 0) {
    const totalLean = extraLeanRad || (st.walkState && st.walkState.leanRad) || 0;
    ctx.save();
    if (Math.abs(totalLean) > 0.001) {
      ctx.translate(st.x, st.footY);
      ctx.rotate(totalLean);
      ctx.translate(-st.x, -st.footY);
    }
    paint(ctx, cfg, st, images);
    ctx.restore();
  }

  function paintPreset(ctx, id, st, images = {}, overrides = {}) {
    return paint(ctx, getPreset(id, overrides), st, images);
  }

  return {
    paint, paintExpressive, drawCuteHead, computeGroundedWalk,
    GAIT_PRESETS, computeMoodWalk, PRESETS, getPreset, listPresets, paintPreset,
  };
})();

/* Bridge legacy scene-engine.js window.CourseActors calls to CourseActorsCute. */
if (!window.CourseActors) {
  window.CourseActors = (() => {
    const Cute = window.CourseActorsCute;
    const lerp = (a, b, t) => a + (b - a) * t;
    function resolveConfig(actor = {}) {
      const presetId = actor.preset || actor.identity;
      const base = (presetId && Cute.PRESETS[presetId]) ? Cute.getPreset(presetId) : {};
      const roleMap = { store_staff: 'staff', store_manager: 'manager', coach: 'manager', customer: 'cust_jacket' };
      const role = actor.role || roleMap[actor.characterRole] || base.role || 'cust_jacket';
      const hairMap = { short: 'casual_short', bob: 'fluffy_bob', pony: 'high_pony', 'side-part': 'side_part', sidepart: 'side_part', mature: 'manager_short', spiky: 'curly_short' };
      const hairStyle = actor.hairStyle || hairMap[actor.hair] || base.hairStyle || 'casual_short';
      const isEmployee = ['store_staff', 'store_manager', 'coach', 'staff', 'manager'].includes(actor.characterRole || role);
      return {
        ...base,
        role,
        hairStyle,
        hairColor: actor.hairColor || base.hairColor || '#4D3B35',
        hairLight: actor.hairLight || base.hairLight || '#745B53',
        skin: actor.skin || base.skin || '#FFE0CC',
        glasses: actor.glasses ?? base.glasses ?? false,
        glassesStyle: actor.glassesStyle || base.glassesStyle || 'round',
        accessory: actor.accessory || base.accessory || '',
        shirtColor: actor.shirtColor || base.shirtColor || (role === 'staff' ? '#3B71C6' : role === 'manager' ? '#2C313C' : '#8392A6'),
        collarColor: actor.collarColor || base.collarColor || '#6998E0',
        innerColor: actor.innerColor || base.innerColor || '#D5E1EE',
        pantsColor: actor.pantsColor || base.pantsColor || '#343C4C',
        shoeColor: actor.shoeColor || base.shoeColor || '#FFFFFF',
        showKG: actor.characterRole === 'customer' ? false : (isEmployee && actor.characterRole !== 'coach' ? true : Boolean(base.showKG)),
      };
    }
    function sampleFacing(facingKeys = [], frame = 0) {
      if (!facingKeys.length) return 0;
      let prior = facingKeys[0];
      for (const k of facingKeys.slice(1)) {
        if (k.frame <= frame) { prior = k; continue; }
        const u = Math.max(0, Math.min(1, (frame - prior.frame) / Math.max(1, k.frame - prior.frame)));
        return prior.yaw + (k.yaw - prior.yaw) * u * u * (3 - 2 * u);
      }
      return prior.yaw;
    }
    function activeWalk(actor = {}, frame = 0, fps = 30, scale = 1) {
      for (const w of actor.walks || []) {
        if (frame >= w.startFrame && frame <= w.endFrame) {
          return Cute.computeGroundedWalk(w.fromX, w.toX, frame / fps, w.startFrame / fps, w.endFrame / fps, Math.max(0.5, scale));
        }
      }
      return null;
    }
    function worldXAt(node = {}, frame = 0, walkState = null) {
      const dx = node.editDx || 0;
      if (walkState) return walkState.x + dx;
      const a = node.vectorActor || {};
      const past = (a.walks || []).filter(item => item.endFrame < frame).at(-1);
      return (past ? past.toX : (node.x || 0)) + dx;
    }
    function pose(node = {}, frame = 0) {
      const a = node.vectorActor || {};
      const scale = node.scaleX || 1;
      const fps = 30;
      const walkState = activeWalk(a, frame, fps, scale);
      const x = worldXAt(node, frame, walkState);
      const floor = (node.y || 0) + (node.editDy || 0);
      const yaw = sampleFacing(a.facing, frame);
      const facing = yaw < -0.05 ? -1 : 1;
      const wWeight = walkState ? (walkState.walkWeight || 0) : 0;
      const turn = 0.92 * wWeight;
      const sqX = walkState?.squashX ?? 1;
      const sqY = walkState?.squashY ?? 1;
      const strideDiff = walkState
        ? Math.max(-1, Math.min(1, ((walkState.feet[1].wx - walkState.feet[0].wx) / scale) / 20))
        : 0;
      const swingAmt = strideDiff * 14 * wWeight;
      const bob = walkState ? (walkState.bobOffset || 0) : 0;
      const shY = -146 + bob * 0.5;
      const makeArm = (sx, sy, hx, hy) => {
        const fwd = Math.max(0, Math.min(1, (hx - sx) / 14));
        const lag = (1.5 + fwd * 3.5) * wWeight;
        const ex = lerp(sx, hx, 0.52) - lag;
        const ey = lerp(sy, hy, 0.52) + wWeight;
        return {
          S: [sx * facing * sqX, sy * sqY],
          K: [ex * facing * sqX, ey * sqY],
          Q: [hx * facing * sqX, hy * sqY],
        };
      };
      const nearSx = lerp(-22, -2, turn);
      const farSx = lerp(22, 10, turn);
      const armNear = makeArm(nearSx, shY + 8, nearSx - 2 - swingAmt, shY + 55 - Math.abs(swingAmt) * 0.25);
      const armFar = makeArm(farSx, shY + 10, farSx + 2 + swingAmt, shY + 55 - Math.abs(swingAmt) * 0.25);
      const armL = facing >= 0 ? armNear : armFar;
      const armR = facing >= 0 ? armFar : armNear;
      return {
        g: { x, y: floor, floor },
        scale,
        facing,
        yaw,
        walkState,
        shoulders: { left: { x: x + armL.S[0] * scale, y: floor + armL.S[1] * scale }, right: { x: x + armR.S[0] * scale, y: floor + armR.S[1] * scale } },
        hands: { left: { x: x + armL.Q[0] * scale, y: floor + armL.Q[1] * scale }, right: { x: x + armR.Q[0] * scale, y: floor + armR.Q[1] * scale } },
        arms: [armL, armR],
      };
    }
    function motionState(node = {}, frame = 0) {
      const a = node.vectorActor || {};
      const w = activeWalk(a, frame, 30, node.scaleX || 1);
      if (w) return { x: w.x };
      const past = (a.walks || []).filter(item => item.endFrame < frame).at(-1);
      return past ? { x: past.toX } : {};
    }
    function paint(ctx, node = {}, frame = 0, images = {}) {
      const a = node.vectorActor || {};
      const cfg = resolveConfig(a);
      const fps = 30;
      const p = pose(node, frame);
      const walkState = p.walkState;
      const yaw = p.yaw;
      const facing = p.facing;
      const scale = p.scale || 1;
      let mouthOpen = 0;
      for (const line of a.speech || []) {
        const idx = frame - line.startFrame;
        if (idx >= 0 && idx < (line.envelope || []).length) {
          mouthOpen = line.envelope[idx];
          break;
        }
      }
      const blink = (a.blinks || []).some(b => frame >= b[0] && frame <= b[2]) ? 1 : 0;
      const imgMap = { kgOriginal: (a.logoAsset && images[a.logoAsset]) || images.kgOriginal || null };
      Cute.paint(ctx, cfg, {
        x: 0, footY: 0, scale: 1, facing,
        walkState: walkState ? { ...walkState, x: 0, feet: walkState.feet.map(ft => ({ ...ft, wx: (ft.wx - (walkState.x || 0)) / scale, lift: ft.lift / scale })) } : null,
        speaking: mouthOpen > 0.15, t: frame / fps, mood: a.mood || 'happy', gesture: a.gesture || 'idle', blink,
      }, imgMap);
      const spread = 9.5 * Math.max(0.5, scale);
      const trailFoot = walkState ? walkState.feet[0] : null;
      const leadFoot = walkState ? walkState.feet[1] : null;
      const feet = walkState ? (walkState.dir >= 0 ? {
        left: { stance: trailFoot.lift === 0, soleX: trailFoot.wx },
        right: { stance: leadFoot.lift === 0, soleX: leadFoot.wx },
      } : {
        left: { stance: leadFoot.lift === 0, soleX: leadFoot.wx },
        right: { stance: trailFoot.lift === 0, soleX: trailFoot.wx },
      }) : {
        left: { stance: true, soleX: p.g.x - spread },
        right: { stance: true, soleX: p.g.x + spread },
      };
      return {
        maxBoneError: 0, maxReachError: 0, walking: Boolean(walkState && walkState.walking),
        mouthOpen, orientation: { torsoYaw: yaw, headYaw: yaw, hipYaw: yaw },
        shoulders: p.shoulders, hands: p.hands, feet,
        drawing: {
          minimumRelativeOpacity: 1,
          armLayers: [{ side: -1 }, { side: 1 }],
          faceFeaturesClipped: true,
        },
      };
    }
    function bounds() { return [{ x: -45, y: -230, width: 90, height: 235 }]; }
    function runtimeCalls() { return []; }
    function prepare() {}
    function paintProp() { return {}; }
    return { prepare, pose, motionState, paint, paintProp, bounds, runtimeCalls };
  })();
}
