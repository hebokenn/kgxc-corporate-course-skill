# 8.3.0 电影级导演引擎、强契约与交付硬门禁（唯一权威规范）

> **优先级声明**：本规范（`8.3.0`）是视频制作、人物演出、道具互动、信息留存、运镜、避让、分场景增量并行渲染与验收的**最高权威规范**。当 `references/` 目录下的历史 6.x / 7.0.0 文档（包括旧版 `workbench.json` 流程、旧版工作台脚本或 `59-streamlined-series-and-selfcheck.md`）与本规范冲突时，**一律以本规范为准**。

---

## 1. 小样即正片引擎原型（彻底消除“正片连小样都不如”）

1. **同一套引擎代码贯通小样与全片**：
   - 小样与完整系列正片**必须共用同一份基于 `DirectorStage` + `CourseActorsCute` + `VisualMetaphors` 的渲染内核与场景模块**。
   - **严禁**小样手写电影级逐镜演出、到全片时另起炉灶改写成简陋的“20+ 个白框填字模板分发器”。
   - 完整系列每集的表现丰富度、镜头调度与人物演出精度**只能高于或等于已确认小样，绝不允许降级**。
2. **三件核心前端库必须同时加载**：
   - `workbench/motion/actors_v3_cute.js`（`window.CourseActorsCute`）
   - `workbench/motion/visual_metaphors.js`（`window.VisualMetaphors`）
   - `workbench/motion/director_stage.js`（`window.DirectorStage`）

---

## 2. 强契约 API 速查表（错参即抛错，禁止凭记忆瞎传）

### 2.1 `window.CourseActorsCute`（人物引擎）

- **行走必传 `walkState`**（严禁传 `walkPhase` / `strideAmp`，8.0.0 会在运行期直接 `throw Error`）：
  ```js
  const ws = CA.computeMoodWalk(fromX, toX, sceneT, startT, 'brisk', 1.72);
  // 合法步速模式: 'stroll' | 'brisk' | 'rush' | 'cold_exit'
  const bounds = CA.paintExpressive(ctx, cfg, {
    x: ws.x, footY: 850, scale: 1.72, facing: 1,
    walkState: ws, // ← 必填！缺少则直接导致走路飘移并被审计拦截
    speaking: true, t, mood: 'happy', gesture: 'explain', blink,
  }, ACTOR_IMAGES);
  ```
- **唯一合法 `mood` 枚举**（传其它值直接抛错）：
  `happy` | `neutral` | `tense` | `confused` | `cold` | `anxious` | `sad` | `shy` | `sweat` | `worried`
- **唯一合法 `gesture` 枚举**（传其它值直接抛错）：
  `idle` | `welcome` | `point` | `wave` | `push_away` | `explain` | `present` | `worry` | `reject`
- **手持道具插槽 `heldProp` 与实时手部锚点（8.2.0 新增）**：
  - 合法 `heldProp` 类型：`phone` | `qr_card` | `card`（支持简写 `'phone'` 或对象 `{ type: 'phone', screenColor: '#6AA6FF', tilt: -0.18 }`；传未知类型直接抛错）。
  - `bounds = CA.paintExpressive(...)` 与 `CA.getActorBounds(st)` 实时返回世界坐标手部锚点 `bounds.frontHand` / `bounds.backHand`（用于对接 `VM.drawHandoverProp` 递交动画或 `VM.drawScreenInset` 屏幕特写引导线）。
- **实时人物包围盒与防重叠锚点**：
  `const bounds = CA.getActorBounds(st)`（`paint()` 与 `paintExpressive()` 也会直接返回 `bounds`）：
  - `bounds.headX / headY / mouthY / footY / rootX / frontHand / backHand`
  - `bounds.headRect`、`bounds.bodyRect`、`bounds.exclusionRect`

### 2.2 `window.VisualMetaphors`（空间避让、累进留存、道具互动与开放画布原语）

- **速度线精确签名**（传像素坐标如 `1300` 直接抛错）：
  `VM.drawSpeedLines(ctx, progress /* 0..1 */, dir /* -1 | 1 */, color, count)`
- **印章徽章精确签名**（切勿漏传前景色 `fg`，否则 `progress` 错位导致印章隐形）：
  `VM.drawStampBadge(ctx, cx, cy, text, bg, fg, progress, angle = -0.07, fontSize = 24)`
- **防重叠对话气泡**（强制替代手写坐标气泡）：
  `const rect = VM.drawSmartSpeakerBubble(ctx, speakerBounds, text, { progress, border, exclusionRects: [otherActorBounds.exclusionRect, logoLightboxRect] })`
- **弹幕/标签/花字自动避让人物**：
  `const safeRect = VM.placeAvoidingActors(candidateRect, [staffBounds.exclusionRect, custBounds.exclusionRect])`
  弹幕与浮标必须经过 `placeAvoidingActors` 计算后绘制，严禁压住人物头部、眼睛或背景 Logo。
- **累进指标轨与事件轨迹栈（8.2.0 新增，根治并列信息原地覆盖）**：
  - `const rail = VM.drawKpiRail(ctx, [{ id, label, value, tone, progress }, ...], PAL, { dir: 'column' | 'row' })`：并列展示 1–4 条诊断指标/得分率，新指标滑入高亮、旧指标温和退阶但完整保留，返回 `unionRect` 供避让。
  - `const stack = VM.drawCumulativeStack(ctx, [{ id, text, tone, progress }, ...], PAL, { maxVisible: 4 })`：同一场戏内并列失误链/事件点自上而下累进排开，禁止在同一坐标原地覆盖前一条。
- **物理递交道具与锚定屏幕特写（8.2.0 新增，根治实景空中悬浮无互动手机）**：
  - `VM.drawHandoverProp(ctx, staffBounds.frontHand, custBounds.frontHand, progress, { type: 'phone' | 'qr_card' })`：沿抛物线弧度在两人手部锚点间传递真机或企微卡。
  - `VM.drawScreenInset(ctx, anchorPt, boxRect, { mode: 'camera_live' | 'video_cinema' | 'search_loading' | 'qr_wechat', title, subtitle, progress })`：从手持手机或桌面展机拉出引导线弹出真机功能特写窗，讲完即收回。
  - `VM.draw3DPhoneProp(..., opts)` 新增可选 `{ showOrbit: false, showShadow: false }`；全息轨道悬浮 3D 手机**仅限封面与抽象隐喻舞台，严禁在 `cinematic_store` 实景里无互动悬空摆放**。
- **开放画布深度拆解原语（8.2.0 新增，根治每拍整卡快闪 PPT）**：
  - `VM.drawOpenChapterDots(ctx, tabs, activeIdx, PAL)`：轻量化节点时间线（替代厚重框式顶部导航）。
  - `VM.drawSculptureBar(ctx, cx, baseY, maxH, ratio, { fillTop, fillBot, valText, subText, progress })`：内置安全高度上限（默认 `<= 210px`），确保柱顶文字绝不撞压上方浮标。
  - `VM.drawFloatingTag(ctx, cx, cy, text, tone, progress, { pal, maxW })`：4–14 字短浮标，在 10–24 秒的主题拆解舞台上累进保留供学员从容阅读。
- **底部「分段章节进度条」（默认「融合进度胶囊」方案 A，高 `48px`，严禁退化为单根总进度条）**：
  ```js
  const navSegments = DS.buildNavSegments(data.lines, CHAPTER_NAV_SPECS, data.totalDuration);
  const navInfo = VM.drawSegmentedProgressBar(ctx, navSegments, t, PAL, { style: 'inline_pill' });
  if (AUDITOR && navInfo) AUDITOR.recordProgressBar(navInfo);
  ```
  按真实音频时长比例分配段宽（带最小宽度保底），自动区分已学（柔蓝底）、当前推进（主色描边 + 内部柔和渐变填充 + 底部蓝金细边推进，绝不切字）、未学（浅灰空胶囊）；单行无标点字幕置于 `y = 988` 独立留空。封面第 0 帧、片头与片尾不显示进度条。

### 2.3 `window.DirectorStage`（双层时间轴 + 发声锚点 + 停稳运镜 + 渲染遥测）

- **双层时间轴状态机 + 发声起点与词锚点（彻底消灭“动画重播”与“画面抢先旁白”）**：
  ```js
  const st = DS.resolveTimeline(data.lines, t);
  // st.sceneT: 当前连续场景内的单调递增时间 —— 跨 Beat 绝不归零！
  // st.speechT: 扣除 TTS 句首静音后的实际发声推进时间 —— 气泡/句首触发统一用 speechT！
  // DS.phraseTime(beat, '关键词', st.sceneStart): 计算句内指定词真正说出口的 sceneT 时刻，绝不提前抢跑！
  const formulaAt = DS.phraseTime(steps[4].line, '体验等于实际感知', st.sceneStart);
  ```
- **有目的运镜（到位即停稳 `hold` / `holdUntil`）与定机位总结板书（`steadyCamera`）**：
  ```js
  // 知识/数据场景：推进到位后用 holdUntil 锁稳画面方便阅读，禁止无停稳地左右往返摇摆
  const cam = DS.evalCamera([
    { at: 0.0, x: -24, y: 0, zoom: 0.98 },
    { at: 1.4, x: 0,   y: 0, zoom: 1.03, ease: 'easeOut', holdUntil: t5 },
  ], st.sceneT, t);
  // 一屏要点总结卡 / 讲义收尾页（layout_kind: 'summary_board'）：必须定机位零晃动
  const cam = DS.steadyCamera();
  ```
- **渲染遥测审计（生成 `render_audit.json`）**：
  ```js
  auditor.beginFrame(frameIdx, t, st, st.layoutKind, cam);
  const staffBounds = CA.paintExpressive(ctx, CAST.staff, staffState, ACTOR_IMAGES);
  auditor.recordActor('staff', staffBounds, staffState.walkState);
  auditor.recordReveal('summary_col1', st.sceneStart + col1At, sT >= col1At);
  auditor.recordMetricSlot('kpi_1', '发掘线索得分率', '< 10%', kpiRect); // 同槽位改写不同指标将被门禁 A 拦截
  auditor.recordProp('demo_phone', phoneRect, { attachment: 'hand', interactive: true }); // 实景无互动悬空将被拦截
  auditor.recordPanel('board_main', panelRect, { contentKey: beat.id }); // 巨幅卡片高频快闪翻页将被拦截
  const bubbleRect = VM.drawSmartSpeakerBubble(ctx, staffBounds, st.beat.speaker_bubble, { ... });
  if (bubbleRect) auditor.recordText('bubble', bubbleRect, 'bubble');
  // 渲染完毕调用 auditor.finalize() 写出 render_audit.json
  ```
- **分场景整帧切片、自动缓存失效与并行渲染（8.3.0 新增）**：
  - `DirectorStage.partitionSceneFrames(lines, totalDuration, fps = 24)`：按连续 `scene_id` 切出无缝无重叠的精确整帧区间 `[startFrame, endFrame)`，保证每帧归属与 `resolveTimeline(lines, f / fps)` 完全一致。
  - `DirectorStage.mergeFrameAudits(segmentAudits)`：按场景顺序无损合并各场景的 `auditor.finalize()` 遥测（含跨场景连续 `card_box` 计数、分段进度条已访问集合并集、全部 8 类违规数组与镜头汇总），产出与全量单次渲染 100% 等价的 `render_audit.json`。
  - 共享增量并行渲染引擎：`node SKILL_DIR/scripts/render_director_incremental.mjs --html <director.html> --audio-dir <audio> --out-dir <out> --tmp-dir <tmp> --meta-json <meta.json> [--intro <intro.mp4> --outro <outro.mp4>] [--workers 3]`。
    - 要求导演 HTML 将各场景绘制函数命名为 `function renderScXX(...)`（或使用 `// @scene:start <id>` … `// @scene:end <id>` 标记）并在 `SCENE_RENDERERS` 中映射，即可实现**改 1 个场景只重渲该场景、改共享库/公共函数/总时长则自动全量失效重渲**；多标签页并行渲染脏场景后以 `-f concat -c:v copy` 无损拼接并产出 `render_cache_report.json`。

---

## 3. 音画同步、禁止抢跑重播、定机位总结与去 PPT 化红线

1. **禁止机械切句克隆场景，严禁画面抢先旁白出现**：
   - `lines.json` 中每个 Beat 必须声明 `scene_id`、`layout_kind`（`cinematic_store` | `kinetic_metaphor` | `data_sculpture` | `summary_board` | `card_box`）和本句专属的 `visual_cue`（说明这句口播让画面产生什么新推进）。
   - 相邻两条 Beat 若共享同一个 `scene_id`（同一场戏/同一视觉舞台），**严禁把入场动画绑定到 `beatT` 导致跨句归零重播**；必须用 `sceneT` 承接连续动作与已完成状态。
   - **声画严禁抢跑（零剧透铁律）**：
     - 严禁在场景刚切入 `sT = 0` 时就把后续多个 Beat 才讲到的条目、三栏要点、多阶标题或剧透标签一口气全画出来——必须**讲到哪条、哪条才出现**；
     - 严禁对步骤切换写负偏移（如 `t3 - 0.1`、`t4 - 0.15`、`t4 - 0.3`）；
     - 对话气泡必须用 `st.speechT`（扣除 `tts_sync.py` 实测的 `speech_onset_sec` 句首静音，人开口再出泡）；句内中后段的核心公式、数字结论、结尾“谢谢大家”等必须绑定 `DS.phraseTime(beat, phrase, sceneStart)`，并在渲染器里调用 `auditor.recordReveal(id, targetAbsTime, visible)` 供门禁 A 硬检。
   - 对话气泡 `speaker_bubble` 必须与当前 Beat 的 `role` 和口播正文实时对齐，禁止旁白说话时挂角色气泡，禁止后一句仍残留上一句气泡。
2. **必须通过 `tts_sync.py --strict-beats` 合成配音**：
   - `tts_sync.py` 自动实测每条 WAV 的真实起声点 `speech_onset_sec / speech_start / speech_end` 与可选 `cue_words` 锚点，并从 `speech_start` 对齐生成单行无标点字幕。禁止另写临时脚本绕过校验。
3. **PPT 框体、反快闪翻页与定机位总结板书硬边界（8.2.0 升级）**：
   - `card_box`（白框/圆角卡片排字，仅限必要横向对比）占全集 Beat 数**严格 ≤ 25%**，且**严禁连续超过 2 个 Beat**。
   - **严禁把大面积整屏翻页卡片伪装成 `kinetic_metaphor` / `data_sculpture`**：案例深度拆解、要点对照段严禁用一个占屏 ≥ 28% 的大框每 2–4 秒清空重写文字（快闪 PPT，学员根本来不及看）。必须改用**开放画布累进舞台**（每个分析主题稳定停留 **10–24 秒**，以人物对照 + 立体雕塑/天平/温度计/峰终曲线 + `VM.drawFloatingTag` 累进保留）；门禁 A 通过 `rapid_card_flip_violations` 硬拦截连续 ≥ 3 次、单屏 `< 5s` 的大面积卡片快闪翻页。
   - `summary_board`（专用于一屏要点总结卡、讲义/练习收尾清单，占全集 Beat 数 **≤ 22%**）：不受 `card_box` 连续 2 Beat 上限约束，但**必须使用 `DS.steadyCamera()` 定机位零晃动**（`pan_span_px ≤ 12` 且 `zoom_span ≤ 0.025`），严禁把总结页伪装成 `kinetic_metaphor` 塞假运镜，画面推进必须由“讲到哪栏/哪条才逐项揭示”驱动。
   - 其余主教学段落必须使用实景纵深门店演绎（`cinematic_store`）、开放画布视觉隐喻动画（`kinetic_metaphor`）或立体数据雕塑/动态曲线（`data_sculpture`），且曲线、柱图、公式高亮必须有真实绘制演进。
4. **信息生命周期分级与实景道具物理接地铁律（8.2.0 新增）**：
   - **禁止并列信息原地覆盖**：只有「对话气泡（`bubble`）」和「同一物理量状态演变（如温度升高、天平倾斜）」允许原地替换。凡是同场内的**并列诊断得分率（如状态 `<30%` 与建联 `<10%`）或连续案例失误链**，必须使用 `VM.drawKpiRail` / `VM.drawCumulativeStack` 累进排开（旧条目温和退阶但完整可读），并通过 `auditor.recordMetricSlot()` / `recordText(..., 'kpi' | 'evidence')` 接受门禁 A `info_overwrite_violations` 校验。
   - **实景门店禁止无互动悬空道具**：`cinematic_store` 实景门店背景的展示桌本身已摆放接地真机，**平时对话/迎宾/口播阶段严禁在画面正中额外漂浮一台带轨道圈的 `draw3DPhoneProp`**。凡剧情需要手机/名片互动（现查资料、演示功能、递机试拍、递企微码），必须采用**三层接地法**：① `CourseActorsCute` 的 `heldProp` 直接握在手心；② `VM.drawHandoverProp(fromHand, toHand, p)` 沿弧线真实递交；③ `VM.drawScreenInset(anchorPt, boxRect, opts)` 拉出引导线展示真实功能界面并在讲完后收回。全息悬浮 3D 手机仅限封面及抽象隐喻舞台，门禁 A 通过 `floating_prop_violations` 硬拦截实景悬空道具。
5. **有目的电影运镜（防死镜，更防无意义晕船晃动）**：
   - `cinematic_store` / `kinetic_metaphor` / `data_sculpture`（≥ 2 秒）须具备有明确叙事目的的推拉摇移（`zoom_span ≥ 0.035` 或 `pan_span_px ≥ 26`）；
   - **阅读停稳红线**：知识与数据类场景（`kinetic_metaphor` / `data_sculpture`）到达落点后必须使用 `hold` / `holdUntil` 停稳便于学员阅读，**严禁全程无停顿漂移且反复左右/上下折返摇摆**（门禁 A 自动拦截 `camera_sway_violations`）；`shakeAmp` 仅允许在实景强戏剧冲击的短瞬间使用，禁止用于知识文字页。
6. **口播发音分离、构图安全距与局部热替换一致性**：
   - **发音与字幕分离（`tts_text` + 默认口语规整）**：`tts_sync.py` 默认将口播中的 `WOW` 规整为“哇哦”、将章节前导零 `第 01 节`–`第 09 节` 规整为“第一节”–“第九节”（不读“零一/零二”），同时保持字幕与画面原样；其他英文缩写、专有名词或多音字可直接为该 Beat 指定 `tts_text` 覆写发音（改动自动触发增量重配与缓存刷新）。
   - **同场景子幕非重叠交接与左边缘气泡安全距**：同一 `scene_id` 内从上一子幕切入下一子幕时，上一子幕的浮标/清单必须在下一子幕人物入场前完全淡出；靠近左侧站位的人物调用 `drawSmartSpeakerBubble` 时显式设置 `safeBounds.minX ≥ 100`（并计入 `zoom > 1` 放大裁边），确保气泡不贴边截断。
   - **曲线轴标净底衬与装饰粒子避字**：波形/折线横穿时间轴刻度时为刻度加柔和底衬，星芒等装饰粒子置于卡片或徽章两侧留白处，不飘压标题文字。
   - **片尾音乐软淡出与热替换一致性**：拼接品牌片尾（如 R5/R8 `outro-1080p24.mp4`）时对片尾音轨最后 `0.35s` 施加 `afade=t=out` 柔和淡出；若采用 `-c:v copy` 局部热替换重配音频，必须确保所有重配 WAV 严格锁在原渲染 `timeline.json` 槽位内，且 `.srt` 与 `timeline.json` 尾部漂移 ≤ 0.8s（门禁 A 自动校验）；一旦时长变动影响句内锚点或节奏，必须按最新 `audio_manifest.json` 同步重渲。

---

## 4. 不可跳过的双验收门禁（不通过禁止交付）

每支小样与每集正片在交付前，**必须同时通过以下两道门禁**：

### 门禁 A：自动化硬校验（零容忍，返回码必须为 0）
```bash
python3 SKILL_DIR/scripts/verify_delivery.py <final.mp4> \
  --srt <final.srt> \
  --cover <cover.png> \
  --timeline <timeline.json> \
  --render-audit <render_audit.json> \
  --strict-ppt-guard \
  --require-attached-pic
```
该命令会自动阻断：
- 任意 1 帧人物无接地步态滑行/飘移（`floating_walk_violations > 0`）
- 任意 1 处文字/气泡/弹幕与人物头身或字幕安全区重叠（`text_actor_overlap_violations > 0`）
- 任意 1 处跨 Beat 动画归零重播（画面像素回弹检测 + `scene_replay_violations > 0`）
- **任意 1 处画面元素或对话气泡抢先旁白起声点/词锚点超过 80ms（`premature_reveal_violations > 0`）**
- **任意 1 处并列指标或事件卡片在同一坐标原地覆盖前一条（`info_overwrite_violations > 0`）**
- **任意 1 处 `cinematic_store` 实景门店出现无接地、无手部绑定、无互动的悬空道具（`floating_prop_violations > 0`）**
- **任意 1 处 `kinetic_metaphor` / `data_sculpture` 场景内用巨幅卡片每 2–4 秒连续整屏翻页冒充动效（`rapid_card_flip_violations > 0`）**
- **任意 1 个总结板书/卡片页存在缩放平移晃动，或知识场景镜头全程漂移反复摇摆（`camera_sway_violations > 0`）**
- 靠微抖镜头欺骗静态帧检测（16×16 宏块结构差拦截，同时对定机位逐项揭示的 `summary_board` 精确放行局部变化）
- PPT 框体占比 > 25% 或连续 > 2 个 Beat，或 `summary_board` 占比 > 22%
- 动态场景缺少真实运镜
- 完整正片未接入分段章节进度条（退化为单根总进度条或未随时间轴切换分段）
- SRT 字幕与渲染 `timeline.json` 尾部漂移 > 0.8s
- 音画解码错误、48kHz AAC 异常、封面停超过第 0 帧、单行无标点字幕错误、尾音截断风险

### 门禁 B：真实成片抽帧目视核验（必须实际查看编码后图像）
交付前必须从**最终编码 MP4** 中抽取关键帧并用图像读取工具实际目视检查，至少覆盖：
1. **人物迈步中段帧**（确认双腿真实迈开弯曲、脚底着地阴影吻合、非僵腿飘移）；
2. **对话气泡 / 弹幕 / 花字高峰帧**（确认文字完全避开人脸、身体与背景 Logo，且气泡文案与当前底部字幕同步）；
3. **关键结论、并列指标与总结卡的“触发前 0.2s vs 触发后 0.4s”对照帧**（确认未讲到的条目/结论/结尾问候绝不提前剧透，并列得分率与案例失误链累进留存不原地覆盖，深度拆解开放画布无快闪 PPT 框感，一屏总结卡构图完全稳固不晃动）；
4. **实景门店道具接地与互动帧**（确认平时对话无悬空漂浮的孤立 3D 手机，演示/递机/查资料时手机真正在手或经引导线弹出特写屏）；
5. **首帧封面、第 1 帧片头、结尾总结卡与末句收尾**。

发现任何上述缺陷，必须在渲染端修完并重跑门禁 A + 门禁 B 后方可交付用户。
