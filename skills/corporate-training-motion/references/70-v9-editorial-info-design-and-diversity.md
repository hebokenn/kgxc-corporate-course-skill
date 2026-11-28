# 9.0.0 杂志级信息层级、定制信息图与反套路视觉多样性规范

> **适用范围**：本规范与 [电影级导演引擎、强契约与交付硬门禁](60-v8-cinematic-director-and-gates.md) 共同构成 `9.0.0` 唯一权威规范。它确立了 **「杂志/Keynote 极简去框排版 + Vox/Kurzgesagt 定制信息图」融合标准（Plan C）**，专门根治 AI 在制课中的四大退化问题：**左右信息重复、双标题叠罗汉、随机漂浮胶囊贴纸、以及反复复用少量内置柱状图做排列组合（最小路径执行）**。

---

## 1. 借鉴的经典信息设计与多媒体学习原理

本规范并非主观审美偏好，而是将以下四套经典信息设计原理直接工程化为可校验的渲染约束与门禁：

1. **Richard Mayer 多媒体学习理论（Cognitive Theory of Multimedia Learning）**：
   - **冗余原则（Redundancy Principle）**：通过 **三通道分工（Triangulation）** 降低认知负荷——旁白讲故事与因果，主图形展比例与结构，画面文字仅作极简锚点；**严禁同屏用两套视觉载体复述同一组数据**（如左侧柱状图与右侧 KPI 卡片重复列出同一批数值）。
   - **信号原则（Signaling Principle）**：通过 **聚光灯降噪（Spotlight Dimming）** 引导视线——多条目并列时，讲到哪一项只高亮哪一项，其余条目自动退阶至 `24%–35%` 柔和透明态，消除“满屏高亮、目不暇接”。
   - **空间临近原则（Spatial Contiguity Principle）**：标注文字紧贴对象或以极细引导线（`drawLeaderLine`）、分组大括号（`drawGroupingBracket`）精确锚定，禁止用无指向的漂浮彩色胶囊到处乱贴。
   - **一致性原则（Coherence Principle）**：剔除无叙事作用的装饰边框、多重标题堆叠与杂乱视觉噪音，留白服务于主焦点。
2. **唯一视觉重心与三级信息层级（Rule of One + Visual Hierarchy）**：
   - **L1 观点大标题（每屏仅 1 套）**：采用无框杂志排版（左侧细竖标 + 轻眉标 + 单行强主张大标题 + 关键词柔光底衬），严禁“页眉标题 + 红胶囊副标 + 居中标题 + 漂浮蓝胶囊”叠加。
   - **L2 唯一视觉主角（占屏 60%–70%）**：每个信息场景只服务一个视觉主角，辅助区若留有空间，必须提供**更高一维的洞察、体感翻译或归因结论**，形成「左证据 + 右洞察」或居中放大留白。
   - **L3 语义标注（Callout）**：仅人物台词使用对话气泡；重点提示优先用细引导线、大括号、下划线或局部高光，不再把普通标题和行动清单塞进宽窄不一的圆角胶囊。
3. **12 栏网格与骨架先行防剧透（Editorial 12-Column Grid + Skeleton-First）**：
   - 所有非实景信息页统一对齐 **12 栏网格（`x = 120..1800`，栏距 `24px`）**，用明确骨架（如 `grid_7_5`、`grid_5_7`、`full_journey`、`center_focus`）替代无网格碰撞弹开。
   - 对需要逐项揭示的行动清单或步骤页，在未讲到对应 Beat 前使用**虚线编号骨架槽（Skeleton-First）**保持版面重心稳健，既 100% 严守零剧透铁律，又避免半屏空荡荡、孤立飘标签。
4. **数据语义决定图形形态 & 对抗最小路径偷懒（Data-to-Visual Matching + Anti-Satisficing）**：
   - 流程和方法论高度复用，但**画面绝不做现有组件的排列组合**。按真实业务逻辑匹配图形语言：
     - 群体占比（如 `近 2/3`、`>60%`）→ **人像/图标点阵（Pictogram）**（Kurzgesagt 招牌，直给体感）；
     - 多项中文长标签排序对比 → **分组水平排序条 + 聚光灯（Spotlight Horizontal Bars）**；
     - 跨环节流程/流失断点 → **横向服务旅程断点图（Journey Funnel）**；
     - 行动打卡/步骤闭环 → **无框极简行动清单（Editorial Checklist + Skeleton Slots）**；
     - 业务专属机理/表单/对象 → **按本课业务现场定制原生 Canvas/SVG 图形（`custom:*`）**（如透明报价单、设备体检仪、对比天平、作业手册实物缩影等）。

---

## 2. 9.0.0 基础能力 + 低套路可选原语（`VisualMetaphors`）

> **重要解绑原则**：所有图表与板书原语均为**可选工具之一**，不再作为必须调用的硬契约。`drawSculptureBar`、`drawKpiRail`、`drawCumulativeStack`、`drawFloatingTag` 仅保留向后兼容与按需选用，**严禁默认把它们排列组合当作通用解题模子**；`drawFloatingTag` 不得用于常规主标题与行动清单，同屏漂浮胶囊总数 ≤ 2。

| 分类 | API | 定位与用法 |
| --- | --- | --- |
| **12 栏网格底座** | `VM.GRID_12` / `VM.gridCols(startCol, spanCols)` | 计算严格对齐 `120..1800` 的列起始 `x` 与宽度 `w` |
| **静谧顶栏与 L1 标题** | `VM.drawQuietTopBar(ctx, logoImg, epLabel, epTitle, pal, opts)`<br>`VM.drawEditorialHeadline(ctx, x, y, kicker, headline, pal, opts)` | 静谧品牌眉栏 + 每屏唯一无框 L1 观点大标题（支持关键词柔光底衬） |
| **指向与归因 Callout** | `VM.drawLeaderLine(ctx, x1, y1, x2, y2, opts)`<br>`VM.drawGroupingBracket(ctx, x, yTop, yBot, targetX, opts)` | 将主图特定条目或分组直接连接到右侧体感翻译/核心归因卡 |
| **低套路信息图（可选）** | `VM.drawSpotlightHorizontalBars(ctx, x, y, w, items, pal, opts)`<br>`VM.drawPictogramGrid(ctx, x, y, w, h, pal, opts)`<br>`VM.drawJourneyFunnel(ctx, x, y, w, steps, pal, opts)`<br>`VM.drawEditorialChecklist(ctx, x, y, w, items, pal, opts)` | 分别对应「分组水平排序 + 聚光灯」「人像/设备点阵」「横向旅程断点」「无框清单 + 防剧透骨架槽」；与业务定制 `custom:*` 图形搭配使用 |

---

## 3. 全集视觉多样性蓝图（写渲染代码前的必过前置关）

在全课分镜确认后、编写导演渲染 HTML 前，必须先为每集产出 `visual-blueprint.json` 并通过校验：

```bash
python3 SKILL_DIR/scripts/check_visual_blueprint.py <visual-blueprint.json> --markdown-out <visual-blueprint.md>
```

每个场景必须声明：
- `scene_id`、`layout_kind`、`layout_skeleton`（12 栏骨架，如 `grid_7_5` / `grid_5_7` / `full_journey` / `store_wide`）
- `l1_headline`（非实景场景必填唯一观点标题）
- `primary_visual`（唯一主视觉形态；业务定制原生图形以 `custom:` 开头，如 `custom:repair_quote_sheet`）
- `secondary_role`（辅助区职责，严禁复述主图数据；可为 `none`、`insight_pictogram`、`bracket_attribution`、`custom:workbook_artifact` 等）
- `callout_style`（如 `leader_line` / `grouping_bracket` / `speaker_bubble` / `spotlight`）

**硬性反偷懒拦截规则**：
1. **同屏零数据复述**：辅助区不得重复展示主视觉同一组数值/指标；
2. **单集同形态上限**：内置单一图表原语（`sculpture_bar`、`horizontal_spotlight_bars`、`pictogram_grid`、`journey_funnel`、`kpi_rail` 等）同一集内**最多出现 1 次**；
3. **相邻非实景防克隆**：相邻两个非实景场景禁止复用相同的 `layout_skeleton` + `primary_visual`；
4. **必须包含业务现场定制图形**：当单集非实景信息场景 ≥ 4 个时，至少包含 **1 个 `custom:*` 业务定制视觉**，禁止整集纯靠内置原语排列组合；
5. **漂浮胶囊克制**：禁止 `floating_pill_wall`，单场景漂浮胶囊 `capsule_count <= 2`。

---

## 4. 9.0.0 导演遥测与门禁 A/B 升级

1. **运行期遥测（`DirectorStage.createFrameAuditor` + `mergeFrameAudits`）**：
   - `auditor.recordDataCarrier(carrierId, dataFingerprint, rect, kind)`：拦截同屏双载体复述同一组数据（`redundant_data_violations`）；
   - `auditor.recordHeadline(headlineId, rect)`：拦截同屏叠加多套 L1 主标题（`double_headline_violations`）；
   - `auditor.recordVisualPattern(patternKind, { skeleton })`：跨整集（含分场景增量并行合并后）拦截内置图表重复超限与相邻构图克隆（`visual_pattern_violations`）。
2. **门禁 A 联动校验**：
   ```bash
   python3 SKILL_DIR/scripts/verify_delivery.py <final.mp4> \
     --srt <final.srt> --cover <cover.png> --timeline <timeline.json> \
     --render-audit <render_audit.json> --visual-blueprint <visual-blueprint.json> \
     --strict-ppt-guard --require-attached-pic
   ```
3. **门禁 B 新增「眯眼测试（Squint Test）」3 项目视否决核查**：
   实际查看抽帧成片时，以下任意一项不通过必须返修：
   - 画面中是否存在**两块区域重复展示同一组数据或文案**？
   - 眯眼看画面，能否 1 秒识别出**唯一的 L1 观点标题与唯一的视觉主角**（无双标题叠罗汉、无漂浮胶囊乱贴）？
   - 整集非实景信息页是否呈现出**贴合业务的多样化图形语言**，而非反复套用同一套柱状图/卡片模子？
