# 仓库维护约定

修改 Skill、发布包、主页或发布流程前，阅读并遵循 [Skill 发布流程](docs/RELEASING.md)。

每次功能更新，先把使用场景、具体用法和实际价值补入 README 的介绍部分，再维护版本记录。“版本更新”始终保留为 README 的最后一个内容章节；详细历史与验证链接保存在 `docs/CHANGELOG.md`。

发布前运行 `python3 scripts/check_readme.py`；正式打包入口 `python3 scripts/build_release.py` 也会强制执行同一检查。检查或打包失败立即停止发布，修正后重试；不得用遗留安装包绕过本次失败。

介绍以当前能力为准，保留实际验证范围。仅修改文档或维护流程时，不改动功能版本，也不重建或替换既有版本的发布附件。
