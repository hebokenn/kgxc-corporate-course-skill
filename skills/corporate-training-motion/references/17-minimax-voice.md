# MiniMax 连续课程配音

用户明确要求 MiniMax 时使用本流程；不改变新课默认的本地Qwen3-TTS Aiden原速，也不改动冻结旧课原带。Azure 音色ID不能直接传给 MiniMax。先核对当前官方文档和账户可用音色，再选适合课程的中文声音；用户只指定供应商时，可说明选用的实际音色后推进，不虚构跨平台同款。

凭据只用于官方接口认证，保留在安全凭据位置或本次运行内存，不进入源码、命令参数、日志、Skill、交付包。不要输出原始认证头、任务令牌或带签名的下载地址。发送本次获准的学员口播文本，来源台账、制作备注不进入请求。

2026-10-16 实测：中国接口 `https://api.minimax.cn/v1/get_voice`，POST `{"voice_type":"system"}`，Bearer 鉴权，HTTP 200 且 `base_resp.status_code=0` 可读取音色。返回系统音色含 `Chinese (Mandarin)_Gentle_Youth`（温润青年）。这是目录验证，未证明实际合成或音质。

当日官方文档给出的长文本路径：

- 创建：POST `/v1/t2a_async_v2`，正文含 `model`、`text`、`voice_setting`、`audio_setting`；完整课程在接口限制内优先一次连续请求。模型和参数以当次文档为准，不能照搬 Azure SSML。
- 查询：GET `/v1/t2a_async/query?task_id=...`，只查询已创建任务，状态区分 processing、success、failed、expired。
- 下载：GET `/v1/files/retrieve_content?file_id=...`。必须验证下载文件格式、完整解码、实际时长、首尾句和逐段文本覆盖；任务 success 或 HTTP 200 均不能替代音频验收。

**已验证的失败边界：** 创建整课任务返回 HTTP 200，但 `base_resp.status_code=1008`、`status_msg=insufficient balance`、无 task_id。这表示没有创建合成任务，没有音频；记录脱敏状态并停止提交，等待账户额度变化。不能循环重试、静默换声或用旧音轨冒充新生成。任务创建请求超时且结果不明时，先查已有任务，不盲目重发。

记录非敏感的供应商、接口、模型、音色ID、参数、文本哈希、任务ID、实际状态和文件哈希。余额不足时保存待恢复点；成功取得新音频后再重新测量时间轴、对齐单行字幕与动作，旧时长不能复用。

官方资料（2026-10-16 查询；异步合成及下载本次尚未成功验收）：

- https://platform.minimax.cn/docs/api-reference/voice-management-get
- https://platform.minimax.cn/docs/api-reference/speech-t2a-async-create
- https://platform.minimax.cn/docs/api-reference/speech-t2a-async-query
- https://platform.minimax.cn/docs/api-reference/file-management-retrieve-content
