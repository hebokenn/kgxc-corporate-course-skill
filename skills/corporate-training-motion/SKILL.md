---
name: corporate-training-motion
description: 酷果星创课程设计与制作统一入口（9.0.0 杂志级信息层级、定制信息图、视觉多样性蓝图、分场景增量并行渲染与交付硬门禁）。先确认教学方案与逐字稿，再交付独立课件或按内容母版定调、全集视觉多样性蓝图、三段有声小样、共用 DirectorStage 导演内核的完整系列视频与配套讲义/题库/作业。
---

# 酷果星创课程共创与制作（9.0.0）

以**你我对话 + 独立生成的富排版 HTML / MP4 审阅成品**为核心协作方式；视频制作统一采用 **9.0.0 电影级导演引擎（`DirectorStage` + `CourseActorsCute` + `VisualMetaphors` 杂志排版与定制信息图底座 + 全集视觉多样性蓝图 + 分场景增量并行渲染器）** 与 **强制交付硬门禁**。

> **唯一权威规则**：先读 [9.0.0 杂志级信息层级、定制信息图与反套路视觉多样性规范](references/70-v9-editorial-info-design-and-diversity.md)、[9.0.0 电影级导演引擎、强契约与交付硬门禁](references/60-v8-cinematic-director-and-gates.md) 与同目录的 `../elearning-course-design/SKILL.md`。当历史 6.x / 7.0.0 / 8.x 文档与 9.0.0 冲突时，**一律以 9.0.0 为准**。

## 1. 主流程总览（统一批次，小样即正片引擎原型）

1. **建档与恢复**：
   - 新课运行 `python3 SKILL_DIR/scripts/kgxc_course.py start COURSE --title 课名 --source 原件`，保留 `inputs/` 原件、建立规范目录并抽取本课浅色色板。
   - 恢复运行 `python3 SKILL_DIR/scripts/kgxc_course.py resume COURSE`；全程**不自动打开工作台网页**，按返回状态沿用有效确认。
   - **模型通道**：严格沿用当前宿主原生已选模型，禁止擅自切换供应商或收费来源。
2. **教学方案与大纲（统一规划）**：
   - 先读透原件（含图表/密集页），结合 [原件覆盖与现场讲解](../elearning-course-design/references/source-coverage-and-scope.md) 明确核心工作任务、学习目标、内容取舍与推荐讲法；有重要影响的选择用宿主结构化提问（最多 3 题）集中展示，再生成可审阅的大纲 HTML。
   - **授课立场**：代表酷果**总部团队发展中心**直接面向门店团队讲解，不在口播、字幕或封面自报部门；保留酷果星创开场问候语与完整收尾。
3. **统一逐字稿与自查**：
   - 按章节编号编写完整口播逐字稿（不含制作备注与避免词元说明），先按 [逐字稿输入与作者自检](../elearning-course-design/references/script-authoring-quality.md) 与 [学员上下文检查](../elearning-course-design/references/learner-context.md) 自查修精，确认标题短促说人话（建议 ≤ 14 字）、**隐藏全部小节标题连读正文仍无缝衔接**（视频中小节标题默认作画面过场页与底部进度条标签、不生硬照念）、**面向全员/新人时先讲白话概念与底层道理再给术语规则**，生成原件覆盖对照报告 `workflow.py source-coverage COURSE --save report.json` 并连同逐字稿 HTML 呈交用户；确认后写入 `source-coverage --confirm` 与 `review --gate script`。
4. **独立分支：课件 或 视频（系列课统一批次）**：
   - **课件分支**：按用户要求交付 PPTX / DOCX / PDF / HTML 课件与逐字稿即可完成；独立课件页面不作为视频制作输入。
   - **视频分支（小样与正片必须共用同一套导演引擎）**：
     - 先用结构化提问确定**制作偏好**（顾客形象/重点花字/原库提示音效 `teaching-native-v1`/配音音色，写入 `project/production-preferences.json`）。
     - **内容母版定调 + 全课最优分镜 + 全集视觉多样性蓝图（9.0.0 新增）**：提炼核心视觉母版，定调后全课逐段输出 1 套最优导演分镜，每个 Beat 必须声明 `scene_id`、`layout_kind` 与本句独立 `visual_cue`；**写渲染代码前必须产出 `visual-blueprint.json` 并通过 `scripts/check_visual_blueprint.py` 校验**（确保同屏零数据复述、单集同内置图表 ≤ 1 次、相邻非实景不克隆骨架、且含业务现场定制图形 `custom:*`）。
     - **全课抽 3 段有声小样**：使用正式 9.0.0 `DirectorStage` 渲染内核、多角色 Qwen3-TTS 配音（经 `tts_sync.py --strict-beats`）与 R5/R8 片头片尾生成 MP4，**通过 9.0.0 双验收门禁后**再交用户试听确认。
     - **共享导演引擎分集导出**：正片直接沿用并扩展小样验证通过的 `DirectorStage` 场景模块（**严禁另写降级版 PPT 模板分发器**），按章节分集导出 MP4 + SRT + 封面，每集均通过双验收门禁后连同讲义/题库/作业交付至 `~/Desktop/ai 制课/<课程名称>/`。

## 2. 视觉信息层级、反套路定制、人物与运镜硬契约（9.0.0 融合标准）

1. **杂志去框排版 + 定制信息图融合（Plan C，详见 70 号规范）**：
   - **唯一 L1 标题 + 12 栏网格对齐**：非实景信息页统一对齐 `VM.GRID_12`（`x = 120..1800`），每屏仅保留 **1 套 L1 观点大标题**（优先 `VM.drawQuietTopBar` + `VM.drawEditorialHeadline`），严禁双标题叠罗汉与无指向漂浮胶囊贴纸墙（单场景漂浮胶囊 ≤ 2）。
   - **三通道分工与零同屏数据复述（Mayer 冗余原则）**：旁白讲故事与因果，主图展比例与结构，文字仅作极简锚点；**严禁左图表与右 KPI 卡片重复列出同一组数字**——辅助区要么留白让主图居中放大，要么提供更高一维的洞察、人像体感翻译或归因结论（配 `VM.drawLeaderLine` / `VM.drawGroupingBracket`）。
   - **聚光灯降噪 + 骨架先行防剧透**：多条数据并列时，讲到哪项只高亮哪项，其余退阶至 `24%–35%` 透明；行动清单与分步总结在未讲到对应 Beat 前使用**虚线编号骨架槽**（`VM.drawEditorialChecklist`）保构图稳健且 100% 零剧透。
   - **基础能力 + 低套路可选原语 + 业务现场定制（反最小路径排列组合）**：流程与方法论高度复用，但每集必须按具体业务现场定制原生 Canvas/SVG 图形（`custom:*`），搭配可选低套路原语（`drawSpotlightHorizontalBars`、`drawPictogramGrid`、`drawJourneyFunnel`、`drawEditorialChecklist`）；**同集内置单一图表原语最多出现 1 次**，旧版 `drawSculptureBar` / `drawKpiRail` / `drawCumulativeStack` / `drawFloatingTag` 已降级为按需可选工具，不再作为强制套用模子。
2. **三库齐载，人物与实景道具物理接地**：
   - 渲染器同时加载 `workbench/motion/actors_v3_cute.js`（`CourseActorsCute`）、`workbench/motion/visual_metaphors.js`（`VisualMetaphors`）与 `workbench/motion/director_stage.js`（`DirectorStage`）。
   - **唯一人物引擎 `CourseActorsCute`**：禁止整张静态 PNG 人物。行走必须传入 `walkState`（来自 `computeGroundedWalk` / `computeMoodWalk`），严禁传 `walkPhase`/`strideAmp`；`mood`、`gesture` 与 `heldProp`（`phone`/`qr_card`/`card`）仅接受规范枚举；对话气泡必须调用 `VM.drawSmartSpeakerBubble` 避开人物与背景 Logo。
   - **有目的电影运镜 + 反快闪 PPT 红线 + 实景道具物理接地**：实景与开放画布用 `DirectorStage.evalCamera` 编排推拉摇移，知识板书到达落点必须用 `hold`/`holdUntil` 停稳；一屏要点总结卡、讲义收尾页统一使用 `layout_kind: "summary_board"` 与 `DS.steadyCamera()` 定机位零晃动（占比 ≤ 22%）；`card_box` 占比 **≤ 25%** 且连续 ≤ 2 句，严禁大面积卡片每 2–4 秒快闪翻页；`cinematic_store` 实景门店禁止无互动悬空 `draw3DPhoneProp`，产品范围限定 Apple。
   - **支持联网检索合规素材**：可用宿主联网检索或 `scripts/web_asset_search.py` 缓存无水印开放许可素材至 `COURSE/project/assets/web/` 后接入。
   - 黑衣 KG 店长与蓝衣 KG 店员绑定 `assets/profiles/kgxc/kg-original.png` 胸标；Coach 保留 MyCoach；顾客穿便装且 `showKG: false`，严禁与背景顺色；同场人物有清晰外貌区分。
3. **精选明亮通透浅色色板、品牌包装与分段进度导航**：
   - 从 `workbench/course-palettes.json` 中 `random_eligible: true` 的 16 套浅色色板（无绿色）随机抽取；深色仅用户明确指定时启用。
   - 酷果片头/片尾使用 `scripts/bookends.py`（R5/R8 母版，`3.72s–4.34s` 浮现标题）；封面、顶栏与总结卡等比加载原版透明 `assets/brand/kgxc/kgxc-logo.png`；封面默认仅第 0 帧显示并写入 `attached_pic`。
   - **底部分段章节进度条（默认「融合进度胶囊」方案 A，高 `48px`，禁止单根总进度条）**：正片调用 `DirectorStage.buildNavSegments` 与 `VisualMetaphors.drawSegmentedProgressBar` 渲染三态并记录 `auditor.recordProgressBar(navInfo)`；单行字幕位于 `y = 988` 独立避让。

## 3. 双层时间轴、音画同步与防重播铁律

- **Scene vs Beat 双层状态机 + 严禁画面抢跑旁白铁律**：
  - 使用 `DirectorStage.resolveTimeline(lines, t)` 同时获取场景连续时间 `sceneT`、子句时间 `beatT` 与扣除句首静音后的实际发声时间 `speechT`。
  - 入场动画、人物走位、曲线生长绑定 `sceneT`（跨 Beat 绝不归零重播）；禁止在 `sceneT = 0` 一次性剧透后续 Beat 才讲到的条目/结论/小标题，禁止负偏移抢跑；对话气泡绑定 `st.speechT`，句内关键词/结论用 `DS.phraseTime(beat, phrase, sceneStart)` 对齐并调用 `auditor.recordReveal`。
- **强校验配音同步与自然口语发音分离**：
  - 使用 `scripts/tts_sync.py --strict-beats` 合成多角色 Qwen3-TTS 配音（建议每条 2.5–5 秒、≤ 26 字），内建自然口语规整（`WOW` 读“哇哦”、`第 01–09 节` 不读前导 0）并支持逐 Beat `tts_text` 覆写读音；单行无标点字幕从 `speech_start` 对齐，末段片尾施加 `0.35s` 柔和淡出。

## 4. 不可跳过的双验收门禁与增量并行渲染

每支小样与每集正片交付前**必须全部通过**，不通过禁止汇报完成：

1. **门禁 A（自动化硬校验，返回码必须为 0）**：
   ```bash
   python3 SKILL_DIR/scripts/verify_delivery.py <video.mp4> --srt <sub.srt> --cover <cover.png> --timeline <timeline.json> --render-audit <render_audit.json> --visual-blueprint <visual-blueprint.json> --strict-ppt-guard --require-attached-pic
   ```
   强拦截：走路飘移、文字压人物/压字幕区、同场景动画归零重播、画面抢先旁白剧透（>80ms）、并列指标原地覆盖（`info_overwrite`）、**同屏双载体复述同一组数据（`redundant_data`）、同屏叠双 L1 标题（`double_headline`）、同集内置图表/相邻构图模板重复超限（`visual_pattern`）**、实景无互动悬空道具、快闪 PPT、总结板书晃动、PPT 框体 > 25%、动态场景无真实运镜、SRT 与时间轴脱节、音画/封面/字幕/尾音缺陷。
2. **门禁 B（实际抽帧目视核验 + 眯眼测试）**：
   - 从最终编码 MP4 抽取并实际查看：人物迈步中段帧、对话气泡高峰帧、非门店信息图/定制隐喻帧、关键结论与总结卡“触发前 0.2s vs 触发后 0.4s”对照帧、首帧封面与第 1 帧片头；
   - **9.0.0 眯眼测试（Squint Test）三项否决**：① 1 秒看清唯一 L1 标题与唯一视觉主角；② 无左右重复展示同一组数据、无随机漂浮胶囊墙；③ 整集图形语言贴合业务且不重复套模子。
3. **分场景增量并行渲染、局部回改与过程保留**：
   - 正片与返修优先通过 `node SKILL_DIR/scripts/render_director_incremental.mjs --html <director.html> --audio-dir <audio> --out-dir <out> --tmp-dir <tmp> --meta-json <meta.json> [--intro <intro.mp4> --outro <outro.mp4>] [--workers 3]` 执行（自动按 `scene_id` 整帧切片、多标签页并行、哈希缓存复用、无损拼接并合并等价 `render_audit.json`）。
   - 过程文件默认保留在课程工程内，正式成品交付至 `~/Desktop/ai 制课/<课程名称>/`。
4. **按需参考**：[9.0.0 杂志级信息层级与视觉多样性](references/70-v9-editorial-info-design-and-diversity.md)、[花字与原库音效](references/46-flower-text-and-native-sfx.md)、[封面与收尾检查](references/37-cover-and-delivery-finish.md)、[情境表演与步态](references/48-situational-acting.md)、[阅读与信息节奏](references/45-reading-and-information-pacing.md)、[本地 Qwen3-TTS 配音](references/23-local-qwen3-voice.md)。
