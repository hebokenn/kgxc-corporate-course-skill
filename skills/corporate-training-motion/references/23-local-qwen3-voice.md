# 本项目默认配音：本地 Aiden

用户于2026-10-19试听全部5个男声后确认，后续Skill新配音默认使用 **Aiden｜清亮中音，美式英语男声**。用户试过慢速版后明确选择原版速度。适用于本项目的课程、代码视频与口播；本次明确另选、已有录音和冻结课程优先。

- 模型：`mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16`，本地MLX推理。
- `speaker=Aiden`，`language=auto`，`instruct=None`；不附加慢读/风格指令，中英文不换声。
- 原版自然语速1.0；不使用`atempo`、时长拟合或按目标时长拉伸音轨。1.0是保持原速的记录，不是模型API的`speed`参数。
- 已试听参数：`temperature=0.65`、`top_p=0.9`、`repetition_penalty=1.05`、`seed=20261019`；`stream=False`。同一seed仍不代表跨环境逐字节相同。

本机运行器位置和非敏感默认值保存在安装目录外的 `~/.config/corporate-training-motion/voice.json`；不要把开发机绝对路径、模型权重或凭据塞入Skill包。脚本可读取该配置并进入已有Python环境；不会安装依赖、下载权重或静默改用系统声/云服务。

```sh
python3 scripts/qwen3_tts.py --dry-run
python3 scripts/qwen3_tts.py --text-file APPROVED_TEXT.txt --out VOICE.wav
```

输出不存在才生成；WAV及相邻JSON记录实际模型、音色、参数、时长和哈希。生成文件是待试听产物，不代填用户验收。仅音频任务不启动视频制作流程。

长文在合理长度内优先连续生成；需要拆分时按少量完整语义段处理，保持同一配置并实听衔接，不机械逐句合成或默认逐章拼接。达到token上限、异常长静音、重复/漏读都不能当作成功；核对首尾句、中英数字及内容覆盖，再安排字幕和画面。已观察到本机长流式输出可能后半段近静音，因此默认非流式，仍需检查实际输出。

旧Azure资料仅在用户明确选择或维护旧课时加载；不得因旧教程或配置里仍有025、Gemini、系统声而覆盖本次Aiden偏好。本机模型或环境不可用时报告实际缺口，不另换声音。


3.4发布安装器默认自动部署独立本地配音环境与固定模型版本，写入用户配置并验证中英数字短句。此处的推理脚本仍为离线生成，不在课程生成时静默下载。官方模型项目为<https://github.com/QwenLM/Qwen3-TTS>；安装版本和模型提交在发布仓库requirements-voice.lock及config/voice-model.json。
