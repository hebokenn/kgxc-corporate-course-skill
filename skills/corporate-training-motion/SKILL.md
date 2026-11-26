---
name: corporate-training-motion
description: 酷果星创课程设计与制作统一入口（7.0.0 精简工作流）。先确认教学方案与逐字稿，再交付独立课件或按内容母版三选一、全课分镜、三段抽样有声小样、完整系列视频与配套讲义/题库/作业。
---

# 酷果星创课程共创与制作（7.0.0）

以**你我对话 + 独立生成的富排版 HTML / MP4 审阅成品**为核心协作方式；已移除旧版网页工作台 UI（`design.html` / `index.html`），本地服务仅作无头渲染、校验与导出。

## 1. 主流程总览（统一批次，不走重复重流程）

先读 [7.0.0 精简高效工作流规范](references/59-streamlined-series-and-selfcheck.md) 与同目录的 `../elearning-course-design/SKILL.md`：

1. **建档与恢复**：
   - 新课运行 `python3 SKILL_DIR/scripts/kgxc_course.py start COURSE --title 课名 --source 原件`，保留 `inputs/` 原件、建立规范目录并抽取本课浅色色板。
   - 恢复运行 `python3 SKILL_DIR/scripts/kgxc_course.py resume COURSE`；全程**不自动打开工作台网页**，按返回状态沿用有效确认。
   - **模型通道**：严格沿用当前宿主原生已选模型，禁止擅自切换供应商或收费来源。
2. **教学方案与大纲（统一规划）**：
   - 先读透原件（含图表/密集页），结合 [原件覆盖与现场讲解](../elearning-course-design/references/source-coverage-and-scope.md) 明确核心工作任务、学习目标、内容取舍与推荐讲法；有重要影响的选择用宿主结构化提问（最多 3 题）集中展示，再生成可审阅的大纲 HTML。
   - **授课立场**：代表酷果**总部团队发展中心**直接面向门店团队讲解，不在口播、字幕或封面自报部门；保留酷果星创开场问候语与完整收尾。
3. **统一逐字稿与自查**：
   - 大纲确认后，按章节编号编写完整口播逐字稿（不含制作备注与避免词元说明），先按 [逐字稿输入与作者自检](../elearning-course-design/references/script-authoring-quality.md) 与 [学员上下文检查](../elearning-course-design/references/learner-context.md) 自查修精，确认口语自然、无依赖原件的悬空指代、无车轱辘话，再输出逐字稿审阅 HTML 请用户确认。
4. **独立分支：课件 或 视频（系列课统一批次）**：
   - **课件分支**：按用户要求交付 PPTX / DOCX / PDF / HTML 课件与逐字稿即可完成；独立课件页面不作为视频制作输入。
   - **视频分支**：
     - 先用结构化提问确定**制作偏好**（顾客形象/重点花字/原库提示音效 `teaching-native-v1`/配音音色与试听方式，写入 `project/production-preferences.json`）。
     - **内容母版三选一 + 全课 1 套最优分镜**：提炼核心视觉母版（每类母版提供 3 套实质不同方案供定调），定调后全课逐段直接输出 1 套最优导演分镜；输出分镜审阅 HTML 供确认。
     - **全课抽 3 段代表性有声小样**：覆盖不同母版与高风险实现，使用正式画布、多角色 Qwen3-TTS 配音及 R5/R8 片头片尾生成 MP4 小样供用户试听确认。
     - **共享母版分集导出**：小样锁定视觉、字体、进度条与声音规范后，全课制作主体、花字与音效并按章节分集导出 MP4 + SRT + 封面，连同讲义精要、题库与可打印作业一并保存至 `~/Desktop/ai 制课/<课程名称>/`。

## 2. 视觉、人物与动画规范（纯代码驱动）

1. **代码化自由动画 + 联网检索合规素材（禁止静态人物）**：
   - 坚持用代码实现动态表现（程序化描边、路径形变、镜头推拉、漫画情绪弹幕与进度仪表），**不使用任何整张静态 PNG 人物**。
   - **支持联网搜索可用素材加入**：当课程需要真实场景纹理、产品参考、矢量图标或实景道具时，可用宿主联网检索或运行 `python3 SKILL_DIR/scripts/web_asset_search.py search "<关键词>"` 检索无水印、可商用/开放许可素材，并通过 `fetch` 缓存到 `COURSE/project/assets/web/`（自动写入含来源与许可信息的 `manifest.json`）后再接入画面；严禁直接热链外网或混入带水印图库/竞品标志。
   - **产品范围限定 Apple**（或明确适配 Apple 的无他牌配件）。
2. **唯一人物引擎 `CourseActorsCute`（`workbench/motion/actors_v3_cute.js`）**：
   - 全课人物统一使用 3.3 头身简洁可爱可动人物（含世界坐标不滑步步态 `computeGroundedWalk`、方案 B 转侧身/停步回正、软性 2-Bone IK）。
   - 黑衣 KG 店长与蓝衣 KG 店员必须绑定原版 `assets/profiles/kgxc/kg-original.png` 胸标；Coach 保留 MyCoach；顾客穿便装且 `showKG: false`。
   - 新课使用 `workbench/layered_customers.py` 的 `design_for_course()` 或在 `actors_v3_cute.js` 内扩展发型/穿搭，**严禁服装与画布顺色**；同场人物有清晰外貌区分，跨镜同一人保持连续。
   - 对白须同场可见、开口前完成朝向、听完再移步；柜台层级严格远景员工 → 柜台 → 近景角色；脚底与物件有真实支撑。
3. **精选明亮通透色板**：
   - 新课从 `workbench/course-palettes.json` 中 `random_eligible: true` 的 16 套高对比浅色系色板随机抽取（不含绿色）；深色仅在用户明确指定时启用。
4. **品牌包装、导航与封面**：
   - 酷果片头/片尾使用 `scripts/bookends.py`（批准 R5/R8 背景与 `title-tracking.json`，片头标题在 `3.72s–4.34s` 背景白底落定后浮现）。
   - 封面、正文顶栏与结尾要点总结卡须等比加载原版透明 `assets/brand/kgxc/kgxc-logo.png`（不以纯文字替代）。
   - 底部必须有随本课风格定制的课程进度条；含两个及以上小节须有课程目录页与小节标题页。
   - **视频缩略图封面**：默认仅第 0 帧显示封面、第 1 帧进入原片头，并在容器中写入 `attached_pic`，不额外停留或淡出。

## 3. 配音、去 PPT 化与音画意象同步铁律

- **1-Beat-1-Visual 意象逐拍对应（严禁讲 PPT）**：严禁把多句长口播合并进同一张大白框文字卡片拼盘，更严禁靠定时光标轮流亮框（如 `floor(t / 1.9)`）或 `Math.sin` 假波形凑动态。必须在合成配音前先把逐字稿拆成**最小完整短句 Beat（建议每条 2.5–5 秒、≤ 26 字，不切碎词语防尾音截断）**，每条 Beat 绑定 1 个明确的**视觉意象（演什么状态变化/隐喻/人物动作）**；使用 `scripts/tts_sync.py` 调用本地 `scripts/qwen3_tts.py`（支持 `didi` / `pipi` 等多角色分声），前端直接按 `timeline.json` 中每条 `beat.start / end` 切换或演进对应镜头。
- **屏幕极简字数红线**：口播负责说完整的话，画面只留锚点词和视觉对象。除非明确需要横向对比或总结回看，否则主标题 ≤ 10 字、卡片短语 ≤ 10 字、同屏信息块 ≤ 3 组、**同屏正文建议 ≤ 35 字**；严禁把 20 字以上的完整解释句搬进卡片。
- **动态气泡锚点**：对话气泡箭头必须根据说话人当前真实画布坐标动态指向头部/嘴部，文字随当前子句同步切换。
- **阅读节奏与真实变化**：任何正文画面禁止静止或仅靠边框变色停留超过 `3.5s`；每次推进必须伴随构图切换、对象状态改变、镜头推拉或人物动作。遵循 [阅读与信息节奏](references/45-reading-and-information-pacing.md) 与 [课程效果与画面工艺](references/36-course-craft.md)，禁止段末自动插静音；单行无标点字幕独立避让主体与底部进度条。

## 4. 产出前实质自查验收 & 局部灵活回改

取消强制多轮独立盲审子 Agent 与形式化监督侦探，改为制作端交付前必须扎扎实实完成**实质自查验收（Self-Check Gate）**并实际查看渲染关键帧与成片：

- **技术与视听硬核验**：运行 `scripts/verify_delivery.py <video> --srt <srt> --cover <cover> --timeline <timeline.json>` 核对 MP4/SRT/封面三件套完整、音画时长一致（48kHz AAC 非静音）、第 0 帧封面/第 1 帧片头、R5/R8 时机、末句口播完整无半句残音、单行无标点字幕无重叠，以及**跨 Beat 画面切换率（拦截连续多句滞留同一画面的 PPT 化片段）**；再实际抽看关键帧与连续播放检查美感与音画配合。
- **最小范围局部回改**：用户对小样或成片提出改稿或微调时，只局部重配受影响句子、重渲染对应片段与衔接、更新对应字幕和受影响讲义条目，保留其余已确认章节的配音与画面。
- **过程文件默认保留**：原始素材、逐字稿、分镜、配音、小样、工程与渲染缓存全部保留在课程工程内，绝不在交付后自动删除；成品正式交付到 `~/Desktop/ai 制课/<课程名称>/`，与过程目录严格分离。
- **深度参考按需加载**：[花字与原库音效](references/46-flower-text-and-native-sfx.md)、[封面与收尾检查](references/37-cover-and-delivery-finish.md)、[逐场视觉检查](references/39-visual-hygiene.md)、[扫读层级与教学动作](references/58-scan-and-teaching-motion.md)、[本地 Qwen3-TTS 配音](references/23-local-qwen3-voice.md)、[系列课质量基线](references/57-series-quality-baseline.md)。
