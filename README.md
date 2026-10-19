# 酷果星创企业课程制作 Skill

面向酷果星创同事的内部课程制作工具。保留企业品牌、业务术语与案例，把资料整理、逐字稿、教学分镜、Aiden 原速配音、动画、字幕和审核串成一条流程，并为每门新课内置可编辑工作台。

## 快速开始

**先准备能正常使用的 Codex。** 在 Mac 的“终端”执行安装命令；不需要打开课程工程，也不需要 GitHub 账号。

<!-- INSTALL_COMMAND_START -->
```bash
/bin/bash -c 'set -euo pipefail; curl -fsSL https://raw.githubusercontent.com/hebokenn/kgxc-corporate-course-skill/v3.4.0/install.sh | /bin/bash'
```
<!-- INSTALL_COMMAND_END -->

安装器会：

1. 把 `corporate-training-motion` 安装到 `~/.agents/skills/`，保留已有本地修改。
2. 准备独立 Python 环境、媒体/图片/QA 软件包、Playwright 浏览器和网页渲染依赖。
3. 检测 ffmpeg、ffprobe、Node.js；有 Homebrew 时自动补装缺项，没有时给出操作提示。
4. 自动部署 Qwen3-TTS / Aiden 本地环境和固定版本模型，生成一条中英数字短句确认推理可用。
5. 写入**本机自己的**运行配置和 `~/.local/bin/kgxc-course`，最后显示逐项检查结果。

**安装 Skill 与完成所有制作准备是两件事。** 安装器不登录 Codex，不填写 Key，不自动安装 Blender。完整安装会下载数GB的本地配音模型，请保持联网并预留磁盘空间。下载仓库后可执行 `bash install.sh --skill-only` 仅安装 Skill；它不能单独完成视频导出。只需编辑已有录音时可执行 `bash install.sh --skip-voice`，跳过模型部署并明确标为仅媒体环境就绪。

安装后在 Codex 新建对话，输入 `$corporate-training-motion`。没有出现时重启 Codex。可在终端运行：

```bash
"$HOME/.local/bin/kgxc-course" doctor
"$HOME/.local/bin/kgxc-course" demo "$HOME/Documents/酷果课程试用" --verify
"$HOME/.local/bin/kgxc-course" serve "$HOME/Documents/酷果课程试用"
```

第三条命令会打印本地网址；在浏览器打开即可改字幕、时间轴、画面文字、图片和裁剪区间，再保存、导出。第二条使用包内真实预生成 Aiden 音频，验证编辑导出链路，**配音是否可用于新文本，以安装结束的 Aiden 生成检查为准**。

## 能做什么

适合门店业务流程、商品与材料核对、制度讲解、系统操作、排班协作及企业案例课程。画面按内容选用实物、截图、日历、图表、插画、流程或泳道，不强制整课大地图。

输出有声 MP4、单行无标点 SRT、可编辑工程 ZIP、实际画布源码、素材和 QA。工作台支持区间试听、画面/声音/字幕同步裁剪、停留顺延、撤销、保存历史、素材替换及再次导出。字幕改文案不会自动重配音。

完整课程保留酷果星创批准的 R5 片头、R8 片尾、固定问候与结束语。片头课名由内置合成器替换，三维母版另提供 Blender 文件。内容、视觉、样片、最终课程的审核仍由课程负责人确认，技术检查不替代审核或听校。

## 适用环境

- 推荐并实际验证：**Codex 桌面端，本地执行，macOS Apple 芯片**。
- 本机验证版本：macOS 27.2 arm64，Codex 自带 CLI `0.163.0-alpha.10.2`；隔离媒体环境使用 Python `3.12.13`。这不是对这些软件最低版本的推断。
- 安装器只将 macOS arm64 的完整环境作为已验证范围；Windows、Linux、Intel Mac、其他 AI 工具和纯网页/云端运行**未验证**。仅复制 Skill 不等于这些平台的完整制作已获支持。
- 不依赖另外两个 Skill；导演方法、网页/插画引擎、品牌和工作台已合并在本包。无需另装 HyperFrames、花叔等 Skill。

## 安装前准备

| 准备项 | 用途与要求 | 安装/检查 |
|---|---|---|
| Codex 和可用模型账号 | 必需；能在本地读写文件、执行命令。模型权限、费用和额度以你的账号/组织为准 | [官方开始使用说明](https://learn.chatgpt.com/codex)。先确认能正常对话并执行一个本地文件任务 |
| macOS Apple 芯片电脑 | 本版完整安装验证范围；系统其他版本需先运行 doctor | “关于本机”检查芯片；终端 `uname -m` 应为 `arm64` |
| 互联网 | 首次安装下载公开仓库、Python 包、浏览器和 npm 包；网络受限时先解决下载访问 | GitHub、PyPI、npm、Playwright、Hugging Face 下载地址可访问 |
| Homebrew | 当本机缺 ffmpeg/Node 时需要；已齐全则不要求 | [Homebrew 官方入口](https://brew.sh/)。按官网完成安装，重新开终端运行 `brew --version` |
| Qwen3-TTS | 新配音依赖；默认 Aiden、原速 1.0，完整安装器自动部署并检查 | [Qwen3-TTS 官方项目](https://github.com/QwenLM/Qwen3-TTS) |
| Blender | 请安装；用于打开/修改随包三维片头片尾工程。例行更换课名由脚本完成，无需三维重渲 | [Blender 官方下载](https://www.blender.org/download/)。已验证 5.2.2 LTS；能打开 `assets/bookends/blender/` 中工程 |
| ffmpeg、ffprobe、Node.js、npm | 编辑音轨、编码、探测与网页渲染；安装器检测并通过已有 Homebrew 补齐 | `ffmpeg -version`、`ffprobe -version`、`node -v`、`npm -v` |

完整依赖链与来源见 [依赖说明](docs/DEPENDENCIES.md)。

Python、Playwright、numpy、Pillow、SciPy、fontTools、OpenCV 和 Node Playwright 的发布版本在 `requirements.lock`、`config/package-lock.json` 锁定。本地配音运行器单独安装，版本见 `requirements-voice.lock`，模型仓库与固定提交见 `config/voice-model.json`。安装器使用 uv 准备独立 Python；不会把软件包装进你的系统 Python。Node Playwright 的依赖声明要求 Node >=20；本机实测 Node 25.8.1。

默认流程不要求单独购买云 TTS、云渲染或 API Key。可选的 Azure 旧配音适配器、AI 生图或其他外部服务只有在明确选用时才需要相应账号、授权和可能的计费。Remotion 是保留的可选静音原型，未纳入默认安装；使用前自行核对其许可，不能当成默认有声课程管线。

## 安装结果与配置

成功时会显示 Skill 路径、快捷入口和“编辑导出环境：就绪”。完整安装须同时显示“编辑导出环境：就绪；Aiden 原速配音：就绪”。Blender、Codex 登录是人工准备项，不会由安装器假定完成。

默认位置：

| 内容 | 位置 |
|---|---|
| Skill | `~/.agents/skills/corporate-training-motion/` |
| 独立运行环境、安装记录、更新备份 | `~/.local/share/kgxc-course/` |
| 本机配置、检查记录 | `~/.config/corporate-training-motion/` |
| 快捷命令 | `~/.local/bin/kgxc-course` |
| 你制作的课程 | 你指定的目录，例如 `~/Documents/酷果课程/` |

安装器不改 shell 启动文件。若 `kgxc-course` 命令找不到，使用上文带 `$HOME/.local/bin/` 的完整命令。支持 `XDG_DATA_HOME`、`XDG_CONFIG_HOME`、`COURSE_CONFIG_DIR` 和安装参数 `--dest`、`--data-dir`、`--config-dir`、`--bin-dir`；路径可有空格。

重复安装不会覆盖现有配置值。未修改的旧 Skill 更新前留有备份；检测到本地修改会停下，只有显式 `--replace-skill` 才备份后替换。失败后修复提示中的缺项，再运行同一安装命令即可。

`config/tools.example.json` 是无凭据示例；正常安装无需手填。本地 voice.json 由安装器生成，不含 API Key。只有明确维护旧 Azure 配音时才参考 `config/azure.example.json` 和 `.env.example`，将真实值设置为本机环境变量。安装器不读取或上传真实 Key。不要提交 `.env`、Cookie、Token、账号密码、私钥或本机配置。

## 手动安装

1. 下载[仓库源码 ZIP](https://github.com/hebokenn/kgxc-corporate-course-skill/archive/refs/tags/v3.4.0.zip)并解压，或使用下面命令克隆固定版本。
2. 进入包含 `install.sh` 的目录。在终端执行 `bash install.sh`；只复制 Skill 执行 `bash install.sh --skill-only`。
3. 如果安装器本身无法运行，手动将 `skills/corporate-training-motion` **整个文件夹**复制到 `~/.agents/skills/`。不要只复制 `SKILL.md`，也不要把它放进多一层的同名目录。
4. 打开 Codex 新对话，通过 `$corporate-training-motion` 调用。仅复制文件时，媒体环境仍需准备；能运行 Python 后，可在下载目录执行 `bash install.sh`，继续检测并安装运行环境（或先安装 uv，再运行 `python3 scripts/install.py`）。

有 Git 的同事可在终端逐行执行：

```bash
git clone --branch v3.4.0 --depth 1 https://github.com/hebokenn/kgxc-corporate-course-skill.git
cd kgxc-corporate-course-skill
bash install.sh
```

团队工程也可放在 `<课程工作目录>/.agents/skills/corporate-training-motion/`。该结构符合 [Codex 官方 Skill 发现规则](https://learn.chatgpt.com/docs/build-skills)。避免同时在个人目录和当前项目装同名副本，否则可能出现两个入口。

## 首次制作课程

先把 Word、PDF、制度正文、原始图片放在单独资料目录。打开一个可写课程工作目录，调用：

```text
请使用 $corporate-training-motion 为酷果星创制作《收货核对流程》内部课程。
原始资料在我提供的文件中，以原文为准，不新增业务规则。
先整理规则台账和逐字稿，交给我确认，再设计分镜并制作有声样片。
新配音用 Qwen3-TTS 的 Aiden 原速，字幕单行无标点，标题按内容保留。
按内容选择画面，流程和多人交接可优先采用流程图或泳道图。
完整课程使用已批准 R5/R8 片头片尾并替换课程名。
从建档开始打开内置工作台，最终交付 MP4、SRT、可编辑工程 ZIP 和检查结果。
```

最小示例可用快速开始中的 `demo`，它自带约9秒录音、3个场景、22个可编辑字段与2张图片，适合先熟悉编辑和导出。企业资料、业务术语和品牌不需要替换成通用占位内容。该演示不是对真实制度的业务审核，也不代替完整课片头片尾。

正常课程流程：资料核对 → 规则/逐字稿确认 → 导演与分镜确认 → 有声样片确认 → 整课与工作台编辑 → 编码/布局/内容/听校 → 最终确认交付。审批由实际负责人完成，Skill 不把模板里的审核状态自动设成通过。

课程目录为 `inputs/` 原件、`project/` 唯一制作工程、`delivery/` 当前视频与字幕、`packages/` 当前可编辑包。工程 ZIP 内置 `project/editor/scripts/workbench.py`，解压后可继续编辑；新电脑仍需媒体运行环境。

更换片头课名：

```bash
"$HOME/.local/bin/kgxc-course" bookends --title "收货核对流程" --subtitle "酷果星创门店课程" --out "$HOME/Documents/收货课程包装"
```

## 更新与卸载

更新到本仓库指定版本：重跑该版本的安装命令。运行环境会检查并复用，已安装依赖按锁文件补齐；用户配置值保留，更新前 Skill 备份留在运行数据目录。更新不会修改已制作的课程或自动重渲旧视频。

卸载时在下载后的仓库目录执行：

```bash
python3 scripts/install.py --uninstall
```

这会把本安装器管理的 Skill、启动器和安装记录移至 `~/.local/share/kgxc-course/uninstalled/`。课程、个人配置、配音环境、运行时与更新备份保留。手动复制的安装可手动移走对应 Skill 文件夹；不要删除其他 Skill。

## 常见问题

- **显示 Skill 已装好，但导出环境尚未就绪**：根据 doctor 的 missing 项操作；常见是缺 Homebrew/ffmpeg、网络无法下载浏览器，或已有配置指向失效环境。不要把本机配置示例误写为真实路径。
- **找不到 Skill**：确认完整目录和名称，开启新对话，必要时重启 Codex；检查同名项目/个人副本。
- **浏览器启动失败**：重跑完整安装。默认使用随安装器准备的 Playwright Chromium，不要求你恰好装着开发者电脑上的 Chrome。自选 Chrome 时在本机 tools.json 设置 `browser_channel=chrome`。
- **运行环境已就绪，仍无法生成新配音**：配音依赖 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)，完整安装会自动部署。检查是否加了 `--skip-voice`，或模型下载失败；重跑同一命令可继续下载，安装器不会自动换声音。包内样例音频仅验证媒体链路。
- **标题换课后仍显示旧课名**：用 `bookends` 命令生成到新目录，将实际片段接入课程；不要直接把 profile 中带烘焙标题的历史片段冒充新课包装。
- **裁剪后如何恢复**：当前会话用撤销；已保存版本可从工作台“历史”恢复为草稿。原始音轨和素材不会被裁剪操作覆盖。剪到说话内容时核对剩余字幕。
- **下载失败或公司网络拦截**：确认 GitHub/PyPI/npm/Playwright 下载可访问；可改用仓库 ZIP 手动安装。不要把代理密码或内部证书私钥写进仓库。
- **想用 Windows、其他 AI 工具或云端**：本版未验证完整制作，先不要承诺可用；可依据文档自行试验并记录实际结果。

## 目录说明

```text
install.sh                         一条命令的启动入口
scripts/install.py                 安装、更新保护、卸载
requirements.lock                  Python 媒体依赖版本
config/                            无凭据示例与 Node 锁文件
skills/corporate-training-motion/
  SKILL.md                         唯一课程制作入口
  agents/                          Codex 显示名称与调用提示
  scripts/                         工作台、生成、检查与快捷命令
  workbench/                       字幕、时间轴、同步裁剪、导出
  assets/profiles/kgxc/             酷果品牌、角色与历史批准资产
  assets/bookends/                  可换课名的 R5/R8 包装与 Blender 源工程
  libraries/                       已融合网页/插画引擎及原许可证
  examples/quickstart/              真实有声最小技术样例
  references/                      教学、动效、品牌、字幕与审核细则
tests/                             安装、重复执行和配置保留测试
docs/                              依赖、版本变更与验证记录
```

公开仓库用于方便酷果星创同事安装。企业品牌、角色、业务内容继续用于酷果星创内部课程；第三方代码、字体及其他资产按各自原许可使用，见 [第三方与素材说明](THIRD_PARTY_NOTICES.md)。模型权重放在使用者数据目录，私人课程工程、认证凭据、日志、缓存和开发者个人配置不随包分发。

实际验证范围与未验证项见 [验证记录](docs/VERIFICATION.md)。

## 下载与版本

[公开仓库](https://github.com/hebokenn/kgxc-corporate-course-skill) · [3.4.0版本与安装包](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v3.4.0) · [Skill ZIP](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v3.4.0/corporate-training-motion-v3.4.0.zip)
