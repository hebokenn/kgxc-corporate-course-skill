# 全课内容演绎、逐段备选与三段抽样

5.9.0 起新视频课程使用 `planning_workflow=storyboard-v1`。共同前段仍是教学方案和逐字稿确认；独立课件不增加视频前置条件。旧工程保持原确认算法，用户明确要求改用本方法时才运行 `planning`，保留有效逐字稿、历史方案和原小样。

## 先解决整课怎样讲，再花费生成动态样段

这是前期分镜设计与分阶段验证：分镜审阅回答整课覆盖和讲解选择，动态小样验证实际实现。一个漂亮片段不能代表整门课。普通表现选项先以文字分镜和粗构图说明，需要看材质、角色或布局才少量制作关键帧；不先把全部候选渲染成视频，也不先制作整课再挑好看的三段。

1. 将**全部已确认口播及练习、答案反馈**拆为语义完整的教学片段。按原稿顺序完整覆盖；标题、来源和制作备注不冒充口播。问候、虚构声明或过渡语并入相邻的完整教学情节；不要把半句话或只有人物入场的标签拆成独立抽样单位。长段可以含连续镜头，但三种备选都须说明整个片段。
2. 每个教学片段至少写**三种有实质差别的画面表现**。逐一列原文、教学目的、开场状态、可见变化、结果、焦点、是否用人物、所需素材/能力、预计成本、风险和推荐理由。差异应改变理解路径，例如实物状态变化、因果路径、前后比较；仅换色、换图标或换入场方向不算三种。
3. 共同美术规范单独记录配色、字体、图形材质和气质。同一课程可以混用人物演绎、物件操作、信息图、流程推导和对照；不是从这几种方法里选一种套全课。人物出现规则依据本课和用户偏好，不把“概念一律无人”写成所有课程的通则。
4. 提供可查看的全课分镜表。用户可逐段选择，也可明确采用推荐组合；推荐不能自动选中。**全部片段有明确选择、全课分镜确认后，才进入三段动态抽样。** 批量选择和整课确认可引用同一次明确授权，不要求用户重复表达。
5. 在已确定方案的完整片段中**分层随机抽取三个不同片段**。有情境与概念时各抽一个，第三个优先在剩余高风险实现中补未覆盖类型；没有对应类别时优先补未覆盖类别，再从其余片段随机。随机种子、候选池、选中ID和原因落盘；同一计划恢复不重抽。重新抽样记录原因；不能反复抽到容易片段，失败片段保留问题并修正。少于三个完整片段时说明范围，不能复制同一段凑数。
6. 仅制作这三个**完整、有声、有字幕、有真实变化**的片段，展示彼此的原文、选中表现和实际区间。可组合为一个可导航MP4或三个独立播放项；当前内置导出用一个含三段的时间线。与正式制作共用生产画布、运行时代码及素材，不另写简化示范。开头立即有可识别信息；保留完整教学情节及必要的声音/场景衔接，不能裁掉停顿问题后才提交。抽样同时覆盖读图和讲解连贯性，未抽中的目录、章节交接与密集信息段另外低成本检查，不能替换随机结果或要求用户额外审批。逐段检查动作开始、运动中和停稳后的主体、支撑关系、遮挡与字幕，正常速度听看。段长按实际完整口播决定，不硬压成固定秒数。
7. 用户确认当前三段小样后再生成整课。三段仅是代表性验证；公布未覆盖表现类型和未抽中高风险段，整课仍逐段验收。修改段落或表现使相关分镜选择失效；共同美术、声音或运行时代码改变后重新核对受影响小样，不重签教学稿批准。

5.9.1新视频的每种备选还须按[阅读与信息节奏](45-reading-and-information-pacing.md)说明独立信息组、动作与稳定阅读时长、焦点顺序和结果保留方式；全课声明 `reading_contract=reading-pacing-v1`。动态样段同时验证读图与回看条件，动作数与空档不证明学员读懂。6.0中稳定阅读可与相关旁白重叠，分镜分别设计动作、信息和讲解节奏；动作结束不必换字，保留比较结果并只移动焦点。计划停顿写明学员任务与实际提示，不按阅读缺口批量加静音。

## 数据与命令

`project/storyboard.json` 使用 `course-storyboard/1`：

- `script_sha256` 绑定当前逐字稿文件；`visual_direction` 含 palette/typography/graphics/atmosphere。
- `presentation_policy` 为本课可选约定，如 concept_characters=false、scenario_characters=true。
- `segments[]` 含 id、unit_id、source_paragraph_ids、script_excerpt、teaching_goal、kind、risk（normal/high）、assessment_ids、options、recommended、recommendation_reason、selected。
- `options[]` 至少三项，含 id、method、opening、action、result、focus、characters（布尔）、feasibility、cost、risk_note、difference。不要把规划中尚未验证的能力写成已经实现。
- `selected` 初始为 null。选择凭据由 `choose-shot` 或工作台写入，导入文件里的自填选择不会当成用户批准。

段落ID由 `workbench/storyboard.py` 的 `paragraphs(text)` 产生；匹配 `【口播】` 和 `【练习引导】`，遇制作/来源备注停止。一般纯文本按非空段落处理。导入前检查提取范围，非标准稿件显式排除元数据；不能删原稿来消除覆盖错误。

```sh
# 仅对用户要求升级的旧v5视频工程执行；新建工程已启用
python3 SKILL_DIR/scripts/kgxc_course.py planning COURSE --evidence 实际升级授权
python3 SKILL_DIR/scripts/kgxc_course.py storyboard COURSE --file STORYBOARD.json
# 分别选，或用户明确采用推荐组合时批量选
python3 SKILL_DIR/scripts/kgxc_course.py choose-shot COURSE --id S01 --option B --evidence 实际选择
python3 SKILL_DIR/scripts/kgxc_course.py choose-shot COURSE --id all --option recommended --evidence 实际批量选择
python3 SKILL_DIR/scripts/kgxc_course.py review COURSE --gate storyboard --evidence 实际全课分镜确认
python3 SKILL_DIR/scripts/kgxc_course.py sample COURSE
```

抽样保存到 `project/storyboard-samples.json`。默认自动生成随机种子；`--seed` 用于可复现验证，生产中先记录理由再固定种子，不能通过挑种子选择结果。`--redraw --evidence 原因` 才能重抽当前有效计划。

工作台的“制作与交付”展示全课原文与备选，逐段保存或批量采用推荐后确认。`project/storyboard.html` 是可离线查看的只读审阅表，源数据继续保留；不能把HTML存在当作动态预览已通过。

## 样段必须连接实际生产时间线

抽样后将选中片段编排进 `workbench.json`，加入 `storyboardBindings`：

```json
[{"segment_id":"S01","option_id":"B","script_excerpt":"该片段完整原文","startFrame":0,"endFrame":600,"sceneIds":["scene-1","scene-2"]}]
```

每条连接实际场景和完整源帧区间；三个片段区间不重叠。用同一个编辑器的 `workbench.py export COURSE --server URL --purpose pilot` 导出。系统在开始渲染前检查分镜批准、抽样计划和导出范围，编码后写入视频、分镜、种子计划、实际画布和源码哈希。缺少绑定回执、换成自选片段、裁掉一段或用外部演示片冒充时不能登记为当前小样。绑定证明可追溯，**不证明人物动作自然、配音正确或观感合格**。

小样审阅后 `review COURSE --gate pilot --evidence 实际有声小样确认`；扩展整课时每条已选分镜都连接实际场景，`--purpose final` 检查全量覆盖。新增画面不修改已冻结小样，可新增素材；已抽样使用的素材ID、路径或字节改变会使相应小样确认失效。新的素材与实现仍按整课质量规范验证。

## 验证时避免伪造批准

用现有课程验证时，主工程只写入真实获得授权的内容和确认。需要测试后续批准/抽样/导出时，在隔离副本中使用明确 `qa-operator` 的测试凭据，报告为技术模拟。不得把测试选择、自动批准、合成媒体或代码检查写回主课作为用户认可；真实主课保留待审阶段。
