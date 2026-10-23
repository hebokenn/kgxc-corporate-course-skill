# 分支课程工作流 v5

共同前段：原始素材→ATD教学分析、推荐讲法和大纲→确认outline→逐字稿→确认script。逐字稿确认后，选择独立课件或导演视频。v5新工程使用course-workflow/2和design-plan schema_version=2；v4工程保持旧流程，不自动迁移。

## 操作与恢复

`python3 SKILL_DIR/scripts/kgxc_course.py start COURSE --title 课名 --source 原件` 建档并默认打开工作台。`resume COURSE` 从文件恢复实际阶段、分支、选择、产物和未决事项，复用或启动后台服务。输出的WORKBENCH_IDENTITY已核对课程ID、根目录与版本；WORKFLOW_STATE_URL是实际/api/workflow接口，不必猜接口或重读后端。

主要命令：

```sh
python3 SKILL_DIR/scripts/kgxc_course.py design COURSE --file DESIGN.json
python3 SKILL_DIR/scripts/kgxc_course.py review COURSE --gate outline --evidence 实际确认原话
python3 SKILL_DIR/scripts/kgxc_course.py script COURSE --file TRANSCRIPT.md
python3 SKILL_DIR/scripts/kgxc_course.py review COURSE --gate script --evidence 实际确认原话
python3 SKILL_DIR/scripts/kgxc_course.py branch COURSE --type courseware --evidence 实际交付需求
python3 SKILL_DIR/scripts/kgxc_course.py checkpoint COURSE --gate courseware --artifact ../delivery/courseware/课件.pptx
```

课件交付自动随附该版逐字稿，状态为已交付；技术登记不是代填用户批准。格式可为真实PPTX、PDF或HTML，按用户需要使用宿主现有制作工具，查看实际生成文件。默认保留可编辑格式。课件文件仅存delivery/courseware或project/courseware，避免进入视频源码和媒体指纹。

后来用户要求视频时：

```sh
python3 SKILL_DIR/scripts/kgxc_course.py branch COURSE --type video --evidence 实际追加视频需求
python3 SKILL_DIR/scripts/kgxc_course.py director COURSE --file DIRECTOR.json
python3 SKILL_DIR/scripts/kgxc_course.py style COURSE --id STYLE_ID --evidence 实际画面和风格确认
python3 SKILL_DIR/scripts/kgxc_course.py checkpoint COURSE --gate pilot --artifact 视频小样相对路径.mp4
python3 SKILL_DIR/scripts/kgxc_course.py review COURSE --gate pilot --evidence 实际有声画面小样确认
```

课件、确认记录与逐字稿保留。视频输入限定已确认逐字稿与登记的原始素材；已生成课件及其截图、页面布局、导出图不作为视频基础。已交付课件的重命名副本同样不能伪装成原始素材。原始输入中的PPT仍可作为来源核对。

风格确认后可配置实际视频画布，按真实语音定时，先运行`workbench.py export COURSE --server URL --purpose pilot`导出有声画面小样。小样可以独立构成短时间线，不必预先制作整课。确认后扩展完整课程，保留已冻结的小样文件与共用方案，再用`--purpose final`导出完整时间线。完整导出检查pilot确认；纯WAV不能替代小样。导出完成后登记final实际文件并交付，不再增加固定的中间审批。主观听看和业务用户认可仍分别报告。

## 教学与逐字稿

前置模块是同一安装根目录下的elearning-course-design。每个核心单元有teaching_method和teaching_reason，显示推荐讲法与理由，并与目标、示范、练习和反馈对应。素材诊断与大纲放同一轮审阅；实际事实缺口才按范围澄清。

设计用schema_version=2，stage为outline或script；script_file指向逐字稿。逐字稿只包含实际讲解、案例、练习引导、答案反馈、衔接与收束；来源与制作备注单列。保存不会自动确认。主要用户决策依然用decisions，gate可为outline/script/style/pilot；独立课件与完整视频是交付记录，不伪造为用户审阅。

issues可加gate和branches，将只影响视频的素材问题限定到style或pilot及video分支；事实问题仍在共同前段处理。普通待选项可按当前阶段展示1—3项。已有明确需求与确认沿用，沉默和推荐不构成批准；用户授权按实际范围记录。

## 导演交接

project/director-plan.json至少包含：

- basis: approved-transcript；script_sha256: 当前逐字稿文件SHA-256。
- inputs: role为transcript或original，path是相对project的实际文件路径；transcript必须包含当前script_file，original只能指向登记的原始输入。
- script_excerpt: 从本稿抽取同一段内容供三个风格对比。
- beats: 每项有id、unit_id、script_excerpt、picture、action、assessment_ids；覆盖核心单元及练习反馈，不增加稿中不存在的台词。
- style_scope: 新方案为 `visual`，表示三选一只决定美术规范。旧工程未声明时继续原确认算法，不自动迁移。
- styles: 恰好三个不同ID，每项有id、title、rationale、visual、production_impact、preview_file。`visual` 含非空文字 `palette`（配色）、`typography`（字体与层级）、`graphics`（图形与材质）、`atmosphere`（画面气质）；不再要求每个风格选一种motion。预览为实际SVG/PNG/JPEG/WebP或HTML，三份画面内容不同，并由导演检查视觉差异。
- recommended: 推荐风格ID，仍保持未选择，直到收到明确选择。

可用`python3 -c`计算脚本SHA-256。导演负责根据内容创造三种方案，不按固定全课模板或只换三种配色。`style_scope=visual` 时，风格选择绑定当前稿件、三种美术规范和实际预览；分镜beats更新不会让视觉选择失效。未确认小样仍须与当前完整画布和声音一致。批准绑定冻结的实际MP4、逐字稿、视觉规范、声音、字幕样式和实际渲染源码。全片可以增加或组合不同场景、动效和镜头；动作编排标识language和核心动作清单protectedEffects不再被当作视觉批准的范围。protectedEffects仍检查明确要求保留的动作是否实际存在。改变美术规范、声音、字幕样式、渲染源码或冻结MP4会使受影响批准失效。整片导出继续绑定它自己的完整导演方案、当前画布、声音及源码，新增镜头不会使未渲染的新版本冒充已有成片。未声明style_scope的旧方案按原算法判断，不静默重签历史确认。

## 工作台与文件

- design-plan.json：教学分析、大纲、讲法、目标、练习、来源、选择。
- source/transcript.md：两分支共享的逐字稿。
- course-state.json：分支、确认、版本、产物和历次交付；工作流工具写入。
- director-plan.json：视频专用导演与三风格方案。
- workbench.json：视频画面、音轨、字幕、时间轴。
- workflow-history：变更前快照，保存历史依据。

工作台显示设计、待确认、制作与交付。课件分支完成后显示已交付，并可再选择视频；未选择视频时不要求配音或视频导出。视频分支提供三个风格预览、明确选择、真实MP4播放器和小样确认。所有操作后端落盘，不能只靠localStorage或聊天摘要。

工程包保留原件、设计、逐字稿、导演、选择、审阅、两分支已交付文件和内置启动器。解压重开时使用新根目录核验服务身份，不接到原工程的服务。

WorkBuddy与Codex使用同一文件格式、标准库工作流和本地浏览器。原生WorkBuddy分别验证课件完成、后来追加视频、三风格选择、有声画面小样、整片及独立新对话恢复；不能只凭Codex终端通过。新对话恢复与真实自动上下文压缩事件分别报告。

## 配色批准边界

新小样确认同时保存实际配色约束，整课新增节点按[配色一致性](03-visual.md#默认外观)检查。该基准区别画布、文字、容器和线条；同一个风格ID不等于实际配色一致。历史确认不自动补签或失效；用户明确要求修正配色时才对当前工程应用相应检查。
