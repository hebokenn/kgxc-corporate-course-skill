---
name: corporate-training-motion
description: 酷果星创课程设计与制作统一入口（8.0.0 电影级导演引擎与交付硬门禁）。先确认教学方案与逐字稿，再交付独立课件或按内容母版定调、全课分镜、三段有声小样、共用 DirectorStage 导演内核的完整系列视频与配套讲义/题库/作业。
---

# 酷果星创课程共创与制作（8.0.0）

以**你我对话 + 独立生成的富排版 HTML / MP4 审阅成品**为核心协作方式；视频制作统一采用 **8.0.0 电影级导演引擎（`DirectorStage` + `CourseActorsCute` + `VisualMetaphors`）** 与 **强制交付硬门禁**。

> **唯一权威规则**：先读 [8.0.0 电影级导演引擎、强契约与交付硬门禁](references/60-v8-cinematic-director-and-gates.md) 与同目录的 `../elearning-course-design/SKILL.md`。当历史 6.x / 7.0.0 参考文档（含旧版 `workbench.json` 流程）与 8.0.0 冲突时，**一律以 8.0.0 为准**。

## 1. 主流程总览（统一批次，小样即正片引擎原型）

1. **建档与恢复**：
   - 新课运行 `python3 SKILL_DIR/scripts/kgxc_course.py start COURSE --title 课名 --source 原件`，保留 `inputs/` 原件、建立规范目录并抽取本课浅色色板。
   - 恢复运行 `python3 SKILL_DIR/scripts/kgxc_course.py resume COURSE`；全程**不自动打开工作台网页**，按返回状态沿用有效确认。
   - **模型通道**：严格沿用当前宿主原生已选模型，禁止擅自切换供应商或收费来源。
2. **教学方案与大纲（统一规划）**：
   - 先读透原件（含图表/密集页），结合 [原件覆盖与现场讲解](../elearning-course-design/references/source-coverage-and-scope.md) 明确核心工作任务、学习目标、内容取舍与推荐讲法；有重要影响的选择用宿主结构化提问（最多 3 题）集中展示，再生成可审阅的大纲 HTML。
   - **授课立场**：代表酷果**总部团队发展中心**直接面向门店团队讲解，不在口播、字幕或封面自报部门；保留酷果星创开场问候语与完整收尾。
3. **统一逐字稿与自查**：
   - 按章节编号编写完整口播逐字稿（不含制作备注与避免词元说明），先按 [逐字稿输入与作者自检](../elearning-course-design/references/script-authoring-quality.md) 与 [学员上下文检查](../elearning-course-design/references/learner-context.md) 自查修精，生成原件覆盖对照报告 `workflow.py source-coverage COURSE --save report.json` 并连同逐字稿 HTML 呈交用户；确认后写入 `source-coverage --confirm` 与 `review --gate script`。
4. **独立分支：课件 或 视频（系列课统一批次）**：
   - **课件分支**：按用户要求交付 PPTX / DOCX / PDF / HTML 课件与逐字稿即可完成；独立课件页面不作为视频制作输入。
   - **视频分支（小样与正片必须共用同一套导演引擎）**：
     - 先用结构化提问确定**制作偏好**（顾客形象/重点花字/原库提示音效 `teaching-native-v1`/配音音色，写入 `project/production-preferences.json`）。
     - **内容母版三选一 + 全课最优分镜**：提炼核心视觉母版（每类 3 套实质不同方案定调），定调后全课逐段输出 1 套最优导演分镜，每个 Beat 必须声明 `scene_id`、`layout_kind` 与本句独立 `visual_cue`。
     - **全课抽 3 段有声小样**：使用正式 8.0.0 `DirectorStage` 渲染内核、多角色 Qwen3-TTS 配音（经 `tts_sync.py --strict-beats`）与 R5/R8 片头片尾生成 MP4，**通过 8.0.0 双验收门禁后**再交用户试听确认。
     - **共享导演引擎分集导出**：正片直接沿用并扩展小样验证通过的 `DirectorStage` 场景模块（**严禁另写降级版 PPT 模板分发器**），按章节分集导出 MP4 + SRT + 封面，每集均通过双验收门禁后连同讲义/题库/作业交付至 `~/Desktop/ai 制课/<课程名称>/`。

## 2. 视觉、人物、运镜与避让硬契约（纯代码驱动）

1. **三库齐载，错参即抛错**：
   - 渲染器必须同时加载 `workbench/motion/actors_v3_cute.js`（`CourseActorsCute`）、`workbench/motion/visual_metaphors.js`（`VisualMetaphors`）与 `workbench/motion/director_stage.js`（`DirectorStage`）。
   - **唯一人物引擎 `CourseActorsCute`**：禁止整张静态 PNG 人物。行走**必须传入 `walkState`（来自 `computeGroundedWalk` / `computeMoodWalk`）**，严禁传 `walkPhase`/`strideAmp`（8.0.0 会直接抛错阻断飘移滑行）。`mood` 与 `gesture` 仅接受规范枚举（详见 [60 号规范](references/60-v8-cinematic-director-and-gates.md)）。
   - **空间避让防重叠**：对话气泡必须调用 `VisualMetaphors.drawSmartSpeakerBubble(ctx, actorBounds, text, opts)`；弹幕、标签、花字必须经过 `VisualMetaphors.placeAvoidingActors(rect, exclusionRects)` 避开所有人物 `headRect/bodyRect` 与背景 Logo；严禁拍脑袋写死坐标压人脸。
   - **有目的电影运镜 + 定机位总结板书 + 去 PPT 红线**：实景与开放画布用 `DirectorStage.evalCamera(keyframes, sceneT, t)` 编排推拉摇移，知识板书到达落点必须用 `hold`/`holdUntil` 停稳，严禁无停稳地左右往返晃动或全局 ±12px 假抖动；**一屏要点总结卡、讲义收尾页统一使用 `layout_kind: "summary_board"` 与 `DS.steadyCamera()` 定机位零晃动**（靠逐栏/逐条渐进揭示推进，占比 ≤ 22%）；`card_box`（白框卡片）占全集 Beat 数**严格 ≤ 25%** 且不得连续超过 2 个 Beat；门店情景调用 `drawCinematicAppleStore` + `draw3DPhoneProp`，产品范围限定 Apple。
   - **支持联网检索合规素材**：可用宿主联网检索或 `scripts/web_asset_search.py` 缓存无水印开放许可素材至 `COURSE/project/assets/web/` 后接入。
   - 黑衣 KG 店长与蓝衣 KG 店员绑定 `assets/profiles/kgxc/kg-original.png` 胸标；Coach 保留 MyCoach；顾客穿便装且 `showKG: false`，严禁与背景顺色；同场人物有清晰外貌区分。
2. **精选明亮通透浅色色板**：从 `workbench/course-palettes.json` 中 `random_eligible: true` 的 16 套浅色色板（无绿色）随机抽取；深色仅用户明确指定时启用。
3. **品牌包装、分段进度导航与封面**：
   - 酷果片头/片尾使用 `scripts/bookends.py`（R5/R8 母版，`3.72s–4.34s` 浮现标题）；封面、顶栏与总结卡等比加载原版透明 `assets/brand/kgxc/kgxc-logo.png`；封面默认仅第 0 帧显示并写入 `attached_pic`。
   - **底部分段章节进度条（默认「融合进度胶囊」方案 A，高 `48px`，禁止单根总进度条）**：正片必须调用 `DirectorStage.buildNavSegments(lines, chapterSpecs)` 绑定真实音频章节边界，调用 `VisualMetaphors.drawSegmentedProgressBar(ctx, navSegments, t, PAL)` 渲染已学 / 当前推进 / 未学三态，并调用 `auditor.recordProgressBar(navInfo)` 接受门禁 A 硬检；封面、片头与片尾不显示进度条，单行字幕位于 `y = 988` 独立避让。

## 3. 双层时间轴、音画同步与防重播铁律

- **Scene vs Beat 双层状态机 + 严禁画面抢跑旁白铁律**：
  - 使用 `DirectorStage.resolveTimeline(lines, t)` 同时获取场景连续时间 `sceneT`、子句时间 `beatT` 与**扣除句首静音后的实际发声时间 `speechT`**。
  - 入场动画、人物走位、曲线生长绑定 `sceneT`（跨 Beat 绝不归零重播）；**禁止在 `sceneT = 0` 一次性剧透后续 Beat 才讲到的条目/结论/小标题，禁止负偏移抢跑（`t_k - 0.1` 等）**。
  - 对话气泡绑定 `st.speechT`，句内中后段核心词/结论/结尾问候必须用 `DS.phraseTime(beat, phrase, sceneStart)` 对齐实际说出口的时刻，并用 `auditor.recordReveal(id, targetAbsTime, visible)` 接受门禁 A 拦截。
- **强校验配音同步与自然口语发音分离**：
  - 使用 `scripts/tts_sync.py --strict-beats` 合成多角色 Qwen3-TTS 配音（建议每条 2.5–5 秒、≤ 26 字），自动实测每条 WAV 的真实起声点 `speech_onset_sec / speech_start` 与 `cue_words` 词锚点，并拦截：超长句、过密同屏字（> 35 字）、相邻 Beat 机械复制相同场景与参数、旁白挂角色气泡或气泡文案与当前口播错位、尾音截断。
  - **口播与字幕发音分离**：`tts_sync.py` 内建自然口语规整（默认将 `WOW` 读作“哇哦”、将 `第 01–09 节` 读作“第一–九节”不读前导 0，同时字幕与画面保持原规范写法），并支持逐 Beat `tts_text` 覆写多音字/英文缩写读音。
  - 单行无标点字幕从 `speech_start` 对齐实际开口时刻并独立避让主体与底部进度条，禁止段末自动插静音；拼接品牌片尾时在末段 `0.35s` 施加柔和淡出消除尾音峰值告警。

## 4. 不可跳过的双验收门禁（技术遥测 + 真实抽帧目视）

每支小样与每集正片交付前**必须全部通过**，不通过禁止汇报完成：

1. **门禁 A（自动化硬校验，返回码必须为 0）**：
   - 渲染器在运行期间通过 `DirectorStage.createFrameAuditor()` 写出 `render_audit.json`。
   - 运行：
     ```bash
     python3 SKILL_DIR/scripts/verify_delivery.py <video.mp4> --srt <sub.srt> --cover <cover.png> --timeline <timeline.json> --render-audit <render_audit.json> --strict-ppt-guard --require-attached-pic
     ```
   - 强拦截：走路飘移、文字压人物/压字幕区、同场景动画归零重播、**画面抢先旁白剧透（>80ms）**、**总结板书/知识页无意义镜头晃动漂移**、微抖动假动态 PPT、PPT 框体 > 25%、动态场景无真实运镜、SRT 与时间轴脱节、音画/封面/字幕/尾音缺陷。
2. **门禁 B（实际抽帧目视核验 + 关键揭示点前后帧核对）**：
   - 从最终编码 MP4 抽取并实际查看：人物迈步中段帧、对话气泡/弹幕高峰帧、非门店隐喻/数据帧、**关键结论与总结卡“触发前 0.2s vs 触发后 0.4s”对照帧（确认零抢跑、定机位不晃）**、首帧封面与第 1 帧片头；亲眼确认脚底落地、零压字、音画字幕气泡精准同步、构图稳健后方可交付。
3. **局部回改与过程保留**：用户微调某段时只重配/重渲受影响范围（若发音微调后的新 WAV 落入原 Beat 时间槽，可按原时间轴重混音并 `-c:v copy` 无损热替换视频流，数秒完成复验）；过程文件默认保留在课程工程内，正式成品交付至 `~/Desktop/ai 制课/<课程名称>/`。
4. **按需参考**：[花字与原库音效](references/46-flower-text-and-native-sfx.md)、[封面与收尾检查](references/37-cover-and-delivery-finish.md)、[情境表演与步态](references/48-situational-acting.md)、[阅读与信息节奏](references/45-reading-and-information-pacing.md)、[本地 Qwen3-TTS 配音](references/23-local-qwen3-voice.md)。
