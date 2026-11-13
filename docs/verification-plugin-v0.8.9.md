# 插件0.8.9 / 核心仍6.7.7 工作与核验切换

本次为本地开发插件修复，公共附件仍0.6.0/6.5.0。核心6.7.7与既有核心安装包保持；未重新安装全局课程Skill。

普通制作曾在原生技能middleware发出完整目录时误判为新对话。工作快照现仅在同一agent、实际pre-step之后，核对当前registry、真实工作目录、可见skill工具和active fiber有效显示策略，并逐字核对原生来源、条目和frame。新真人、claimed伪目录、未知来源、developer输入及其他任务通知继续停止旧任务并保留队列。

从只读QA返回普通工作时，原生SDK可能因目录未变而不再发出完整目录。本分支只从当前可信registry与实际策略派生本轮工作投影，生成新context ID、标明derived来源并分别计数；不会把旧目录当作当前权威，不复用旧ID或改写持久历史。新原生目录优先，不重复追加派生项。

## 已执行定向验证

- `node --test tests/test_native_producer_work_snapshot.mjs tests/test_native_producer_snapshot.mjs`：2/2通过。真实安装SDK内存fixture，36次synthetic dispatch、37次prepare、0网络模型调用。
- 同一agent组合覆盖：pending本课context正常claim → work实际完整目录 → idle → QA d50零工具真实空更新剔除 → 同registry工作恢复时派生当前目录 → 实际job/job_output → idle；新增技能后原生完整刷新保留。
- 工作51工具及toolHistory、原executor/system/config/signal和持久历史保持；目录原生保留/派生/历史排除分别审计。
- 真实/伪造目录、真人/未知输入、旧任务及他人任务拒绝边界已检查。
- 完整Node回归67/67通过，重点Python27/27通过。首次Python命令缺少tests导入路径，失败日志保留；补正PYTHONPATH后完成27项验证，未为该命令错误修改产品。
- 新增预存伪job、他人owner、真实旧job恢复与真实registry移除后拒绝案例。预存通知也要求真实调用、注册、终态、inbox邻接、原producer和registry证明，不能仅凭source.kind放行。
- 制作核验提示明确使用blind_report.items[].id规范ID（如finding:F01），区分裸finding ID；每条问题在现有报告字段回应修复、证据不匹配或待核验。执行/CAS逻辑不变。
- QA helper d50与后端保持原哈希；未变化核心沿用既有214项完整Python验证。打包及冷安装由本轮本机回执另记。

该fixture验证实际SDK准备和执行边界，未发送真实模型请求，不能据此声称现场课程已修复。现场恢复、自动审阅与实际课程质量分别验证。全部旧失败、未知用量、原模型通道和课程过程文件保留；本次未公开发布。
