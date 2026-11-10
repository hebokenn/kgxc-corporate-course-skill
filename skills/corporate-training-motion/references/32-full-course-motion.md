# 整课实际动效与防降级验收

本规范适用于5.1起新建的视频工程，以及用户明确要求升级视觉的旧工程。安装或恢复不自动修改冻结课程、配音、小样确认或旧成片。

## 可调用能力，以实际入口为准

`course_tools.py motion-catalog`列出100种实际动作，其中89种用于对象操作、比较、判断、路径或反馈；另有8种文字/强调和3种符号描绘。渐变、缓动、配色、速度、重复次数、构图风格不算新的动作种类。17类教学构图通过`sceneGraph.modules`调用，共用`teaching_modules.py`编排器和工作台实际渲染器。它们不是只供宣传的十秒视频。

```sh
python3 SKILL_DIR/scripts/course_tools.py motion-catalog
python3 SKILL_DIR/scripts/course_tools.py compile-modules --spec SPEC --out COMPILED
python3 SKILL_DIR/scripts/course_tools.py motion-check --spec COURSE/project/workbench.json
```

17类构图：blueprint扫描连线、editorial公式拆解、whiteboard逐笔路径、presenter品牌手势、spotlight聚光放大、correction差异纠正、sorting流程归位、quiz选择反馈、timeline时段编排、data数量聚合、swiss字体层级、isometric空间拆层、papercut纸艺折页、comic分镜对话、terminal记录筛选、ink知识分枝、pixel任务闯关。

动作可在普通节点的`effects`中组合；构图是可选起点，不能全课只换文字。三选一决定配色、字体、图形材质和画面气质，全部动效与构图仍可按内容选用。选定同一视觉风格后，整课应根据不同内容充分组合人员变化、对话、操作、对比、流程、反馈和镜头，不锁定小样的少数动作或同一版式。无需机械塞入全部100种，丰富程度由内容是否得到恰当表现判断。

`motionPlan.language` 是本课动作编排的说明标识，不是动作类别限制。`protectedEffects` 是明确要保留的核心动作下限，不是允许使用的动作清单；其他实际动作可增加。`style_scope=visual` 的风格与小样批准不因这两个字段或内容分镜的正常扩展而失效。实际源码、声音、字幕或美术规范改变仍按受影响范围复核；所有新动作继续通过口播、实际实现和编码画面检查。

## 从旁白排真实过程

每个新的操作、使用条件、判断、关系或反馈，都指定对象起态、过程与结果。为完整段落安排节拍，不把一个1.4秒入场动作当作二三十秒讲解的实现。保留同一人物、物件和问题的身份连续；展示体验就演示与交接，发掘需要就显示问题如何分枝、归组，流程就显示任务如何流转。

静止阅读、观察结果和练习思考是有效设计，记录学员具体在读或想什么。背景漂浮、字幕变化、无意义镜头缓推和重复装饰不能充当教学主体动作。动作时长服从对象和讲解，不能通过慢放短小样填满长旁白。

5.1.0的连续样段出现过具体失败：制作端把整句的5～12秒直接传给交接、回填、描线等局部动作；技术检查只确认“主体在变”，未判断动作用处和节奏。**不得照搬该样段的时长编排。** 5.1.1将旁白窗口与单次动作拆开，并改为按实际动作帧验证。既有100种动作能力保留，不以调用种类或更高覆盖率作为课程合格结论。

每个讲解事件写清：实际口播词句及源帧、学员此刻要看懂的用途、具体对象、操作后的可见结果，以及后续问题/条件/反馈。服务场景里尤其区分“准备好体验机”“顾问演示”“交给顾客”“顾客自己操作”“看照片结果”“问是否符合期待”；每件事各有对应词句，不能把同一段长位移铺在整段讲解下。普通动作自然完成，解释已完成结果时停稳；长动作必须是确实需要持续展示的过程，记录跨越的真实词句和复看帧。


示例中要使用的效果必须有实际调用。素材、API或性能不足时先修复实现、换用能保持教学意图的真实方法并验证；需要改变已批准的视觉或动作方案时展示受影响的连续样段。不得自行降级后声称按原方案完成。

## 编排和编辑

时间使用课程源时间轴的绝对整数帧。模块须由制作端提供本课数据和实际节拍，不自动缩放示例时间轴。

```json
{
  "rendering":{"route":"auto"},
  "sceneGraph":{"modules":[{
    "id":"service-phases","module":"papercut","sceneId":"S01",
    "data":{"title":"接待前、中、后，各有重点","phases":[
      {"title":"接待前","labels":["状态准备"]},
      {"title":"接待中","labels":["待客之道","建立联系","发掘线索","展示体验","达成交易"]},
      {"title":"接待后","labels":["建立长远关系"]}
    ]},
    "beats":[{"startFrame":0,"endFrame":60},{"startFrame":60,"endFrame":120},{"startFrame":120,"endFrame":180}]
  }]}
}
```

`workbench.py configure`自动编译为普通节点、整句文字字段、图片ID与位置绑定；预览和导出使用同一套实际代码。`teachingModules`保留来源和节点清单，后续编辑以保存后的节点/fields为准，不用旧模块参数覆盖用户改字或移动。复杂实例仍可直接编排普通节点，不能退回默认静态图。

需要新增或定制时遵守各动作的真实输入：path-follow用真实points；group-collect的from/to对应实际子对象；record-filter用保留记录序号；count-up/odometer以可编辑文字为终值；presenter-gesture绑定已批准M1原图、KG、张口和眨眼四个素材ID，使用连续网格，不拆四肢拉伸。品牌手势是已验证的动作范围，不宣称任意骨骼或逐音素口型。

## 新工程必须通过三层检查

1. **导出前，检查口播与对象状态。** `motionPlan.schema=course-motion-plan/1`；动作beat含真实对象、purpose、before、after，另须`anchor={cueId,phrase,atFrame}`绑定实际口播。5.1.1新工程默认`semanticRequired=true`，`narrationLinks.schema=narration-object-events/1`，其`cueLinks`逐句含`cueId,text,purpose,visibleObjectIds`；本句可以解释已经完成的状态，不要求每句持续运动。旧词句、虚构对象、缺少锚点、动作与口播时刻错开会拒绝。新建工程的motion-contract.json防止删除策略绕过检查；旧冻结工程不自动迁移。
2. **检查异常拖长。** 普通揭示/对话默认超过1.2秒、交接/组装/归位超过2秒、沿路径位移超过2.5秒会要求重新编排；这些是异常提示，不能机械当成全部动画的速度标准。确有长过程时，在`narrationLinks.pacingExceptions[对象ID:动作起帧]`写实际理由、至少两个跨越该过程的真实cueIds、至少三个过程内源帧reviewFrames，再实际复看；结构检查不代表理由被人工认可。不要为了过检查把所有动作同速化。
3. **编码后，检查真实动作帧与调用。** 对每个动作按第一帧、中间帧、最后活动帧解码最终MP4主体，保存真实运行回执。快速点击和交接不再靠2fps粗采样判定，禁止把动作放慢来让采样“看得到”。2fps只用于定位长静止段；字幕、页眉和跨镜头变化不算教学对象动作。未检测到已声明动作或缺运行回执则失败。静止结果可供解释；未解释的空等保留候选供修正。
4. **正常速度连续复看，才能登记整课完成。** 比较批准小样与全片早、中、晚段及难讲部分，逐场景说明动作是否适合此句用途、是否拖慢、操作后结果或反馈是什么。`qa/director-review.json`绑定当前视频和文档SHA，记录实际1倍速复看范围及方法。关键帧和技术计数不能代替连续检查。未完成时只登记候选；技术检查、内部视觉复核、人工听看和用户认可分别报告。

复核文件格式：`schema=course-director-review/1`、`status=reviewed`、`videoSha256`、`documentSha256`、`reviewer`、`scope`、`pilotComparison`和`sections`。5.1.1的连续复看另含`continuousPlayback={speed:1,method:实际方法,reviewedRanges:实际范围}`；每个section另含`semanticFit`、`pacingObservation`、`resultOrFeedback`，如实说明实际检查，不得用自动填充文字冒充观看。每个section含`sceneId`、`status=reviewed`、`observedAction`、`narrationAlignment`、`visualContinuity`、`unresolvedIssues=[]`、`evidenceFrames=[{path,sha256,sourceFrame}]`。证据路径相对project，须为当前成片抽取的实际画面。只填写实际检查范围，不冒称已全程人工听看。复核完成后对同一当前MP4重新checkpoint final，无需为补登记重复渲染。

小样批准绑定实际已加载动效源码哈希；视觉范围的新方案还绑定美术规范、声音和字幕，不把小样的动作种类当全课上限。旧方案继续原动作语言与核心动作绑定，除非用户明确授权修改。扩展内容可新增与组合镜头、构图和动效；不能通过保留“A”标签却替换动效引擎绕过受影响的小样复核。自定义native路线也须提供真实动作实现路径/函数与`courseWorkbench.motionReceipt()`运行回执，不能改adapter名称逃过检查。

## 可复现的验证

```sh
python3 SKILL_DIR/scripts/motion_gallery.py NEW_GALLERY
python3 SKILL_DIR/scripts/verify_motion_library.py NEW_GALLERY --out QA_DIR
python3 SKILL_DIR/scripts/motion_gallery.py NEW_MODULE_GALLERY --modules
python3 -m unittest discover -s SKILL_DIR/scripts -p test_motion_quality.py
```

图库明确标记无配音技术演示，不能取代连续有声课程验收。每次新增动作验证起态、过程、结果、正反向定位、实际改字/移动/换图和导出；补查8帧短动作落在2fps采样点之间仍能被精确帧检测；“拉长交接填整句”“旁白锚点是旧文本”“删除对应策略”必须失败。用“字幕会动但主体不动”“一秒动作冒充长讲解”“虚构30种名称”“原生路线缺运行回执”作负例。发布前再验证一个完整连续教学小节及可编辑工程恢复，不能仅凭图库通过承诺整课审美。

新工程的实际状态断言、目标隔离编码证据和整场阅读边界按[导演与人物演出](41-direction-and-performance.md)执行。旧工程不因安装更新自动迁移。

## 执行检查：实际结构与显示时钟

统一入口为 `workbench/production_validation.py:inspect_extra(project, context)`；由[统一执行合同与放行](55-execution-contract-and-release.md)固定调用，仍以 `production-contract.json` 为主记录，不另写“已批准”台账。`context` 明确 `current_document/current_video/current_contract/purpose`。视频分镜检查实现，编码阶段另外检查当前媒体；大纲、独立课件不被要求提供未来视频。

`requirements.direction.presentation` 登记 `chapters[{chapter_id,teaching_task,primary_structure}]`、`scenes[{scene_id,spatial_organization,interaction_order,information_order,before,process,after,reading_task}]`。实际对象引用沿用 `direction.scenes[].node_ids`。`presentation_signatures.signature()` 从真实节点类型、父子关系、归一布局、属性操作顺序与文字首显顺序生成结构签名，排除文案、颜色、名字、镜像及单独更换效果名。相同签名报 `DUPLICATE_PRESENTATION`；不同签名也不等于视觉丰富或教学有效。

编码检查复用 `motion_quality.audit_encoded()`，排除字幕和导航所在区域，保留真实静止时间窗。阅读例外须给 `reading_tasks[{scene_id,object_ids,reading_group_id,source_window,display_window,reason}]`，绑定实际稳定阅读组；整场 reading/observe 标签不能作为豁免，讲解新增字段而正文静止报 `STATIC_WITH_NEW_TEACHING`。正常速度比较由 `direction.review.continuous_comparisons` 和 `chapter_viewings` 记录真实范围、方法和观察，缺失保持 `PRESENTATION_COMPARISON_UNVERIFIED`。签名或抽帧不能替代这项观看。

导航唯一来源为 `requirements.chapters.chapter_table` 与完全相同的 `document.chapterTable`。每行包含 `chapter_id,label,source_start,source_end,display_start,display_end,body_visible_windows,nav_node_ids`；`table_sha256` 绑定整表。`chapter_table.canonical_table()` 用既有剪切/停顿映射生成显示边界；目录和MP4章节通过 `export_playback.playback()`消费同表。`label_mode/allow_state_words`保留本课选择，纯章节名选择下禁止自动加“已学/未学/当前/勾号”。

可执行填充子节点声明 `navigation:{kind:'progress-fill',chapter_id,segment_width}`，并保留作用于实际宽度的线性 `motion`。`CourseRenderer`把实际 `displayFrame`传给新原生桥接；`scene-engine`仅对这些导航填充按章表计算宽度，正文继续用源帧。停顿期间正文冻结、进度继续，跳转直接算当前位置。旧引擎没有 `navigationClock='display-frame/1'`则拒绝忽略新导航。父标签不添加虚假动作，子节点真操作可以单独绑定。

`chapter_table.inspect()`检查章界前后、10%/50%/90%、尾帧和线性端点；编码阶段逐图核对真实矩形填充像素。特殊绘制/变换无法自动量测时保留 `NAV_PIXEL_UNVERIFIED`。章表、编辑和消费者不一致报 `CHAPTER_TABLE_STALE`；静态或重置进度报 `NAV_TIME_MISMATCH`。新增合成验证实际覆盖24fps、两章、剪切、停顿、跳转和H.264像素；这不是任意片型/连续视听验收。
