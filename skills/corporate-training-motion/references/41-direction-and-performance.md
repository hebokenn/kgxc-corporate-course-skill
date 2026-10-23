# 从动态分镜到人物演出与对象证据

内容和美术选择有效时沿用。本规则约束新视频的实际制作与检查，不把某一课的版式、人物、时长、颜色或特效数量推广为所有课程模板。旧工程保留冻结实现；用户要求返修时再对受影响范围显式升级。

## 先安排观众如何看懂，再精修

从本段任务选择动词、对象、起态、关键过程、结果与反馈。操作看空间和接触，人物交流看意图和反应，数字看量与范围，材料流转看身份和去向，查阅画面看比较任务。动作完成后允许停稳；文字出现或全局缩放不能自动替代内容所需的演示。

精修前以粗图或当前可用素材做动态分镜，包含关键姿态、相邻镜头交接和已确认声音。分别安排动作时长与结果读图时长，按实际词句触发，不将整个旁白段落用作同一个缓慢动画。静音看关系，再用正常速度检查视听时机。动作、镜头和声音不能同时争抢同一注意力。

## 人物如何交流

先写清人物当时想做什么、看谁或什么、如何听到对方、什么时候才回应。可按内容组合预备、动作、短停留和回稳，改变主次与速度；不要让所有人物同步眨眼、周期摆动或对着讲师旁白不断张嘴。

- 眉、眼、嘴共同建立情绪，原本微笑的图不直接代替疑虑。
- 视线绑定实际对象。角色看向对方、转向被解释的对象、再回到对方，有对应的时刻。
- 倾听与说明有先后，另一个人也有反应。手势和头颈配合，保留轮廓、关节和服装衔接。
- 景别让必要表情足够大；全身与半身共用同一原图与时间轴。保留真实胸标，不水平翻转带标衣服。
- 口型只跟角色自己的实际对白。讲师叙述角色时可保持闭口，不冒称已做逐音素同步。

当前内置 `C01` 和 `S01` 各有自己的原图标定。`character-performance` 使用原纹理的眉眼连续网格、视线、眨眼、局部嘴形、短促点头和肩肘腕通道。口部是局部代码重画，头发、轮廓与其他纹理沿用原图；它属于正面二维表演，未验证侧面转头、自然行走、接物或逐音素口型。S01只开放已验证的左侧手势；其他角色先建立自己的原图、五官和关节标定，不能套C01或M1坐标。

```sh
python3 SKILL_DIR/scripts/course_tools.py stage-performance COURSE --identity C01 --out COURSE/project/source/C01-performance.json
python3 SKILL_DIR/scripts/course_tools.py stage-performance COURSE --identity S01 --out COURSE/project/source/S01-performance.json
```

合并输出 `assets` 和 `data` 到 `sceneGraph.materials` 的 `kind: actor`。给 `data.performance` 加 `keys`、`blinks`、`targets`；关键帧用本课绝对源帧，从素材起帧开始；数值通道连续插值，目标ID离散切换。`targets[].id` 指向实际节点，如另一角色的 `ID-performance` 或讲解中的物件；`blinks` 每项是开始、闭合、回开三帧。`keys[].values` 支持 `concern/relief/gazeX/gazeY/nod/head/left/right/leftFore/fore/leftHand/hand`。幅度按入口验证，先从小范围演出检查效果。可用 `viewport:[x,y,w,h]` 声明实际取景区，并在关键帧断言 `performance.visibility.face.fraction` 或 `performance.visibility.rightHand.fraction`，避免点头或手势发生在画外。它检查投影外框与取景区的覆盖比例，不代替alpha轮廓、接触和遮挡复核。

素材编译为普通图片节点的 `performance` 属性；预览、位置与素材编辑、逐帧定位和MP4共用同一引擎。原图SHA随profile保存；换原图后核对标定，不改一个哈希就推定兼容。新表演仍须看实际编码画面。

## 新工程的对象证据

新工程默认 `motionPolicy.stateProofRequired=true`，创建标记防止删策略绕过检查。动作节拍除原有用途、起态、结果、词句锚点和对象ID外，提供：

```json
{
  "evidenceFrames": [30, 42, 54],
  "stateChecks": [
    {"sourceFrame":30,"objectId":"item","property":"x","op":"eq","expected":200},
    {"sourceFrame":54,"objectId":"item","property":"x","op":"approx","expected":500,"tolerance":0.1}
  ]
}
```

这只是字段示例，不是固定节拍。三个证据帧按当前动作选择；瞬态可包括进入、接触/关键过程和离开后的结果。人物可断言 `performance.concern`、`performance.gazeY` 等实际通道。断言支持 `eq/approx/lt/gt/absent`；不能用镜头坐标或标签变化替代对象状态。动作锚点仍绑定原旁白，剪切和停留通过同一时间映射处理。

静态停留绑定 `objectIds` 和具体 `reason`，写清看什么或想什么。整场查阅可在 `scene.presentation.mode=reference` 声明；操作、交流、关系演示不能用整场observe包住。导航或品牌场景可分别声明 `navigation/brand`，不为它们强加业务动作。

导出时实际检查运行状态，在指定帧隐藏目标对象取得可见像素区域，再从最终MP4解码同帧核对变化。状态比较不把全局镜头计为物件自身变化；视线目标标签也不单独算动作。像素诊断按实际字幕高度排除字幕带。目标区域证据比全画面变化更可靠，但仍不能自动理解业务语义或所有接触关系。

`course_tools.py motion-check --spec SPEC` 做导出前结构检查；正式工作台导出自动写 `object-proof/proof.json`。任意定位、修改后预览、编码和全量解码也要完成。自定义原生路线在已有 `apply/seek` 外还提供 `objectReceipt()` 与 `isolate(objectIds)`，返回实际本地对象状态并能按ID隐藏同一渲染对象；不能只返回镜头或声明标签。技术证据通过后，再记录正常速度的演出、可读性、形体连续、情绪与视线判断；审美、学习效果和用户认可分别登记。没有统一动作密度或特效配额。
