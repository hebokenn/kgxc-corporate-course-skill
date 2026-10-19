# 酷果星创同事安装说明

完整说明、依赖、更新和卸载见[仓库中文README](https://github.com/hebokenn/kgxc-corporate-course-skill#readme)。

推荐在macOS Apple芯片电脑的终端复制这一条命令：

```bash
/bin/bash -c 'set -euo pipefail; curl -fsSL https://raw.githubusercontent.com/hebokenn/kgxc-corporate-course-skill/v3.4.0/install.sh | /bin/bash'
```

完整安装自动准备Skill、媒体环境及Qwen3-TTS Aiden本地模型，生成短句检查配音。需要联网下载数GB模型；Codex登录和Blender安装仍需本人完成。配音项目：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)；请安装[Blender](https://www.blender.org/download/)用于三维工程编辑。

手动使用本ZIP：把整个`corporate-training-motion`文件夹放到`~/.agents/skills/`，在Codex新对话中调用`$corporate-training-motion`。仅复制Skill没有准备运行环境，仍推荐执行完整安装。不要只复制SKILL.md，不要覆盖已有修改过的同名Skill。

安装完成后运行`~/.local/bin/kgxc-course doctor`，确认编辑导出和Aiden配音状态。制作的课程与个人配置在Skill外保存，更新不会自动改变旧课程。
