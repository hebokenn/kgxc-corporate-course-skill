## 7.3.0：纯净 Skill 化、移除 DSH 插件并打通纯对话原件覆盖确认

**核心 Skill `corporate-training-motion 7.3.0` · `elearning-course-design 2.1.1`**

本版彻底移除 DeepSeek Harness（DSH）桌面插件及旧工作台残留锁，回归纯粹跨平台的 Agent Skill 工作流：

- **移除仓库 DSH 插件，保留唯一历史备份入口**：删除主仓库内所有 DSH 插件源码、构建/安装脚本与插件测试，仅在 [`docs/ARCHIVE.md`](https://github.com/hebokenn/kgxc-corporate-course-skill/blob/main/docs/ARCHIVE.md#%E5%8E%86%E5%8F%B2-dsh-%E6%A1%8C%E9%9D%A2%E6%8F%92%E4%BB%B6%E5%AE%89%E8%A3%85%E5%A4%87%E4%BB%BD%E5%B7%B2%E5%81%9C%E7%94%A8%E4%BB%85%E4%BD%9C%E5%8E%86%E5%8F%B2%E5%AD%98%E6%A1%A3) 保留 `v7.2.0` 历史插件包备份链接。
- **打通纯对话 / CLI 原件覆盖确认**：`source_coverage.py` 与 `workflow.py source-coverage` 支持通过对话或宿主结构化提问记录真实用户确认并绑定当前 SHA-256，不再卡死在不存在的 `dsh-user-click` / 网页按钮上。
- **全平台开箱即用**：适配 **Antigravity、Claude Code、Codex、WorkBuddy、Cursor、Windsurf、Trae**，无需安装或重启任何桌面插件。

## 安装方式

将以下链接发给你的 AI 助手即可自动安装或更新：

```text
请帮我安装这个企业培训制课 Skill：https://github.com/hebokenn/kgxc-corporate-course-skill
```

或手动下载 [`kgxc-course-suite-v7.3.0.zip`](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v7.3.0/kgxc-course-suite-v7.3.0.zip) 并核对 `SHA256SUMS`。

> 本版已通过 `check_readme.py`、`test_release_readme.py`（16 项）、`test_source_coverage` / `test_source_coverage_gate` / `test_streamlined_v700` / `test_blind_review` / `test_stage_confirmation` / `test_studio`（89 项）、`test_install.py`（7 项）、`test_v7_tools.py`（3 项）与 `build_release.py` 构建校验。
