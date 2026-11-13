# 插件0.8.1 / 核心6.7.1 实机边界修复验证

2026-11-07，本地开发修复。0.8.0完成210项回归与最小原生API验证，首次实际恢复课程时已自动触发独立审阅；创建阶段被零工具保护阻止，未形成模型审阅。这一失败保留，不改称成功。公共版本仍为0.6.0/6.5.0。

## 实机差异与修复

真实DSH会给新Agent注册本地团队工具，并加入required运行上下文。restrict空名单只过滤继承工具，原实现误把自有注册表的非空定义当成最终模型工具暴露。现在保留注册表供宿主管理，而只读执行器始终输出空schemas、拒绝全部执行；全局guard及最终assemble/request的零工具检查保持。精确Agent的只读提示词适配层清除运行上下文副本，refresh后再核验，不修改其他Agent或全局provider。

新会话header已保存中性cwd时不再重复workingDirectory.set，避免额外目录消息。create完成后模型可见历史必须为空，任何角色的已有消息都拒绝；实际assemble后再核对，防止延迟注入。

仅失败会计允许真实调用前审计无invocation/request，必须明确preflight与model_invoked=false；用量保留{}，不补零，累计预算预约次数不回退。已构造请求但是否发出未知时保留unknown/null；真实返回的部分用量照实累计。成功审阅仍必须有真实调用记录，失败会计不能用来提交通过。界面区分调用预算与实际推理明细。

## 已完成验证

- 已配置媒体Python运行 `python -B -m unittest discover -s tests -v`：**162项通过**。其中新增8项失败会计边界，以及Chromium中的预算/未调用/未知用量呈现验证。
- `node --test tests/test_*.mjs`：**58项通过**。包含四阶段自动衔接、只读身份、制作端返修、监督与真实停止、持久预算及原生服务契约。
- 本机安装的DSH 0.2.2-rc.1真实TeamService、Team工具插件、WorkingDirectoryService、Agent/Loop/Session/Tools/Prompt服务回归：4次合成模型流，**联网/真实模型推理0次**。实际注册包含9个团队工具和1个延迟测试工具；送入模型的tools=[]、局部工具执行0，team:identity、目录和延迟required context被隔离。回归中的普通Agent上下文与工具保持正常。
- developer/message、system/message、tool/result三种创建时注入均先证明进入可见历史，再被历史检查在stream之前拒绝；合成流次数没有增加。全局上下文、额外工具schema和pre-step注入的阻断继续覆盖。
- 真实后端预留在preflight失败后落为failed/not_invoked，calls不减、usage={}且无totalTokens:0；hold期间仅允许失败会计回写，不能新启动审阅或审批。

## 安装与能力边界

使用标准冷安装与完整重启；版本、源文件字节、包清单及SHA分别核对。本机安装回执和实际课程日志单独保存，不把私人课程正文、原件或影片写入本报告或公共包。

当前仍沿用codex-chatgpt / gpt-6.1-sol / xhigh和ChatGPT登录，不改provider配置或自动切换收费来源。文本/图片理解不能充当连续全片看听；相关关键项仍可为无法验证并阻塞。开发测试、实际课程审阅、用户确认和正式交付分别记录。全部过程与历史失败保留。
