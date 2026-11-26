## 7.1.0：全链路纯对话制课引擎、CourseActorsCute 可动角色与完整能力焕新

**制课 Skill 7.1.0 · DSH 插件 0.11.0**

本仓库定位为**双引擎 AI 企业培训课程生产引擎**（[`elearning-course-design`](skills/elearning-course-design/SKILL.md) 教学设计前端 + [`corporate-training-motion`](skills/corporate-training-motion/SKILL.md) 动效视频/课件后端），将制度 PDF、Word、PPT、扫描件与访谈录音转化为可落地交付的成套课程：

- **专业教学设计 + 零遗漏核对**：建立可定位来源台账、单列关键条件与例外、执行“学员没有原件”检查，按工作触发情境重构自然口播，并在关键决策点弹出带推荐的 1–3 个选项。
- **百种教学动效 × `CourseActorsCute` × 16 套浅色画布**：内置 100 种教学动效、17 类构图母版、F 型视觉扫读引导与可选 Blender 代码化三维道具；全员搭载 3.3 头身可爱可动矢量角色（零滑步步态、防弹膝盖 IK、行进转向与稳态回正、规范工服胸标与便装顾客）。
- **离线 `Qwen3-TTS` 配音 × `1-Beat-1-Audio` 精准对齐**：内置已授权 `didi / pipi` 音色并支持本地音色克隆，企业资料不出本地；`scripts/tts_sync.py` 与 `scripts/verify_delivery.py` 实现按句精准时长同步、48 kHz 原库提示音混音、无标点单行 SRT 与第 0 帧 `attached_pic` 封面自动全检。
- **一套资料多态交付 + 按句局部秒改**：同步支持单支/多集系列 1080p 视频、独立 HTML/PPTX/PDF 课件、《讲义精要》、测验题库与 A4 手写作业；规则修改只重配重渲受影响句，过程文件默认保留。

## 一句话让 AI 帮你安装（最推荐）

把仓库链接发给正在使用的 AI 助手（Antigravity / Claude Code / Codex / Cursor / Windsurf / WorkBuddy）：

```text
请帮我安装这个企业培训制课 Skill：https://github.com/hebokenn/kgxc-corporate-course-skill
```

或按需手动下载压缩包：
- **通用 AI 宿主**：[独立 Skill v7.1.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.1.0/kgxc-course-suite-v7.1.0.zip)（含 `corporate-training-motion 7.1.0` 与 `elearning-course-design 2.1.0`）。
- **DeepSeek Harness**：[DSH 插件 v0.11.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.1.0/kgxc-course-plugin-v0.11.0.zip)。
- 校验清单 `SHA256SUMS` 与 `PLUGIN-SHA256SUMS` 附在下方。

> 本版已核对主页结构检查（`check_readme.py`）、567 项 Python 自动化测试（0 failures / 0 errors，3 skipped）、`test_v7_tools.py`、`verify_delivery.py` 新宣传片全项交付校验及双安装包完整性与 SHA-256。原生 DSH 桌面应用内 UI 点击与 Node ES Module 测试环境（`zod` 依赖未预装）不在本次自动验证范围内。
