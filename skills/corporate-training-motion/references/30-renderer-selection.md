# 按画面要求选择实际渲染器

选路用于实现已经批准的导演方案，不改变逐字稿、风格或小样确认流程。先定义观众要看清的对象变化，再声明实现所需能力。运行以下只读命令核对包内能力；不能只检查已有课程的scene-engine.js后宣布整包不支持。

这是每次“继续制作”在视频阶段自动执行的制作职责，无需用户再发选路提示词。resume的production_handoff给出当前路线、构图核对结果、可用动效与下一步；制作端结合已确认导演方案补齐需求，实际完成接入/必要升级和当前阶段产物。基础画布足够时保留；需要复杂动效时主动接入，不停在解释能力或要求用户决定技术路线。音效同时按[动作音效](31-action-sound.md)选择并在小样中核对，不能用统一提示音代替动作声音。

```sh
python3 SKILL_DIR/scripts/course_tools.py capabilities
python3 SKILL_DIR/scripts/course_tools.py route --spec COURSE/project/source/course-composition.json
```

| 路线 | 适用画面 | 接入状态 |
|---|---|---|
| scene-graph | 基础形状、图片、对象位移缩放和透明度，足以讲清当前内容 | 既有简易画布，scene-graph-v1 |
| motion-canvas | 整段可编辑文字的逐字、遮罩升起、模糊浮现；图像/组遮罩；渐变；真实路径描线；强调；镜头与缓动 | 已封装TY/DG/UI/CAM/MO，configure自动复制依赖并建立seek-bridge-v1及全部编辑绑定 |
| native-canvas | 超出封装的插画、Three.js、特殊材质/角色/交互或其他真实原生实现 | 制作端提供Canvas和apply/seek，保留现有源码，实测改字/换图/移动/导出；不能直接捕获DOM充当Canvas |

`rendering.route`通常设`auto`。route读取`rendering.requiredEffects`及节点effects、渐变、镜头和非基础缓动，报告路线与理由；configure自动落实前两条路线。显式指定简易路线却要求复杂动效会拒绝；未知能力会要求自定义实现，不静默降级。存在明确自定义adapter的旧spec仍保留原生路线。课件分支不运行此流程。

将选择理由记入director-plan.json；实际结果保存在workbench.json的rendering中，resume可恢复。route检查参数和接入要求，不证明制作质量；只有代表性动态片段、实际编辑和编码结果能证明当前画面已实现。

## 可直接制作的参数

沿用27号构图格式和真实音轨，添加如下字段。下面仅展示局部用法，不是整课模板；时间均为**课程源时间轴的绝对整数帧**，不是场景内秒数。多段内容可以在同一工程混用基础节点和动效节点。

```json
{
  "rendering": {"route":"auto", "requiredEffects":["chars-in","mask-reveal","draw-on"]},
  "sceneGraph": {
    "background":"#f3f2ec",
    "nodes":[
      {"id":"title","type":"text","sceneId":"S01","text":"先核对 再提交","x":180,"y":150,"fontSize":64,
       "effects":[{"type":"chars-in","startFrame":0,"endFrame":36,"stagger":0.04}]},
      {"id":"receipt","type":"image","sceneId":"S01","assetId":"receipt","x":180,"y":320,"width":680,"height":400,
       "effects":[{"type":"mask-reveal","startFrame":24,"endFrame":60,"direction":"right"}]},
      {"id":"handoff","type":"path","sceneId":"S01","x":930,"y":500,"fill":null,"stroke":"#17654b","lineWidth":8,
       "points":[[0,0],[140,0],[140,140],[310,140]],
       "effects":[{"type":"draw-on","startFrame":60,"endFrame":100}]}
    ]
  }
}
```

对象仍登记一整段文字，WorkBuddy与用户可以直接改整句，字符排布重新计算。图片仍用assets稳定ID，换图作用于所有引用；group包含children可同时遮罩或移动。字幕由外层工作台绘制，不随镜头运动。

| 参数 | 用法 |
|---|---|
| effects中的chars-in | 逐字错开；stagger单位秒，自动收敛到起止帧内；可设dy、scale0 |
| text-rise / blur-in / typewriter | 选一种文字入场；blur-in可设blur与dy；每个文字节点只设一种入场 |
| mask-reveal | direction为right/left/up/down；对象或组明确width、height |
| draw-on | line/path提供真实points；按弧长绘制，折线路径不再用scaleX冒充 |
| marker / underline | 强调底色/下划线；明确width、height，可设color与lineWidth；可与一种文字入场组合 |
| fill / stroke / background | 字符串色值或下述渐变对象；图形和文字都可使用 |
| sceneGraph.camera | x/y为画面中心对应世界坐标，zoom默认1、rotation为度；motion动画属性为x/y/zoom/rotation |
| motion[].ease | capabilities列出已有MO缓动，如expoOut、sineInOut、backOut、snappy；起止落定，保持绝对时间seek |

线性渐变：`{"type":"linear-gradient","from":[0,0],"to":[800,0],"stops":[[0,"#17654b"],[1,"#72b59a"]]}`。径向渐变用`type=radial-gradient`、`inner=[x,y,r]`、`outer=[x,y,r]`及同样stops。坐标是当前对象的局部画布坐标。

动态光斑背景：`{"type":"mesh-gradient","base":"#10271f","grain":0.02,"blur":40,"blobs":[{"x":600,"y":300,"r":500,"col":[40,150,100],"ax":40,"period":6}]}`，放在sceneGraph.background；直接调用已有UI.mesh。明确的静态读图不必添加漂浮背景。

配置执行仍是`workbench.py configure COURSE --spec SPEC`。构图、真实音轨、字幕、风格确认均满足后才可导出；先导出当前课程的代表性有声小样。复杂参数由制作端改源码/spec，工作台UI仍负责已登记文字、位置、图片、字幕与时间轴。

## 自定义路线与验证

已有简易画布课程在本次新增动效需求下可显式升级，无需重新configure。先读取当前workbench.json和revision，在课程source中写只包含更新后sceneGraph、rendering及新增assets的升级spec；不要用旧spec覆盖后来编辑的字幕、配音或时间轴。运行：

```sh
python3 SKILL_DIR/scripts/course_tools.py upgrade-renderer COURSE --spec COURSE/project/source/renderer-upgrade.json --base-revision 当前revision
```

命令保留已有整句改字、位移、换图、字幕、配音、裁剪与停留；升级前备份native、工程文档及随包编辑器，再更新到motion-canvas。已有自定义native源码、旧revision或改动音轨/时间轴时拒绝自动覆盖。升级后重载工作台，重新验证动态与受影响的小样；旧成片和确认历史保留，不能把旧批准直接用于新画面。安装更新本身不运行此迁移。

当requirements需要封装外的能力时，route会报告具体缺口。选择已有插画或网页实现并使用27号apply/seek桥接；`adapter=seek-bridge-v1`、`rendering.route=native-canvas`及fields/assets必须对应真实实现。configure不会覆盖已有native源码。需要的三维模型、依赖和许可分别核对；不能将默认画布改个adapter名字就报告完成。

首次接入须检查：正常速度动态是否符合导演意图；正反向定位像素是否一致；整句文字、对象位置和图片修改是否改变真实画面；工作台导出与预览是否同源；ZIP解压后能否独立重开、修改并再导出。`check_workbench.py --runtime`覆盖技术定位与绑定；人工听看及用户认可分别记录。升级Skill不修改冻结课程或套用已有小样批准。
