# Azure 配音接入

本页保留Azure接入及旧课设置。2026-10-19起，新配音默认已改为[本地Qwen3-TTS Aiden原版语速](23-local-qwen3-voice.md)，不再自动调用Azure。下述025选择只适用于已确认旧课或本次明确选择Azure的任务，不因默认更新重做历史课程。

历史课程使用 Azure，区域 southeastasia。上一轮曾选择云涵 Dragon HD Flash：`zh-CN-Yunhan:DragonHDFlashLatestNeural`；用户已完成重新试听，并以“用25”确认本排班课使用025：`zh-CN-Yunxiao:DragonHDFlashLatestNeural`。声音以项目最新确认记录为准，不能因为私人配置仍保留旧值就认定用户已选定。

私人非敏感配置默认位于 `~/.config/corporate-training-motion/azure.json`；Key 存 macOS 钥匙串，脚本通过配置中的 service/account 引用读取。不要将 Key 放入工程、命令参数、日志或分发包。可移植部署支持明确指定环境变量名，凭证值留在环境中。

```sh
python3 scripts/azure_tts.py --voices --allow-cloud
python3 scripts/azure_tts.py --text-file APPROVED_TEXT.txt --out VOICE.wav --allow-cloud
```

授权 flags 表示实际已有授权，不是获取授权的办法。正式课程只发送已确认的口播文本；资料上传和云渲染另行授权。用户现已授权配置 Azure 及这次通用试听。

macOS 用系统 curl/SecureTransport 验证 HTTPS，与 Python 默认 CA 库不一致时仍保留证书验证；密钥经 stdin 配置送入 curl，不进入 argv/文件。单次请求失败或超时不自动重试，先核实结果，防止重复收费。输出已存在则失败，不能覆盖获批音轨。

音频要求实际 WAV、非空波形，记录采样率、时长、哈希、请求声音。REST 返回没有词级时间戳，本适配器不假装提供精确字幕对齐；之后做人工语句锚点或核验过的 SDK/对齐工具。LatestNeural 是更新别名，保留已批准的原始 WAV，不重新生成后冒称完全一致；resolved_model_version 未返回则 null。

当前先用自然语气，不添加未经验证的 prosody/rate/style 参数；调整讲师语气后再试听。声音区域列表、成功响应与试听验收分别记录。

## 连续课程配音

当前排班课程禁止改回Google声线；本排班课已确认025 Yunxiao轻盈版，按项目authorization.json生成新版整课旁白。完整讲稿在服务时长限制内时，优先在同一voice节点的一次请求中生成全课，保留原始WAV，统一响度后才提取时间戳；不要按章节分别生成后拼成不同音色。

长请求可显式使用`--request-timeout 600`，仅延长等待，不自动重试或切换其他声音。微软REST最长输出10分钟，超长会截断；开工前估计时长，收到响应后检查实际时长、首尾句、逐章文本覆盖和异常长静音。超过服务限制时另行选用支持长音频的接口，不能无提示按章节回退。完整WAV保持连续，不为章节跳转而插入固定空白。

字幕和动画共用新音频上的口播锚点；整段做本地转写核对重复/漏读、首句和末句，并在章节边界抽听检查。必要的修复应是原带上的可审计局部编辑，保持原带哈希；不能仅凭HTTP200声称无断句或无声线变化。

调用参考飞书的“固定声音、正文纯口播、整段先生成、音频落盘再驱动画面”的思路，接口与SSML采用微软实际协议。飞书示例的Gemini模型名、style字段和响应解析不能复制到Azure请求里。

官方资料（2026-10-14 核验）：
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/high-definition-voices
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech

企业固定问候语：欢迎来到酷果星创企业培训课堂。使用用户本轮确认的声音，与正文连续生成并配入无声片头，只出现一次；按真实音频时长对齐，必要时延长片头末帧。

## 重新选声与完整试听

从当前区域目录读取 Gender=Male 且主语言为中文或 SecondaryLocaleList 含中文的声音，按中文本底与其他多语男声分组，同名不同模型保留独立ID。用户要求全部试听时，目录不能只给少数推荐声线；每款使用同一段文案、相同音量处理和独立播放器，不自动轮播或替用户选声。记录实际请求Voice ID、文本和音频哈希；接口不可用明确标注，不能用另一音色补位。已确认HTTP429且本地没有音频时，可在核查后做一次有记录的补试；超时等结果不确定的请求不得直接重发。

用户确认新声音后，固定问候语、正文和片尾统一跟随同一声音；不得拼接旧版片头旁白，避免课程中途出现音色变化。
