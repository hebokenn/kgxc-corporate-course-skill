## 7.1.0：无界面对话制课工作流、CourseActorsCute 可爱人物与全新展示页

**制课 Skill 7.1.0 · DSH 插件 0.11.0**

- **对话优先的无界面制课流**：移除冗余浏览器表单 `design.html` 与网页时间轴编辑器 `index.html`，所有立项、逐字稿确认、母版三选一与局部返修直接在 AI 对话中完成；底层保留无头 `/renderer.html` 与 Playwright 导出引擎。
- **公共音画同步与交付校验 CLI（`scripts/`）**：新增 `tts_sync.py`（兼容 `Qwen3-TTS` 24-bit WAV 精确时长校准与尾音静默/截断检查）与 `verify_delivery.py`（一键核对分辨率、帧率、48 kHz 音轨、零标点单行 `.srt`、单帧 `attached_pic` 封面与 Frame-0 MAE）。
- **全面启用 `CourseActorsCute` 可爱矢量人物**：3.3 头身可动矢量引擎（讲师、双色系员工制服、便装顾客）彻底替代静态 PNG 人物与旧版 `acting.js`。
- **主页全面焕新与历史归档隔离**：主 `README.md` 与 GitHub Pages 首页替换为全新制作的 44.19 秒 `v7.1.0` 宣传片与 3 张架构/角色/16 套明亮浅色板展示图；过往 v5/v6 界面截图、17 支历史样片与旧版宣传片统一归入独立归档页（`docs/ARCHIVE.md` 与 `archive.html`），仅供查阅历史版本。

## 安装与下载

- **用 Antigravity / Claude Code / Codex / WorkBuddy / Cursor / Trae / Windsurf 等支持 Agent Skill 的宿主**：[独立 Skill v7.1.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.1.0/kgxc-course-suite-v7.1.0.zip)（含 `corporate-training-motion 7.1.0` 与 `elearning-course-design 2.1.0`）。
- **用 DeepSeek Harness**：[DSH 插件 v0.11.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.1.0/kgxc-course-plugin-v0.11.0.zip)。已有版本可用右上角「检查更新」；下载超时可用正式 ZIP 手动安装。
- 校验清单 `SHA256SUMS` 与 `PLUGIN-SHA256SUMS` 附在下方。历史版本演示与旧版安装包仍保留于各自 Release 与仓库归档页。

> 本版已核对主页结构检查（`check_readme.py`）、567 项 Python 自动化测试（0 failures / 0 errors，3 skipped）、`test_v7_tools.py`、`verify_delivery.py` 新宣传片全项交付校验及双安装包完整性与 SHA-256。原生 DSH 桌面应用内 UI 点击与 Node ES Module 测试环境（`zod` 依赖未预装）不在本次自动验证范围内。
