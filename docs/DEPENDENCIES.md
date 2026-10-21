# 依赖与安装范围

媒体完整安装验证范围为本地 macOS Apple 芯片。v5.0.0同时安装到Codex与WorkBuddy；教学设计、文件恢复和确认记录使用同一标准库工作流及本地浏览器，WorkBuddy的实测范围单独记录。以下依赖沿用已验证环境，除明确有上游声明者外，不推断最低版本。

| 环节 | 实际依赖 | 安装方式/版本依据 |
|---|---|---|
| 理解资料、业务台账、逐字稿、导演和审核 | 可用的 Codex 模型账号，本地执行权限 | 人工登录；账号费用、额度和模型授权以组织实际配置为准；[官方入口](https://learn.chatgpt.com/codex) |
| Skill 发现 | Codex 的 `.agents/skills/<名称>/SKILL.md` | 默认安装至用户 `~/.agents/skills`，也可放当前项目；[官方规则](https://learn.chatgpt.com/docs/build-skills) |
| 安装运行器 | Bash、curl、tar；uv 0.11.21 | macOS 自带前三项；缺 uv 时从官方固定版本安装到用户数据目录，不改 shell 配置；[uv 官方安装](https://docs.astral.sh/uv/getting-started/installation/) |
| 媒体 Python | CPython 3.12.13 | uv 管理的独立解释器；不要求用户先装 Python，启动时无可用解释器会引导下载 |
| 工作台服务/字幕/保存 | Python 标准库 | 随媒体解释器；仅监听 127.0.0.1，不提供公网编辑服务 |
| 浏览器预览、逐帧渲染 | Python playwright 1.63.0、greenlet、pyee、typing-extensions；专用 Chromium | 安装器读取 `requirements.lock` 并执行 `python -m playwright install chromium`；[官方浏览器说明](https://playwright.dev/python/docs/browsers) |
| 网页运动引擎 | Node.js、npm、playwright-core 1.63.0 | `config/package-lock.json` 固定 npm 依赖；上游包元数据声明 Node >=20，本机实测25.8.1。缺 Node 时尝试已有 Homebrew |
| 编码、剪辑、混音、探测 | ffmpeg、ffprobe | 实测9.0.2；缺项时尝试已有 Homebrew；[FFmpeg 官方](https://ffmpeg.org/download.html)、[Homebrew](https://brew.sh/) |
| 插画、字体、波形、布局与运动 QA、换课片头 | numpy2.5.4、Pillow12.3.0、SciPy1.18.1、fontTools4.67.0、OpenCV5.0.0.93 | 具体传递依赖见 `requirements.lock`，安装到独立媒体环境 |
| 新文本配音 | [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)，MLX Audio0.5.9、MLX/MLX Metal0.32.4、transformers5.20.1、soundfile0.14.0等 | 默认完整安装自动创建单独配音环境，依赖及传递依赖见 `requirements-voice.lock`；实测 Apple 芯片本地推理；[运行器官方说明](https://github.com/Blaizzy/mlx-audio) |
| 配音模型 | `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16` | 固定提交 `7d3824abff87e49756bb0f83fb5411de75d160c4`；完整安装从[模型仓库](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16)下载约4.2GB，权重在用户数据目录，不放 Git；B2 原始生成1.0、保音高交付1.1；其他预设与参考克隆需相应变体，见[配音指南](VOICE.md) |
| 品牌包装换课名 | 包内批准R5/R8背景、原配乐、中文字体、跟踪参数、`scripts/bookends.py` | 无需开发者的外部工程。保持背景动作和音乐，更换课名；重编码会产生正常编码差异，不承诺视频字节与历史片段相同 |
| 三维源工程修改 | Blender5.2.2 LTS已验证 | 请人工从[官方入口](https://www.blender.org/download/)安装；内置两份已打包外部图片的 `.blend`；一般换课名用合成器，无需重渲三维 |

## 关联 Skill 和可选服务

企业课程入口只有 `corporate-training-motion`。网页与插画实现已经复制融合至 `libraries/`，随包保留许可证，不在制作时下载另外两个 Skill，也无需 `npx hyperframes`。内部运动/插画报告用于诊断，最终检查仍执行企业课程门槛。

- 默认录音、编辑、渲染和导出本地运行，无需额外 TTS API Key 或付费云渲染。
- Azure 旧适配器仅在主动指定时使用，需要相应订阅和环境变量；示例见 `config/azure.example.json`、`.env.example`。本版未验证真实云调用。
- MiniMax仅保留明确另选供应商时的历史接入指引，需要相应账号、有效余额和安全凭据；不纳入默认安装，本版未完成真实合成验收，不覆盖当前选定默认声音。
- AI 生图、远程资料抓取或另选外部服务，需要目标工具对应权限，可能产生费用；不自动开通或上传内部资料。
- `templates/remotion` 是保留的静音原型，需要自行安装其声明依赖并核对许可；不进入默认安装，不宣称完成有声课。
- 三维几何可在 Blender 编辑；完整品牌后期仍由包内标题合成器完成，不承诺单靠 Blender 复现全部后期。

## 资源和账号边界

网络需要访问 GitHub/codeload、astral.sh、Python发行下载源、PyPI包文件、npm、Playwright浏览器下载源、Hugging Face模型和文件下载源。首次建议为模型、两套Python环境、浏览器、Skill及课程输出预留至少10GB空闲空间，这是容量建议而非实测系统最低要求。

安装器不会自动登录 Codex、获取模型调用额度、安装 Homebrew 或 Blender，不修改系统 Python、不改 shell 启动文件、不上传课程。若 ffmpeg/Node 缺失且没有 Homebrew，先按提示安装 Homebrew，再重跑同一命令。默认模型为公开下载，不要求填写 Hugging Face Token；公司网络限流或拦截时先解决下载连接。

`--skill-only` 只安装文本、脚本与资源；`--skip-voice` 准备媒体环境并跳过模型。只有默认完整安装通过实际短句生成，才标记所选配音就绪。
