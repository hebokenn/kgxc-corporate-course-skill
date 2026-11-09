# 插件0.8.11 / 核心仍6.7.7 返修失败终止

本地插件窄修，不发布公共附件、不重建既有核心安装包、不重装全局课程Skill。

## 具体行为

旧编排在repair_error返回retry=true后直接进入下一轮，尽管事务未修改文件仍新开学员审阅。本版先保留repair_error，再重抛原repair异常，由现有outer finish路径记为failed并终结。错误登记本身失败时附注而不替换原错误。已有CAS、保护字段与预算控制不变。

制作提示列明原有分镜约束：顶层除segments不得增删改（包括navigation），片段身份、来源、正文摘录及实际选择等六字段和数量顺序保持。只可说明/服从已有导航、调整片段演绎；不能用更名或搬字段更改全局规则。确需禁改内容如实报告另行制作，不提交非法repair。规范issue ID和逐项回应契约继续执行。

## 定向验证

- 真实backend CAS拒绝集成用例在旧host重现原错误被后续重复审阅错误覆盖。
- 修后定向5/5通过：initial拒绝但retry=true时仍failed且仅一个reviewer reserve/invoke；producer-only重试拒绝时原accepted learner、maker QA、监督、提案、repair_error、累计和早先unknown调用保留；正常实际修改仍使用fresh reviewer。
- 完整Node77/77、重点Python27/27通过，无失败或跳过；未变核心沿用既有214项完整Python验证。
- bridge142d、work d134、QA d50及backend/core未变；安装和现场恢复由本机回执另记。

本次未公开发布；已保存文件与技术验证不能代替独立课程审阅或用户验收。
