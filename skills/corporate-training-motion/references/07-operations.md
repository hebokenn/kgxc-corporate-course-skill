# 实施与复验入口

以SKILL.md为唯一入口，按本次任务读取相应参考。创建工程：

```sh
python3 scripts/scaffold.py courses/COURSE_ID
python3 scripts/validate.py courses/COURSE_ID/project --stage analyze
python3 scripts/export_traceability.py courses/COURSE_ID/project
python3 scripts/export_storyboard.py courses/COURSE_ID/project
python3 scripts/check_visual_plan.py courses/COURSE_ID/project
python3 scripts/check_visual_plan.py courses/COURSE_ID/project --require-evidence
python3 scripts/check_course_completeness.py courses/COURSE_ID/project --stage script
python3 scripts/check_course_completeness.py courses/COURSE_ID/project --stage storyboard
python3 scripts/workspace_check.py courses/COURSE_ID
```

scaffold只生成模板，不生成录音或成片，非空目标拒绝覆盖。原件入inputs/；project.json中的source_file从project/相对指向它。填真实规则、稿件、分镜、疑义和用户确认后按任务推进。新云调用按用户授权，已有冻结声音只读复用。

模板默认启用content_contract_version=2，预置固定结束语，但仍须在其前补全讲稿。逐页填source_images.json；选地图时才填写knowledge_maps.json，否则maps为空；按[可选关系图与原图保留](18-relationship-maps-and-source-images.md)绑定分镜。validate.py在script及之后阶段自动检查；盘点pending、信息图无分镜去向、关系图未绑定或末句缺失不能通过。文本型资料可无图，但仍须逐页记录确实无图，不编造素材。此检查不会自动观看图片/视频或验证实际配音。

新建/重做视觉统一执行包内导演及视觉动作方法，直接使用内部工具，不再加载其他Skill。生成的visual_plan_version=2分镜模板必须填观众理解、图示动作、镜头理由和实际场景选择；空模板不能过检查。qa/assessment-status.json分开记录规则覆盖、结构、导演视觉、成片；qa/visual-evidence.json绑定关键帧和连续动态小样。证据检查不是机器视觉认证。历史冻结课程不自动迁移。

制度更新先以rule_id与条款比较新增、删除和变化，保留生效来源及例外。按影响范围更新稿件→音轨/对齐（如需要）→动画→下游QA。视觉修改不自动改口播；用户明确只留最终版时按工作区清理规范收尾。

具体课程自己的README记录实际依赖、预览/绘帧/审计/渲染/打包命令。结构验证器不能代替课程引擎QA或业务审阅，也不能拿模板数据过门禁冒称成片完成。发布和外发依照用户本次授权。
