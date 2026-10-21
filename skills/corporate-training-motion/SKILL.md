---
name: corporate-training-motion
description: 酷果星创课程设计与制作统一入口。设计新课或继续制作已有课程；恢复工程后自动核对渲染选路和动作音效，沿用有效确认。先确认教学方案与逐字稿，再交付独立课件或导演视频、风格小样和完整视频。
---

# 酷果星创课程共创与制作

版本 **5.0.3**。共同成果是已确认逐字稿。课件和视频分别制作、分别完成，工作台保存选择、证据、版本与交付记录。安装说明见[INSTALL.md](INSTALL.md)。

## 开工与恢复

新课先运行 `python3 SKILL_DIR/scripts/kgxc_course.py start COURSE --title 课名 --source 原件`，保留原件并默认打开实际工作台。继续制作的首个操作是完整命令 `python3 SKILL_DIR/scripts/kgxc_course.py resume COURSE`；独立工程也可运行 `python3 COURSE/project/editor/scripts/workflow.py resume COURSE`。返回摘要已包含当前分支、确认原话、时间、产物与未决项；从摘要进入当前阶段，再按需读取该阶段参考，沿用有效确认。界面未打开时展示实际URL并使用宿主浏览器能力打开；不要直接打开Skill目录中的design.html。

问题与分析只完成所求。旧版工程保留原流程，不自动迁移或重新渲染。完整字段、命令和分支见[课程工作流](references/28-course-workflow.md)。

用户说“继续制作”“接着做”即恢复并执行当前阶段，不要求重复长提示词。视频分支依据resume返回的`production_handoff`，主动读取当前稿件、导演方案与构图，核对实际能力，选择并接入合适渲染器；必要时保留编辑后升级通用画布，特殊源码保留实际实现。技术选路、动效接入、动作选音及验证由制作端完成，不把这些选择推回给用户，也不停在分析说明。把实际结果写回工程并交付当前阶段产物；只在真正缺少事实、资源或仍需用户确认内容/风格/新小样时询问。既有有效确认沿用，完成或冻结工程不因恢复自动修改。具体判断见[选路](references/30-renderer-selection.md)，声音见[动作音效](references/31-action-sound.md)。

## 共同前段：教学方案，再逐字稿

先读同一安装目录旁的 `elearning-course-design/SKILL.md`，在项目、安装目录或完整发布包中定位实际文件。它负责原始素材诊断、工作任务、学习目标、内容取舍、练习反馈，以及有理由的讲解方法与课程大纲。

第一轮展示具体结构、每章推荐讲法及理由、素材缺口和当前关键选择，请用户确认。按选定方案编写完整逐字稿，区分实际口播、练习引导和制作备注，再请用户确认逐字稿。本阶段不先生成课件，也不设计成片镜头。事实疑义按影响范围澄清，普通素材诊断合并进结构方案审阅。

教学设计写入 `project/design-plan.json`；逐字稿用 `script COURSE --file TEXT` 保存，确认用工作台或 `review COURSE --gate outline|script --evidence 实际原话`。用户明确答复才记录，推荐与沉默不算确认。该模块完成当前设计阶段后返回本主流程。

## 逐字稿确认后的两个独立分支

用户选择用 `branch COURSE --type courseware|video --evidence 实际需求原话` 保存。初始请求已明确形式时，沿用已有授权，逐字稿确认后记录并进入该分支，不重复问已回答的问题。

**课件分支**：根据逐字稿独立制作适合讲授或自行录制的实际课件；按用户格式调用宿主可用的PPTX、文档或网页制作能力并查看生成结果。课件存放 `delivery/courseware/` 或 `project/courseware/`，交付课件与逐字稿即可完成本次任务，无配音、视频小样或整片前置条件。用 `checkpoint COURSE --gate courseware --artifact 相对project的课件路径` 登记交付。不能把逐字稿或分镜表当课件成品。

以后用户提出视频需求，可以从同一份仍有效的已确认逐字稿选择video分支，保留原课件和所有记录。生成的课件及其页面布局、截图、导出图片不作为视频制作基础；视频设计使用逐字稿与保留的原始素材。原始输入中本来就有的PPT可作来源，与本流程生成的独立课件区分。

**视频分支**：启动[导演方法](references/12-director-teaching.md)，从逐字稿拆解画面、动作、镜头、示范和练习反馈，映射教学单元。先提供**三个实际视觉风格**：使用同一段本课内容制作可查看的关键画面，说明动作方式、适用理由、制作影响及推荐。三个方案按本课内容设计，不固定套三套通用模板；推荐不自动选中。

导演方案保存到 `project/director-plan.json`，用 `director COURSE --file PLAN` 导入。请用户同时确认画面方案与所选风格，工作台或 `style COURSE --id 风格ID --evidence 实际确认原话` 保存。

画面实现先读[渲染选路与已接入动效](references/30-renderer-selection.md)，按具体对象变化选择路线。`course_tools.py capabilities`查看实际可用能力；在构图spec中声明`rendering.route=auto`及需要的动效，运行`course_tools.py route --spec SPEC`核对。工作台configure会把逐字、遮罩、模糊、渐变、描线、强调和镜头接入内置动效库并保留整段文字编辑，无需重写桥接。基础图解仍可用简易画布；三维或其他特殊需求须提供实际原生实现。不能从默认画布缺少参数推断整包不支持，也不能忽略未实现的需求后继续出片。

风格确认后，使用本课逐字稿生成**配音与画面结合的有声MP4小样**，含代表性画面、动作、字幕和发音难点，供用户正常速度观看和试听。使用 `workbench.py export COURSE --server URL --purpose pilot`，可导出独立短小样的整条时间线，不必先做完整课程；工作台自动登记，也可用 `checkpoint --gate pilot` 登记外部小样。明确确认后才生成完整配音与完整视频，使用 `--purpose final` 导出完整时间线。已有音色选择沿用；每课小样检查实际发音、节奏及视听配合，最终交付MP4、SRT与可编辑工程包。

## 持续工作台与按需制作

`design-plan.json`保存教学方案，`source/transcript.md`保存逐字稿，`course-state.json`保存当前分支、确认和交付历史，`director-plan.json`保存视频导演方案，`workbench.json`保存视频画面与时间轴。恢复由这些文件计算；改逐字稿后只让受影响确认失效，改变独立课件不应让视频重新确认。未确认小样必须对应当前制作版本；确认后冻结实际小样及共用的稿件、导演风格、声音和字幕样式。后续扩展完整课程不覆盖小样批准；更换共用方案或修改冻结小样会要求复核。

课件分支在交付后显示完成，仍保留以后启动视频的入口。视频分支显示三个风格、实际小样播放器与确认。所有选择写入后端工程文件，不能仅靠聊天记忆或localStorage。

制作时按需加载：[制作方法](references/29-production-method.md)、[工作台契约](references/27-content-workbench.md)、[来源核对](references/01-evidence.md)。新配音默认本地Qwen3-TTS B2清亮平和教学男声，可选其他预设、文字改声或参考音频克隆；本次另选及既有录音优先，见[声音参数](references/23-local-qwen3-voice.md)。完整视频沿用已批准KGXC R5/R8换课名头尾，见[品牌资源](references/11-brand-bookends.md)。字幕、布局、听看和编码沿原制作规范，不用课件翻页代替导演画面。

inputs/project/delivery/packages保持分离。修改Skill先备份；技术检查、主观听看和真实用户认可分别报告。WorkBuddy兼容必须在原生应用验证；独立新对话恢复不冒称已触发真实自动压缩事件。
