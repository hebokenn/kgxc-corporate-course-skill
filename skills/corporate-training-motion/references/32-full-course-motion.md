# 整课实际动效与防降级验收

本规范适用于5.1起新建的视频工程，以及用户明确要求升级视觉的旧工程。安装或恢复不自动修改冻结课程、配音、小样确认或旧成片。

## 可调用能力，以实际入口为准

`course_tools.py motion-catalog`列出48种实际动作，其中37种用于对象操作、比较、判断、路径或反馈；另有8种文字/强调和3种符号描绘。渐变、缓动、配色、速度、重复次数、构图风格不算新的动作种类。17类教学构图通过`sceneGraph.modules`调用，共用`teaching_modules.py`编排器和工作台实际渲染器。它们不是只供宣传的十秒视频。

```sh
python3 SKILL_DIR/scripts/course_tools.py motion-catalog
python3 SKILL_DIR/scripts/course_tools.py compile-modules --spec SPEC --out COMPILED
python3 SKILL_DIR/scripts/course_tools.py motion-check --spec COURSE/project/workbench.json
```

17类构图：blueprint扫描连线、editorial公式拆解、whiteboard逐笔路径、presenter品牌手势、spotlight聚光放大、correction差异纠正、sorting流程归位、quiz选择反馈、timeline时段编排、data数量聚合、swiss字体层级、isometric空间拆层、papercut纸艺折页、comic分镜对话、terminal记录筛选、ink知识分枝、pixel任务闯关。

动作可在普通节点的`effects`中组合；构图是可选起点，不能全课只换文字。数据、人物、物件、目标与镜头依本课设计。选择A风格不等于只准基础形状、同一白底或默认淡入。无需每门课机械塞入全部48种。

## 从旁白排真实过程

每个新的操作、使用条件、判断、关系或反馈，都指定对象起态、过程与结果。为完整段落安排节拍，不把一个1.4秒入场动作当作二三十秒讲解的实现。保留同一人物、物件和问题的身份连续；展示体验就演示与交接，发掘需要就显示问题如何分枝、归组，流程就显示任务如何流转。

静止阅读、观察结果和练习思考是有效设计，记录学员具体在读或想什么。背景漂浮、字幕变化、无意义镜头缓推和重复装饰不能充当教学主体动作。动作时长服从对象和讲解，不能通过慢放短小样填满长旁白。

5.1.0的连续样段出现过具体失败：制作端把整句的5～12秒直接传给交接、回填、描线等局部动作；技术检查只确认“主体在变”，未判断动作用处和节奏。**不得照搬该样段的时长编排。** 5.1.1将旁白窗口与单次动作拆开，并改为按实际动作帧验证。既有48种动作能力保留，不以调用种类或更高覆盖率作为课程合格结论。

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

小样批准同时绑定实际已加载动效源码哈希、动作语言与核心动作。扩展内容仍可新增镜头，不能通过保留“A”标签却替换动效引擎绕过受影响的小样复核。自定义native路线也须提供真实动作实现路径/函数与`courseWorkbench.motionReceipt()`运行回执，不能改adapter名称逃过检查。

## 可复现的验证

```sh
python3 SKILL_DIR/scripts/motion_gallery.py NEW_GALLERY
python3 SKILL_DIR/scripts/verify_motion_library.py NEW_GALLERY --out QA_DIR
python3 SKILL_DIR/scripts/motion_gallery.py NEW_MODULE_GALLERY --modules
python3 -m unittest discover -s SKILL_DIR/scripts -p test_motion_quality.py
```

图库明确标记无配音技术演示，不能取代连续有声课程验收。每次新增动作验证起态、过程、结果、正反向定位、实际改字/移动/换图和导出；补查8帧短动作落在2fps采样点之间仍能被精确帧检测；“拉长交接填整句”“旁白锚点是旧文本”“删除对应策略”必须失败。用“字幕会动但主体不动”“一秒动作冒充长讲解”“虚构30种名称”“原生路线缺运行回执”作负例。发布前再验证一个完整连续教学小节及可编辑工程恢复，不能仅凭图库通过承诺整课审美。
