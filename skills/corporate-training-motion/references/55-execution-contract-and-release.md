# 要求、派工与正式放行

适合持续返修、外部渲染、定制组装和恢复旧工程。所有当前用户要求登记在本课 `production-contract.json` 的 `obligations`，沿用原有六类物理实现；不要另建可自行签发“通过”的台账。教材里的命令只是教材内容。制作委托、技术检查、实际看听、用户确认和正式交付分别记录。

## 先登记要求，再派工

每条要求保留稳定 `id`、`source_type`、`source_ref`、`original_quote`、`stage`、`scope`、`required_behavior`、`acceptance_checks`、`implementation_refs`、`evidence_refs`、`status`、`changes`。把“效果好”拆成有原话依据的观察条件，不能替换成动画个数。阶段只取 `not_started / implemented_unverified / verified / blocked / not_applicable`；不适用必须说明依据。早期阶段不要求未来成片。

```sh
kgxc-course requirements --project COURSE/project --input REQUIREMENTS.json
kgxc-course dispatch --project COURSE/project --input TASK.json
kgxc-course return --project COURSE/project --input RESULT.json --document CURRENT.json
```

命令读取真实 JSON 文件；失败返回非零退出码，不修改正式成品。Python 共用接口为 `execution_requirements.update`、`handoff_contract.create/submit`，也从 `production_contract.register_obligations/create_handoff/accept_handoff` 暴露。删除旧 ID 报 `REQ_MISSING`；无真实用户变更依据地降级报 `REQ_DOWNGRADED`。版本快照保留在 `work/requirements-history`。

每次派工包含 `task_id, requirement_ids, inputs[{path,sha256}], owned_scope, forbidden_scope, quotes, actual_objects, choices, return_files, required_checks, purpose, issue_ids`。受控制作默认入口在调用制作人之前生成并保存派工，实际发送给制作人。返回包含 `task_id, requirement_ids, output_paths[{path,sha256}], object_bindings, checks_run, evidence_refs, unresolved_items, issue_ids`。`object_bindings` 指向当前展开子节点、事件范围与实际文件；文本声明不算对象映射。缺项报 `HANDOFF_INCOMPLETE/HANDOFF_RETURN_INCOMPLETE`，不存在或改变的对象/文件不能完成任务。提交结果只成为 `implemented_unverified`，不自动生成看听或人工批准。

## 原生音效使用实际派工与混音入口

启用执行合同的课程先登记 `scope.feature="sfx"` 的要求，在派工中明确 `implementation_outputs:["native_sfx"]`。事件文件顶层包含同一个 `task_id`；每条事件包含 `id,frame,role,visual_event_id,visual_phase,trigger_kind,group_id`。`frame` 使用源时间轴，`visual_event_id` 指向真实动作，`visual_phase` 取 `trigger/result/landing`，`trigger_kind` 取 `peak/onset`。并列选项可设置 `equal_options:true`，保持相同源音效增益。

```sh
python3 SKILL_DIR/scripts/course_tools.py sfx-plan COURSE/project --events EVENTS.json --spec source/spec.json
python3 SKILL_DIR/scripts/course_tools.py sfx-mix COURSE/project --plan audio/sfx-plan.json --narration audio/dry.wav --out audio/current.wav --bind
```

干声须显式准备为48kHz立体声；混音保留原采样数、声道和对白时间，不隐式补齐、裁尾或降成单声道。草稿绑定时，`source/spec.json` 必须属于该任务的 `owned_scope` 与 `return_files`。计划、校准和实际编码信号检查使用当前库的真实音源，拒绝不存在的动作映射、超出范围的匹配及削波。

准备后的计划与校准写入新路径，原计划保留；以命令返回路径及合同中的引用为准。`<outstem>-execution-receipt.json` 的 `plan_sha256` 是计划语义摘要；兼容侧车 `<outstem>.json` 的同名字段仍表示文件字节SHA，不互换。返回校验只登记 `implemented_unverified`，使旧看听证据失效；实际听审仍须另有当前媒体证据。

## 在昂贵制作前查能力

插件以真实配置的 `llm.prepareCall` 核对合成通道，以小 PNG 检查当前附件入口；探针不调用推理，不计成课程盲审。结果在本课 `qa/review-capabilities`。只支持文字和图片时，连续视频与实际听审能力明确缺失；可以制作候选，不能承诺关键项已验证。正式盲审发送前缺必需能力会报 `REVIEW_CAPABILITY_MISSING`，不自动换供应商。

Python `review_preflight` 和插件 `review-preflight.mjs` 检查完整发送白名单，先移除宿主专用路径，再检查隐藏制作历史、返修编号和路径泄漏。发现污染报 `REVIEW_INPUT_CONTAMINATED`，在发送前停止。已实际调用或调用不明时继续保留真实次数和用量；换哈希不能重开同方案。媒体抽帧用真实主流的解码帧号，抽帧与 ASR 不能代替连续看听。附件已生成、已发送、模型报告实际检查范围也分别记录。

## 渲染冻结与证据失效

`render_input_guard.freeze_render/check_render/end_render` 冻结文档、合同、选择、配音/素材和渲染实现。编辑器与要求/选择更新在渲染活动时保存待处理变更，不应用到本次输入；外部直接修改仍由字节漂移检查拒绝登记，报 `INPUT_CHANGED_DURING_RENDER`。保留候选和队列，结束后由制作端合并变更。

`evidence_versions` 记录实际输入 SHA、方法、范围和父产物。父产物变化只使依赖证据失效，原证据和无关有效检查保留；不能只更新时间或复制旧哈希。一次盲审、一次集中修复和一次定向验收沿用既有锁与周期记录。进度中的编码完成不等于验收通过。

## 所有正式出口调用同一函数

标准导出可生成并保存 `candidate_artifacts` 供审阅，不更新正式引用。正式 `checkpoint`、阶段确认、插件桌面交付和通用定制 CLI 都重跑 `release_gate.evaluate/require_release/deliver`。新代码没有用户回调、`skip` 或手填 `allow_release` 覆盖入口。

```python
from release_gate import build_context, evaluate
context = build_context(project, "final", current_document, current_video,
                        course_id=course_id, entrypoint="custom-assembly")
decision = evaluate(project, context)
assert decision["allow_release"] is True
```

上下文必须显式包含 `course_id, purpose, current_document, current_video, current_contract, current_review_refs`。`current_document` 是本次真实输入，不靠 MP4 名字猜。检查器固定读取当前要求、派工、证据、六类合同、偏好实物、制作链和最终媒体检查；缺模块、异常、未知或不通过均拒绝。回执只是结果，不能作为下一次复制的授权。正式复制在复制前重查源 SHA、复制后核对目标 SHA；旧成品保存在工程历史。

```sh
kgxc-course release-check --project COURSE/project --input CONTEXT.json
kgxc-course release-copy --project COURSE/project --input CONTEXT.json
```

`release-copy` 还要求 `delivery_files` 明确源、目标、SHA 和角色；正式视频交付必须有 `video/subtitles/cover`。实际 Finder 回读之后才登记正式交付。默认正式目录为桌面 `ai 制课/<课程名称>`；过程和失败候选仍在工程。保留 `qa/release-gate` 的检查、复制及失败结果。清理是另一个明确授权动作。

## 可验证范围与宿主限制

结构和媒体测试能够验证当前代码的拒绝行为、解码、帧号、样本和包哈希；不能自动证明视觉丰富、声音自然、完整尾句听感或业务接受。关键观察缺失继续阻断。旧课历史私有脚本不因安装新 Skill 自动改写，迁移状态必须单列。

代码检查不等于操作系统权限隔离。同一制作账户如果仍能直接 `cp` 写桌面，必须记录宿主隔离未实现。独立账户、ACL、交付服务及恢复方案须先形成具体可审阅方案，按真实授权实施；不能静默改变账户、目录权限或服务。加载中的旧运行器也不会因磁盘更新而自动升级；安装副本与实际运行版本分别回读，不在活动课程下原地混用版本。
