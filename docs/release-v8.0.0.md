## 8.0.0：电影级导演引擎、强契约避让、自然口语发音分离与双验收硬门禁

**核心 Skill `corporate-training-motion 8.0.0` · `elearning-course-design 2.1.1`**

本版面向多集精品课实战交付升级为 **8.0.0 电影级导演引擎与强制双验收门禁**，彻底消除“小样精致、正片退化成白框模板”“跨句动画重播”“无接地滑行”“气泡压人脸”及“英文/编号生硬朗读”等问题：

- **共享电影级导演内核（`workbench/motion/director_stage.js`）**：小样与全集正片共用同一套 `DirectorStage` + `CourseActorsCute` + `VisualMetaphors` 内核，内置 `resolveTimeline`（`sceneT` / `beatT` 双层时间轴，跨句绝不归零重播）、`evalCamera`（多关键帧真实推拉摇移运镜）与 `createFrameAuditor`（输出逐帧遥测 `render_audit.json`），详见唯一权威规范 [`60-v8-cinematic-director-and-gates.md`](https://github.com/hebokenn/kgxc-corporate-course-skill/blob/main/skills/corporate-training-motion/references/60-v8-cinematic-director-and-gates.md)。
- **强契约人物引擎 + 智能避让防压字**：`CourseActorsCute` 禁止传 `walkPhase/strideAmp` 与非法 `mood/gesture` 枚举（错参直接抛错阻断飘移），直接返回 `headRect/bodyRect/exclusionRect`；`VisualMetaphors` 新增 `drawSmartSpeakerBubble` 与 `placeAvoidingActors`，自动避开人物头身、背景 Logo 与字幕安全区，并规范同场景子幕非重叠交接与左边缘气泡安全距。
- **自然口语发音分离 + 无损音频热替换（`scripts/tts_sync.py`）**：`--strict-beats` 严控克隆雷同分镜与气泡错位；内建口语规整（默认 `WOW` 读作“哇哦”、`第 01–09 节` 读作“第一–九节”不读前导 0，同时字幕与画面保持原样，并支持逐句 `tts_text` 覆写）；沉淀品牌片尾末段 `0.35s` 柔和淡出与发音微调 `-c:v copy` 秒级无损音频热替换实践。
- **不可跳过的双验收硬门禁（`scripts/verify_delivery.py`）**：新增 `--render-audit` 硬门禁 + 16×16 宏块微抖防作弊 + 动画归零重播像素检测，零容忍拦截走路飘移、文字压人物、同场景重播、PPT 框体 > 25% 或连续 > 2 句及静态机位（门禁 A），并要求对最终编码 MP4 抽取迈步/气泡/数据/首尾帧实际目检（门禁 B）。

## 安装方式

将以下链接发给你的 AI 助手即可自动安装或更新：

```text
请帮我安装这个企业培训制课 Skill：https://github.com/hebokenn/kgxc-corporate-course-skill
```

或手动下载 [`kgxc-course-suite-v8.0.0.zip`](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v8.0.0/kgxc-course-suite-v8.0.0.zip) 并核对 `SHA256SUMS`。

> 本版已通过 `check_readme.py`、`test_release_readme.py`、`test_v8_tools.py`、`test_v7_tools.py`、仓库全量回归测试与 `build_release.py` 构建校验，并在真实课程《门店服务体验提升》第 01 节（116 句 / 9,231 帧 / 6 分 35 秒）完成全量 8.0 实渲与门禁 A/B 零错误零警告验证。
