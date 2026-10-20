# 交付与校验

## 按深度交付

结构设计一般只需一份可读方案和来源/取舍表，不为简单大纲制造十几个文档。包含受众、工作任务、目标、模块、练习方向、媒介、估计学习量和当前选项。取舍表用 Markdown、CSV 或 JSON，原页/段/时间码可追溯。

课件分支的逐页稿建议字段：`页面ID/单元、学习动作/目标、学员可见内容、讲解稿、图/演示/素材、学员操作、答案/评分与反馈、来源/示例标记、估时`。不是每页都要互动，但关键能力要有合适检验；知识回顾不代替操作。全课保留稳定ID以支持删改。

制作包包括完整学员稿/旁白、案例练习及反馈、素材需求、媒介/交互逻辑、选择记录和未决项。要 PPTX 等才按要求制作实际文件；不把分镜表冒充成品课件。

## 已确认逐字稿与分支

共用前段先交教学分析、推荐讲法与大纲，确认后交完整逐字稿。逐字稿确认后：课件分支生成实际课件并交付逐字稿；视频分支把逐字稿和原始素材交给导演，三个风格确认、有声画面小样确认后生成整片。课件不作为视频制作基础；以后追加视频时复用仍有效的逐字稿确认。

## design-plan.json

需要结构化交接时复制 `assets/design-plan.json`。这是教学设计数据，不能直接当视频渲染数据。v2使用schema_version=2，兼容检查旧schema_version=1。

- `sources`：`id,title,location,kind`，可加`sha256,pages`。来源存在不自动证明事实正确。
- `objectives`：`id,statement,evidence,criterion`。评价标准未知可标“建议，待选”，不偷偷设公司及格线。
- `units`：`id,title,objective_ids,source_refs,disposition,teaching_method,teaching_reason,media,media_reason,activity`。取舍为`core/optional/job_aid/separate/omit`。
- `assessments`：`id,objective_ids,task,criteria,feedback`。结构阶段任务应可执行，逐字稿阶段补全实际题目、答案和纠错反馈，两个分支均沿用。
- `source_refs`：对象数组，各含`source_id,locator`，例如`{"source_id":"S01","locator":"PDF第7页"}`。教学补充/虚构练习单独说明假设。
- `decisions`：`id,question,finding,options,recommended,selected,status,evidence,blocking_for`。选项各含`id,label,impact`。无选择为`selected:null`；`status`为`open/confirmed/delegated`；`blocking_for`列`courseware`和/或`production`，或空数组。
- `issues`：`id,detail,state,blocks`，可加`source_refs,resolution`。`state`为`open/resolved/mitigated`；`blocks`为`none/courseware/production`。缓解需具体做法。
- `handoff`：`ready_for_courseware,ready_for_production`。校验器只报告，不自动改成就绪或代替授权。

v2的`stage`为`outline/script`；完整逐字稿由`script_file`引用，相对设计JSON定位。旧schema_version=1保留outline/courseware与courseware_file。仅存在不证明内容完整，需检查全稿及格式渲染。

## 复核

来源、条件、例外能回溯；核心单元对齐目标，目标有任务和反馈；取舍有去向，确认有证据；课件能指导制作且交互适配媒介；记录数据当前性、小屏/字幕/图表需求、素材缺口及估时基础。

运行 `check_design.py`检查结构和引用。它不能判断教学质量、业务正确、真实用户回答或学习效果；仍需人工复核与试学。仅要大纲时，大纲完成即完成当前请求，不为就绪伪造已定稿、已试学或已发布。
