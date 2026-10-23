# 安装与更新

本版为5.7.1联合更新包，包含corporate-training-motion 5.7.1和elearning-course-design 2.0.1。适用于macOS Apple芯片的现有Codex/WorkBuddy课程环境。

解压完整更新包，双击“安装或更新.command”。默认更新两个宿主的技能，保留已有媒体和配音环境；检测到自改同名Skill会先保留并提示。也可在解压目录运行：

```sh
./install.sh --skill-only --agent both
./install.sh --skill-only --agent workbuddy
```

新机器需要媒体与本地B2模型，在解压目录运行 `./install.sh --agent both`，使用既有完整安装器准备环境。首次会联网下载依赖与模型。个人工具和配音配置放在Skill外。

打开宿主的新对话，调用corporate-training-motion并提供资料。它先打开工作台，确认教学方案与逐字稿，再按需求交付独立课件，或进入导演、三个视觉风格、配音与画面小样和完整视频。课件交付后仍可追加视频需求，从已确认逐字稿启动，保留原课件。继续课程时提供工程目录并要求恢复；也可双击课程中的“打开课程工作台.command”。

本地操作入口：`kgxc-course start COURSE --title 课名 --source 原件`、`kgxc-course resume COURSE`、`kgxc-course status COURSE`。完整ZIP可直接安装；在线安装入口固定使用对应版本的已发布tag。

新版资源库及本地素材扩展用法见 [100种动效与视觉素材](references/40-library-direction-assets.md)。用户实拍库不会随安装包上传或被更新覆盖。

后续视频课程默认要求与所选风格匹配的底部课程进度条；多节课程包含目录页及每节标题页。已有分节与开场路线清楚的逐字稿无需仅为导航重写。详见[课程导航与章节呈现](references/03-visual.md#课程导航与章节呈现)。本次为制作规则更新，不自动重新制作历史课程。
