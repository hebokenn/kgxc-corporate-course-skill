# 安装与更新

本版为5.0.0联合更新包，包含corporate-training-motion 5.0.0和elearning-course-design 2.0.0。适用于macOS Apple芯片的现有Codex/WorkBuddy课程环境。

解压完整更新包，双击“安装或更新.command”。默认更新两个宿主的技能，保留已有媒体和配音环境；检测到自改同名Skill会先保留并提示。也可在解压目录运行：

```sh
./install.sh --skill-only --agent both
./install.sh --skill-only --agent workbuddy
```

新机器需要媒体与本地Aiden模型，在解压目录运行 `./install.sh --agent both`，使用既有完整安装器准备环境。首次会联网下载依赖与模型。个人工具和配音配置放在Skill外。

打开宿主的新对话，调用corporate-training-motion并提供资料。它先打开工作台，确认教学方案与逐字稿，再按需求交付独立课件，或进入导演、三个视觉风格、配音与画面小样和完整视频。课件交付后仍可追加视频需求，从已确认逐字稿启动，保留原课件。继续课程时提供工程目录并要求恢复；也可双击课程中的“打开课程工作台.command”。

本地操作入口：`kgxc-course start COURSE --title 课名 --source 原件`、`kgxc-course resume COURSE`、`kgxc-course status COURSE`。本地更新包不依赖尚未发布的远端tag。
