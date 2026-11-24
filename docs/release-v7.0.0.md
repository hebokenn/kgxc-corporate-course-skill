## 7.0.0：精简系列课工作流、16 套明亮浅色画布与产出前自查验收

**制课 Skill 7.0.0 · DSH 插件 0.10.0**

- **多集系列课统一批次 + 内容母版三选一**：一门课含多支章节视频及配套《讲义精要》、测验题库与 A4 可打印手写作业时，整门课走统一大纲、统一逐字稿、按内容类型提供每类母版 3 套实质不同方案（`template_masters` + `segments[].template_id`）及跨章节 3 段代表性有声小样，共享视觉/声音/片头片尾并分集导出。历史工程仍兼容逐段三备选模式。
- **16 套精选明亮通透浅色色板**：默认随机选色池升级为 16 套 `random_eligible: true` 的明亮、高对比（WCAG ≥ 4.5）、无绿色浅色系画布；深色画布改为用户明确指定时才启用。
- **代码化自由动画表现**：保留 6.9.8 全部 100 种教学动效与 17 类构图能力，坚持纯代码动态呈现（不调用外部 AI 生图、不用静态人物贴图、产品限定 Apple），按情境释放微表情、路径形变、分屏带练与可视化仪表表现力。
- **产出前实质自查验收（Self-Check Gate）与最小范围局部回改**：面向 Antigravity / Codex / WorkBuddy 等独立宿主精简流程，制作端在交付前完成实质自查修精，成片后改稿只局部重做受影响片段；已存在 `ai-review.json` 的历史工程继续兼容原有门禁。过程文件默认保留，绝不自动删除。
- **本地 Qwen3-TTS `doctor` 检测改进**：支持直接识别本地已就绪的多模式模型目录（`model_paths`）与克隆参考音。

## 选择你的安装方式

- **用 Antigravity / Claude Code / Codex / WorkBuddy / Cursor / Trae / Windsurf 等支持 Agent Skill 的宿主**：[独立 Skill v7.0.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.0.0/kgxc-course-suite-v7.0.0.zip)（含 `corporate-training-motion 7.0.0` 与 `elearning-course-design 2.1.0`，无需打开 DSH）。
- **用 DeepSeek Harness**：[DSH 插件 v0.10.0](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.0.0/kgxc-course-plugin-v0.10.0.zip)。已有版本可用右上角「检查更新」；下载超时可用正式 ZIP 手动安装。
- 安装包校验文件 `SHA256SUMS` 与 `PLUGIN-SHA256SUMS` 附在下方。旧版安装包及 v6.9.8 宣传片、100 种动效图谱保留在原发布页，不替换。

本版已核对主页结构、7.0.0 单元测试（色板、母版分镜、自查工作流与本地语音诊断）、核心回归及双安装包完整性与 SHA-256。原生 DSH 桌面应用内重启与真实课程人工审阅不在本次自动验证范围内。
