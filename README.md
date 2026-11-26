# 酷果星创 · AI 企业培训课程全链路引擎

**只需把制度文档、SOP 手册、产品资料或访谈录音发给 AI，通过自然对话，就能一键打造真正懂教学、有动效、有角色演绎、离线配音不出本机的全套企业精品课**——既能生成**多集 1080p 有声动画系列视频**，也能同步交付**独立交互课件（PPTX / HTML / PDF）、《讲义精要》、章节测验题库与 A4 可打印手写作业**。

> **它和普通 AI 生成 PPT/视频工具的本质区别**：市面工具只会“摘要念稿 + 贴静态网图”，遇到业务条款漏掉前提与例外、画面静止超过十秒、改一句话就要全片重做；本套件由 **ATD 教学设计引擎（`elearning-course-design`）** 与 **代码动画制片引擎（`corporate-training-motion`）** 双核驱动，从“核对原件覆盖率与条件例外”开始，到“1-Beat-1-Audio 毫秒级音画咬合”“3.3 头身可动角色演练”“自动化技术全检 + 按句秒级重渲”全程闭环。

- **跨主流 AI 平台通用（纯正 Agent Skill）**：基于标准 `SKILL.md` 与纯对话 / CLI 工作流，支持 **Antigravity、Claude Code、Codex、Cursor、Windsurf、WorkBuddy、Trae** 等主流 AI 工具直接安装使用，无桌面插件或浏览器工作台耦合。

[一句话发给 AI 自动安装](#一句话让-ai-帮你安装) · [在线观看 Antigravity 实渲宣传片与能力画廊](https://hebokenn.github.io/kgxc-corporate-course-skill/) · [下载 Skill v7.3.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.3.0/kgxc-course-suite-v7.3.0.zip) · [历史插件备份归档](docs/ARCHIVE.md#历史-dsh-桌面插件安装备份已停用仅作历史存档)

---

## 一句话让 AI 帮你安装

不需要自己配置路径或学终端命令。**直接复制下面这句话和链接，发给你正在用的 AI 助手**（Antigravity、Claude Code、Codex、Cursor、Windsurf、WorkBuddy 等），AI 会自动帮你拉取仓库、完成本地安装与依赖检查：

```text
请帮我安装这个企业培训制课 Skill：https://github.com/hebokenn/kgxc-corporate-course-skill
（macOS Apple Silicon 请运行仓库安装脚本 ./install.sh --agent both；若只需加载 Skill 规范也可安装 skills/corporate-training-motion 与 skills/elearning-course-design，安装好后告诉我怎么开始做第一门课。）
```

<details>
<summary>其他安装方式：双击安装包 / 命令行检查（doctor）/ 校验与开课示例</summary>

1. **下载 ZIP 双击安装（通用 Skill）**：[下载 `kgxc-course-suite-v7.3.0.zip`](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.3.0/kgxc-course-suite-v7.3.0.zip) → 解压 → 双击`安装或更新.command`（升级自动保留个人配音、设置与已有课程工程；仅同步 Skill 可运行 `./install.sh --skill-only --agent both`）。
2. **命令行体检（确认 FFmpeg / Chromium / 本地 Qwen3-TTS 状态）**：
   ```sh
   "$HOME/.local/bin/kgxc-course" doctor
   ```
3. **校验清单**：[Skill 包 SHA256SUMS](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.3.0/SHA256SUMS) · [完整依赖说明](docs/DEPENDENCIES.md)
4. **历史备份**：曾使用 DSH 桌面插件的用户，可在 [ARCHIVE.md](docs/ARCHIVE.md#历史-dsh-桌面插件安装备份已停用仅作历史存档) 查看已停用维护的 v7.2.0 历史安装包备份入口。

**装好后，直接把资料发给 AI 并输入：**

```text
请用 corporate-training-motion，把我提供的资料做成《收货核对流程》培训课。
受众：新入职门店同事。
目标：能找到并核对订单、商品 SN 和外包装信息，按原文要求完成交接。
交付：完整系列视频（或改为“只交付独立 HTML/PPTX 课件 + 逐字稿 + 题库”）。
先做资料诊断与原件要点梳理，等我确认大纲后再推进后续制作。
```

</details>

---

## 全景能力矩阵：从原始资料到整套培训交付

### 一、前端教学设计引擎（`elearning-course-design`）：先读透原件，再讲人话

| 核心能力 | 实际解决问题 |
| --- | --- |
| **多源资料精准解析** | 支持制度 PDF、Word、PPT、扫描件 OCR 及访谈音视频（按时间码定位），同时识读文档内的表格、截图与流程图表。 |
| **来源台账与条件/例外单列** | 逐页构建可追溯台账，明确标注**事实规则、触发前提、适用条件、例外情况与待核实缺口**，严格禁止 AI 臆造审批流程、业绩数字或内部制度。 |
| **“学员没有原件”上下文自检** | 培训成品只面向看不见原附件的学员。自动排查并改写“如图/原表/资料中”等悬空指代，首次提到表单与界面时先交代名称、用途与看哪里。 |
| **场景化实战转化 & 智能提问** | 拒绝“重视/赋能/形成闭环”式空话，严格按 **“工作触发情境 → 第一反应与动作判断 → 规则依据 → 示范 → 练习与反馈”** 重构口播；并在影响课程范围的节点主动弹出 **1–3 个带推荐与取舍的简洁选择**。 |

### 二、视觉、动效与角色引擎（`corporate-training-motion`）：纯粹代码生成，绝不静态拼图

| 核心能力 | 实际能力细节 |
| --- | --- |
| **100 种教学代码动效 + 全屏无白框视觉隐喻** | 遵循动画学原则（绝对时间快节奏缓动、虚拟相机推拉摇移、同元素匹配转场）与 **F 型视觉扫读热区引导**（结论前置、动作行首、例外标红）；内置 [`visual_metaphors.js`](skills/corporate-training-motion/workbench/motion/visual_metaphors.js) 提供**全屏 3 层视差 Apple 授权门店（`drawCinematicAppleStore`：玻璃幕墙、MagSafe/AirPods 配件墙、旗舰灯箱、顶棚柔光锥与透视暖橡木桌）**与**无白框开放画布（`drawAmbientBackdrop`）**，用光轨、曲线、数据雕塑与星环替代“大白框装字”PPT 壳，**任何正文画面绝不静止超过 3.5 秒**。 |
| **代码化三维道具 + 联网检索合规素材** | 遇到复杂硬件拆解或立体商品演示时，支持真 3D 透视投影模型（如 `iPhone 18 Pro` 冰川蓝全宽三摄平台与机身比例）与 Blender 联动；当纯几何绘图不足以表达具体实景道具或图标时，可通过 [`web_asset_search.py`](skills/corporate-training-motion/scripts/web_asset_search.py) 联网检索 Openverse / Wikimedia Commons 开放许可无水印素材并本地缓存至 `project/assets/web/`（自动记录来源、许可与 SHA-256 溯源清单）。 |
| **`CourseActorsCute` 3.3 头身可动角色 + 情绪化多档步速** | 全程代码骨骼驱动，自带**零滑步世界坐标落地步行、防弹膝盖 IK、行进转向与停步稳态回正、口型手势同步**，并内置**情绪化步速物理（`computeMoodWalk` / `paintExpressive`）**：在门店情景演练中可按剧情区分 `stroll`（闲逛慢步）、`brisk`（轻快迎宾）、`rush`（急匆匆前倾快步冲入 + 刹车回摆急停）与 `cold_exit`（冷脸转身快撤），解决人物千篇一律慢走呆板的问题；严谨区分黑衣店长、蓝衣店员（统一佩戴原版胸标）与便装无标顾客（禁与背景顺色），对话开口始终面向受话人。 |
| **16 套高对比明亮浅色画布（WCAG ≥ 4.5）** | 从精选明亮浅色板（[选色规范](skills/corporate-training-motion/references/47-course-palette.md)）随机配对，让系列视频、独立课件与《讲义精要》、题库、A4 作业保持出版级统一美观。 |

> 内置人物预设与品牌片头片尾默认服务酷果星创及 Apple 门店零售场景；其他企业与讲师团队可完整复用整套教学设计、动效渲染与配音质检体系，并按需替换为自有品牌视觉。

![AI 全链路企业培训制课工作流与交付闭环](docs/media/v71/headless-workflow-card.png)

![16 套精选明亮高对比浅色画布色板](docs/media/v71/bright-palettes-16.png)

![CourseActorsCute 3.3 头身可动矢量角色阵营](docs/media/v71/cute-actors-cast.png)

### 三、离线安全配音、音画精确咬合与多态交付闭环

- **本地 `Qwen3-TTS` 离线配音与音色克隆（企业机密不外传）**：全流程本地生成拟真多角色语音，内置获授权的 **didi 男声**、**pipi 女声**，并可配置克隆自有讲师声线；不向任何第三方语音云发送制度文件与音频。
- **`1-Beat-1-Audio` 毫秒级音画咬合 + 原库提示音效**：告别长语音猜秒数导致的“字幕提前剧透”或声画错位！[`tts_sync.py`](skills/corporate-training-motion/scripts/tts_sync.py) 按最小视觉意群逐句生成真实录音并校准镜头帧数、驱动**动态说话气泡指向**、自动监测句尾能量防吞字截断、混入 48 kHz **“叮 / 嘟咚”原库教学提示音**与重点花字弹出，并产出**单行零标点外挂 `.srt` 字幕**。
- **一套资料，四种形态按需全套带走**：
  - **多集系列课套件**：统一批次按**内容母版三选一** + **跨章节 3 段代表性有声小样**定调，分集导出 `1080p / 24fps` 视频、字幕与封面，同步交付同风格的**《讲义精要》、章节测验题库、A4 可打印手写作业**。
  - **单支重点培训视频**：含完整品牌片头片尾、目录进度条、双声演练与重点花字。
  - **独立授课课件**：不录视频也能直接交付可面授或自录的 **PPTX / DOCX / PDF / 交互式 HTML 课件** 与完整逐字稿。
  - **按句分钟级局部返修 & 过程默认留档**：制度微调只需对话指出修改哪几句，自动只重配重渲变动片段与对应讲义，其余全部毫秒级复用；[`verify_delivery.py`](skills/corporate-training-motion/scripts/verify_delivery.py) 自动验收音画流、第 0 帧高清识别封面（`attached_pic` 嵌入，第 1 帧秒切正文不拖泥带水）与零重叠字幕后归档至桌面 `ai 制课/<课程名称>/`，原始过程工程默认完整保留。

| 内置授权音色 | 典型适用位置 | 实声试听 |
| --- | --- | --- |
| **didi · 男声** | 步骤拆解、系统示范与要点提示，清晰利落 | [在线试听 MP3](https://raw.githubusercontent.com/hebokenn/kgxc-corporate-course-skill/main/docs/media/voices/didi-audition.mp3) · [下载 WAV](docs/media/voices/didi-audition.wav) |
| **pipi · 女声** | 课程导入、情景对话与概念阐述，自然亲切 | [在线试听 MP3](https://raw.githubusercontent.com/hebokenn/kgxc-corporate-course-skill/main/docs/media/voices/pipi-audition.mp3) · [下载 WAV](docs/media/voices/pipi-audition.wav) |

---

## 宣传片即实证：本片直接由本 Skill 经 Antigravity 实渲产出

下面这支 **全能力介绍宣传片** 本身就是本仓库产出的真实成品——由 **Antigravity 调用本 Skill** 完成文案分段、**`didi / pipi` 本地离线双声配音 + 原库提示音效、`CourseActorsCute` 动画演绎、16 套浅色画布渲染**，并通过 `verify_delivery.py` 全项技术校验（1920×1080、24fps、48 kHz 立体声、第 0 帧封面隔离与 `attached_pic`、单行无标点字幕）。

[![酷果星创 AI 企业培训制课引擎宣传片封面](docs/media/v71/kgxc-v71-promo-poster.jpg)](https://hebokenn.github.io/kgxc-corporate-course-skill/)

**[在线观看 69 秒全面展示宣传片（GitHub Pages）](https://hebokenn.github.io/kgxc-corporate-course-skill/)** · [下载 1080p MP4](docs/media/v71/kgxc-v71-promo.mp4) · [下载无标点 SRT 字幕](docs/media/v71/kgxc-v71-promo.srt) · [查看第 0 帧独立封面](docs/media/v71/kgxc-v71-promo-cover.png)

> 如需查阅更早期 5.x / 6.x 历史版本的旧宣传片、17 支风格样片与过往工作台界面，请移步独立归档页（仅供查阅过往历史版本）：[历史版本与过往素材归档](docs/ARCHIVE.md) · [在线历史画廊](https://hebokenn.github.io/kgxc-corporate-course-skill/archive.html)

---

## 一门课是如何在对话里完整落地的

| 阶段 | AI 为你自动完成 | 你只需要确认 |
| --- | --- | --- |
| **1. 资料拆解与设计** | 读取 PDF/Word/PPT/扫描件/录音，建立来源台账、学习目标与单课/系列课结构 | 教给谁、学什么、重点范围 |
| **2. 原件对照与逐字稿** | 核对要点覆盖、单列条件与例外、消除无原件悬空指代并完成自查；通过 `workflow.py source-coverage` 绑定原件、逐字稿与覆盖报告哈希 | 在对话或结构化提问中核对取舍说明与讲法后明确确认 |
| **3A. 课件与配套文档** | 交付可讲/可录屏的 PPTX / HTML / PDF 课件、《讲义精要》、测验题库与 A4 手写作业 | 核对授课节奏与练习难度 |
| **3B. 视觉母版定调与小样** | 按内容母版输出 3 套实质不同方案（`template_masters`），定调后导出 3 段跨章节有声 MP4 小样 | 选定画布配色、角色造型与声音节奏 |
| **4. 全片交付与按句微改** | 全课批量渲染，经 `verify_delivery.py` 全检后归集至桌面目录；后续改稿只重配重渲受影响句 | 验收成片，或随时对话局部微调 |

---

## 适用环境、开源边界与详细文档

- **运行环境**：完整本地渲染与离线 `Qwen3-TTS` 配音环境已在 **macOS Apple Silicon（arm64）** 实测验证；标准 `SKILL.md` 兼容 Antigravity、Claude Code、Codex、Cursor、Windsurf、WorkBuddy、Trae 运行，模型推理与额度沿用宿主原生配置。
- **开源协议与共创**：自研引擎代码、工具链与通用规范以 **[Apache License 2.0](LICENSE)** 开源；酷果星创 Logo、专有工服角色、R5/R8 片头片尾及第三方字体音效沿用 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。由 [@hebokenn](https://github.com/hebokenn) 主导设计与维护，携手 **Antigravity（[Gemini](https://github.com/gemini-code-assist)）** 与 **[Codex](https://github.com/codex)** 协同共创。

| 专题文档 | 链接 |
| --- | --- |
| 日常制作流程与操作手册 | [使用指南](docs/USAGE.md) · [依赖说明](docs/DEPENDENCIES.md) |
| 系列课批量工作流与自查规范 | [59-streamlined-series-and-selfcheck.md](skills/corporate-training-motion/references/59-streamlined-series-and-selfcheck.md) |
| 角色、配音、花字音效与动效 | [角色指南](docs/CHARACTERS.md) · [配音指南](docs/VOICE.md) · [音效库](docs/SOUND.md) · [动效指南](docs/MOTION.md) |
| 历史版本展示与完整变更记录 | [历史版本归档 ARCHIVE.md](docs/ARCHIVE.md) · [CHANGELOG.md](docs/CHANGELOG.md) · [RELEASING.md](docs/RELEASING.md) |

---

## 版本更新

### 纯净 Skill 化、移除 DSH 插件并打通纯对话原件覆盖确认：核心 7.3.0 · 2026-11-26

- **全面移除 DSH 桌面插件，聚焦纯正跨平台 Skill**：从主仓库删除 `plugin/`、`plugin.json`、`.codex-plugin/`、`.mcp.json`、`cordis.patch.yml`、`安装制课插件.command` 及插件打包/安装脚本，不再在主分支维护桌面宿主插件；在 [`docs/ARCHIVE.md`](docs/ARCHIVE.md#历史-dsh-桌面插件安装备份已停用仅作历史存档) 保留唯一的 `v7.2.0` 历史插件备份入口。
- **打通纯对话 / CLI 原件覆盖确认闭环（`source_coverage.py` / `workflow.py`）**：修复 7.0.0 移除网页工作台后 `SourceCoverage.confirm()` 仍卡死在 `dsh-user-click` / `preferred_workbench == 'dsh'` 的历史阻塞；新增 `workflow.py source-coverage COURSE --save / --confirm` 命令，在保留当前原件/逐字稿/报告 SHA-256 绑定与防 AI 擅自代确认校验的前提下，允许用户在对话或宿主结构化提问中直接确认原件覆盖报告并推进分镜与出片。
- **统一纯对话操作口径（`elearning-course-design 2.1.1` / `corporate-training-motion 7.3.0`）**：清理 `SKILL.md`、`backend.py`、`ai_review.py`、`studio.py`、`stage_confirmation.py` 及参考文档中的 DSH 专属路径与提示，确保 Antigravity、Claude Code、Codex、WorkBuddy、Cursor 等宿主开箱即用。

### 情绪化多档步速物理、全屏 3 层视差门店与无白框电影级动效：插件 0.12.0 / 核心 7.2.0 · 2026-11-26

- **情绪化多档步速物理与微表演（`workbench/motion/actors_v3_cute.js`）**：新增 `GAIT_PRESETS`、`computeMoodWalk` 与 `paintExpressive`，支持按剧情区分 `stroll`（闲逛 `145px/s`）、`brisk`（轻快迎宾 `265px/s`）、`rush`（急匆匆冲入 `470px/s` + `+9.5°` 前倾与刹车急停回摆）与 `cold_exit`（冷脸快撤 `310px/s`），让着急进店、受压后退与热情迎候形成鲜明表演反差。
- **全屏 3 层视差 Apple 授权门店与无白框开放画布（`workbench/motion/visual_metaphors.js`）**：新增 `drawCinematicAppleStore`（商场玻璃幕墙与阳光斜射、MagSafe/AirPods 配件墙、旗舰灯箱、室内陶瓷绿植、顶棚线性 LED 柔光锥、透视暖橡木体验桌与斜立样机）及 `drawAmbientBackdrop` 开放画布基元，并在 `SKILL.md` 固化“去大白框 PPT 壳”规范。
- **同步纳入 7.1.1 动效库与素材能力**：完整包含真 3D 透视投影 `iPhone 18 Pro`（`draw3DPhoneProp`）、F 型扫读热区追踪、`scripts/web_asset_search.py` 开放许可素材联网检索入库与 5 幕连续运镜宣传片 v4；已完成真实课程 3 支 v7.2 样片（`verify_delivery.py --strict-ppt-guard` 零报错零滞留）与打包发布全检。

### 5 幕连续运镜动效引擎、真 3D iPhone 18 Pro 与联网素材检索：插件 0.11.1 / 核心 7.1.1 · 2026-11-26

- **底层动效与运镜基元升级（`workbench/motion/visual_metaphors.js`）**：新增绝对时间快节奏缓动（`easeOutExpo` / `easeOutQuint` / `easeOutBack` / `spring`）、虚拟相机层 `CameraRig`、多层门店景深背景、**F 型扫读激光热区组件**，以及严格按官方机身比例（`71.9 × 150.0 × 8.75 mm`）构建的**真 3D 透视投影 `iPhone 18 Pro`（冰川蓝全宽三摄平台）**。
- **支持联网检索开放许可素材入库（`scripts/web_asset_search.py`）**：聚合 Openverse 与 Wikimedia Commons 开放许可无水印图库，下载至课程 `project/assets/web/` 并自动写入含来源、许可与 SHA-256 的 `manifest.json` 溯源清单；同步写入 `SKILL.md` 与 `references/34-content-driven-assets.md`。
- **全新 5 幕连续运镜宣传片上线**：推翻旧版 16 页分镜，改用全幅连续运动构图、激光斜劈切场、X 光扫描切代码线框、左旋 5 列穿插高速动效墙、全屏上下画布轮播与五端逐项踩点微动效；全片通过 `verify_delivery.py --strict-ppt-guard` 零错误零警告校验。

### 全链路纯对话制课引擎、CourseActorsCute 可动角色与完整展示焕新：插件 0.11.0 / 核心 7.1.0 · 2026-11-26

- **全链路纯对话交互与公共 CLI 工具**：日常制课全部通过自然对话推进，支持多集系列课统一批次规划与按句最小范围局部返修；新增公共工具 `scripts/tts_sync.py`（支持 16/24/32-bit WAV 尾音能量检测、增量缓存、48 kHz 音效混音与单行无标点 SRT）及 `scripts/verify_delivery.py`（全自动核验 1080p/`yuv420p`、48 kHz AAC、第 0 帧独立封面与 `attached_pic` 嵌入、字幕无标点/零重叠）。
- **统一 `CourseActorsCute` 3.3 头身可动矢量角色**：内置世界坐标零滑步步态、防弹膝盖 IK、行进转向与停步稳态回正、口型同步说话及原版胸标绑定，支持按课程扩展新造型便装顾客。
- **全面焕新展示主页与独立历史归档页**：主页与 GitHub Pages 全面呈现双引擎能力矩阵、由 Antigravity 调用本 Skill 实渲制作的最新版宣传片及极简“发给 AI 自动安装”引导；过往历史版本展示与老旧样片统一归档至 [`docs/ARCHIVE.md`](docs/ARCHIVE.md) 与 `docs/archive.html`。

### 多集系列课母版三选一与 16 套明亮浅色板：插件 0.10.0 / 核心 7.0.0 · 2026-11-24

- **多集系列课统一批次与内容母版三选一**：`storyboard.py` 新增 `template_masters` 与 `segments[].template_id` 校验，整门课程可统一输出分集视频 + 《讲义精要》+ 测验题库 + A4 手写作业。
- **16 套高对比明亮浅色色板与实质自查清单**：默认随机选色池升级为 16 套 WCAG ≥ 4.5 无绿浅色画布；制作端在出片前完成实质自查修精，过程文件默认保留。

<details>
<summary>展开查看更早版本概览（5.7.1 – 6.9.8）</summary>

- **6.9.0 – 6.9.8（DSH 0.9.0 – 0.9.9）**：教学动效节奏参数（预备、弧线与落定）、渐进式任务面板、应用内更新提醒与片头等待预算。
- **5.7.1 – 6.8.2**：原件要点覆盖与条件例外单列、全身可动顾客与对白朝向校验、独立第 0 帧封面规则、原库“叮/嘟咚”音效及本地 `didi / pipi` 参考音色。[查看完整历史与验证记录](docs/CHANGELOG.md)

</details>
