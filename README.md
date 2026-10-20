# 酷果星创课程共创与制作 5.0.0

从原始素材开始，先按ATD教学设计思路拆解工作任务、学习目标、讲解方法、大纲与练习，确认后编写逐字稿，再次确认后分别制作课件或视频。Codex与WorkBuddy使用同一份课程工程和确认记录。

## 安装或更新

从 [v5.0.0 Release 下载可安装更新包](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v5.0.0/kgxc-course-suite-v5.0.0.zip)，同页提供 [SHA256SUMS 校验文件](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v5.0.0/SHA256SUMS)。

解压更新包，双击“安装或更新.command”，默认更新两个宿主中的两个课程模块，保留现有媒体与Aiden配音环境。命令行可运行：

```sh
./install.sh --skill-only --agent both
```

只安装WorkBuddy使用 `--agent workbuddy`。新机器准备完整环境使用 `./install.sh --agent both`，首次需要联网下载媒体依赖和本地Aiden模型。完整环境验证范围为macOS Apple芯片。安装器保护已有自改技能；明确需要替换时添加 `--replace-skill`，安装器先备份再替换。个人配置和课程另存，不放进发布包。

联合包包含 `corporate-training-motion 5.0.0` 与 `elearning-course-design 2.0.0`。在宿主新对话调用统一入口corporate-training-motion，不必手动切换两个Skill。

## 两条交付路线

共同前段：原始资料诊断 → 推荐讲解方法与课程大纲 → 用户确认 → 完整逐字稿 → 用户确认。

| 逐字稿确认后的需求 | 后续流程 | 交付 |
|---|---|---|
| 课件，用于讲授或自行录制 | 独立制作实际课件，完成本次交付 | PPTX/PDF/HTML等课件＋逐字稿 |
| 视频 | 导演拆解画面与动作 → 三个实际视觉风格 → 确认画面与风格 → 配音与画面结合的MP4小样 → 用户确认 → 完整视频 | MP4、SRT、可编辑工程ZIP |

课件交付后可以追加视频需求，从同一份仍有效的已确认逐字稿启动导演，保留原课件。生成的课件及其页面布局、截图、导出图片不作为视频制作基础；视频使用逐字稿和保留的原始素材。原始输入本来包含的PPT可以作为来源。

三个风格使用同一段本课内容制作可查看的画面，说明动作、理由与制作影响。推荐不会自动被选中。小样必须同时有实际配音和画面；只交音频不能完成小样阶段。独立短小样使用pilot用途导出；确认后冻结小样，再制作其余内容并以final用途导出完整视频。课件路线无配音、视频样段或整片前置条件。

## 工作台与恢复

```sh
kgxc-course start ./courses/my-course --title 我的课程 --source ./原始资料.pdf
kgxc-course resume ./courses/my-course
kgxc-course status ./courses/my-course
```

start和resume会核对课程身份、复用或启动服务，并请求默认浏览器打开实际工作台。成功请求浏览器不等于页面已验收；以命令返回的实际URL和可见页面为准。无需先生成视频才能打开工作台，不要直接打开Skill目录中的design.html。

工作台保存分支需求、用户选择、确认原话、时间、关联版本和交付文件。关闭聊天或服务后，在独立新对话提供工程目录即可从文件恢复。修改逐字稿、风格或视频源内容会使受影响确认失效；独立课件的版式变化不影响视频确认。

## 工程与交付

- `inputs/`：保留原始资料。
- `project/design-plan.json`：目标、讲解方法、大纲、练习、来源与缺口。
- `project/source/transcript.md`：两个分支共同使用的逐字稿。
- `project/course-state.json`：当前分支、审阅回执、版本、事件与交付历史。
- `project/director-plan.json`：视频画面拆解、三个风格及预览文件。
- `project/workbench.json`：视频画面、字幕与时间轴。
- `delivery/courseware/`：独立课件和逐字稿；`delivery/`、`packages/`保留当前视频与可编辑ZIP。

双击课程中的“打开课程工作台.command”可恢复。保存后可用 `kgxc-course package COURSE --out COURSE/packages/当前课程工程.zip` 重打包，无需重渲。工程包保留设计、分支、来源、导演预览、确认记录、媒体和独立编辑器。另机仍需相应媒体环境。

## 验证与使用边界

使用方法见[中文指南](docs/USAGE.md)，本次实际检查范围见[V5验收记录](docs/V5-VERIFICATION.md)。独立新对话文件恢复与真实自动压缩后的恢复分别报告。技术导出、主观听看与真实课程学习效果分别验证；技术夹具不构成企业课程批准。

旧v4工程继续原确认流程，安装更新不自动迁移、改写或渲染既有课程。新版保留已批准KGXC品牌头尾、字幕、字体与本地Aiden原速能力。第三方资源与许可见THIRD_PARTY_NOTICES.md。包用于酷果星创内部课程，不含课程原件、个人凭据或模型权重。本说明对应v5.0.0发布包。
