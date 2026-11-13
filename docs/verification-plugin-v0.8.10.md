# 插件0.8.10 / 核心仍6.7.7 中文服务响应

本次本地插件修复，不发布公共附件、不重建核心安装包、不重新安装全局课程Skill。

## 具体问题与变更

本机Python服务通过stdout返回UTF-8 JSON。旧bridge以output += Buffer逐块隐式解码，汉字跨data边界时会产生U+FFFD；stderr同样处理。原文件正常与模型实际输入损坏可以同时出现，因此不能只按坏引文去改原稿。

本版仅在stdout/stderr的data监听前启用setEncoding('utf8')，让流维护跨块解码状态。原12MiB响应限制、4000/1500错误截断、超时、取消及调用路径保持。工作helper d134、QA helper d50、后端/core及模型通道不变；旧失败、未知用量和失真报告保留，新输入另行核验。

## 已执行定向验证

- 真正callReview/callTool→invoke→真实子进程，自造70KiB JSON在一个中文字符的三个UTF-8字节间分次write。旧实现review stdout、tool stdout与中文stderr三项失败；已有大小/无效JSON/超时/取消四项通过。
- 新实现node --test tests/test_bridge_unicode.mjs：8/8通过（7子项与父项），完整中文响应SHA一致，并检查错误截断、超大响应、无效JSON、超时/取消真实child退出。该测试无真实模型网络调用，不触私课。
- 完整Node75/75、重点Python27/27通过，无失败或跳过；未改变核心沿用既有214项完整Python验证。
- 只读字节审计已将真实历史native损坏逐字段复现为64KiB独立解码结果；原文件正常而实际输入失真。受影响的当前审阅在修后重验，正文与有效内容确认保留。
- 打包、冷安装和修后真实payload对比由本机本轮回执单独记录。旧报告不因修复而追认有效。

本次未公开发布。
