# 8.0.0 电影级导演引擎、强契约与交付硬门禁（唯一权威规范）

> **优先级声明**：本规范（`8.0.0`）是视频制作、人物演出、运镜、避让与验收的**最高权威规范**。当 `references/` 目录下的历史 6.x / 7.0.0 文档（包括旧版 `workbench.json` 流程、旧版工作台脚本或 `59-streamlined-series-and-selfcheck.md`）与本规范冲突时，**一律以本规范为准**。

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
- **实时人物包围盒与防重叠锚点**：
  `const bounds = CA.getActorBounds(st)`（`paint()` 与 `paintExpressive()` 也会直接返回 `bounds`）：
  - `bounds.headX / headY / mouthY / footY / rootX`
  - `bounds.headRect`、`bounds.bodyRect`、`bounds.exclusionRect`

### 2.2 `window.VisualMetaphors`（空间避让与动效原语）

- **速度线精确签名**（传像素坐标如 `1300` 直接抛错）：
  `VM.drawSpeedLines(ctx, progress /* 0..1 */, dir /* -1 | 1 */, color, count)`
- **防重叠对话气泡**（强制替代手写坐标气泡）：
  `const rect = VM.drawSmartSpeakerBubble(ctx, speakerBounds, text, { progress, border, exclusionRects: [otherActorBounds.exclusionRect, logoLightboxRect] })`
- **弹幕/标签/花字自动避让人物**：
  `const safeRect = VM.placeAvoidingActors(candidateRect, [staffBounds.exclusionRect, custBounds.exclusionRect])`
  弹幕与浮标必须经过 `placeAvoidingActors` 计算后绘制，严禁压住人物头部、眼睛或背景 Logo。
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
  const bubbleRect = VM.drawSmartSpeakerBubble(ctx, staffBounds, st.beat.speaker_bubble, { ... });
  if (bubbleRect) auditor.recordText('bubble', bubbleRect, 'bubble');
  // 渲染完毕调用 auditor.finalize() 写出 render_audit.json
  ```

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
3. **PPT 框体与定机位总结板书硬边界**：
   - `card_box`（白框/圆角卡片排字，仅限必要横向对比）占全集 Beat 数**严格 ≤ 25%**，且**严禁连续超过 2 个 Beat**。
   - `summary_board`（专用于一屏要点总结卡、讲义/练习收尾清单，占全集 Beat 数 **≤ 22%**）：不受 `card_box` 连续 2 Beat 上限约束，但**必须使用 `DS.steadyCamera()` 定机位零晃动**（`pan_span_px ≤ 12` 且 `zoom_span ≤ 0.025`），严禁把总结页伪装成 `kinetic_metaphor` 塞假运镜，画面推进必须由“讲到哪栏/哪条才逐项揭示”驱动。
   - 其余主教学段落必须使用实景纵深门店演绎（`cinematic_store`）、开放画布视觉隐喻动画（`kinetic_metaphor`）或立体数据雕塑/动态曲线（`data_sculpture`），且曲线、柱图、公式高亮必须有真实绘制演进。
4. **有目的电影运镜（防死镜，更防无意义晕船晃动）**：
   - `cinematic_store` / `kinetic_metaphor` / `data_sculpture`（≥ 2 秒）须具备有明确叙事目的的推拉摇移（`zoom_span ≥ 0.035` 或 `pan_span_px ≥ 26`）；
   - **阅读停稳红线**：知识与数据类场景（`kinetic_metaphor` / `data_sculpture`）到达落点后必须使用 `hold` / `holdUntil` 停稳便于学员阅读，**严禁全程无停顿漂移且反复左右/上下折返摇摆**（门禁 A 自动拦截 `camera_sway_violations`）；`shakeAmp` 仅允许在实景强戏剧冲击的短瞬间使用，禁止用于知识文字页。
5. **口播发音分离、构图安全距与局部热替换一致性**：
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
3. **关键结论与总结卡的“触发前 0.2s vs 触发后 0.4s”对照帧**（确认未讲到的条目/结论/结尾问候绝不提前剧透，且一屏总结卡构图完全稳固不晃动）；
4. **首帧封面、第 1 帧片头、结尾总结卡与末句收尾**。

发现任何上述缺陷，必须在渲染端修完并重跑门禁 A + 门禁 B 后方可交付用户。
