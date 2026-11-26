# 按课程内容制作素材

## 先决定对象、状态与操作，再选择画法

同一位顾客可以跨镜头保持身份，手机也应保持同一设备；要变化的是本句需要解释的内容、界面状态、人物动作、表情与景别。素材库是起点，不是只能重复调用的上限。不要拿同一张相机图、同一张人物站姿去配所有需要；也不要把优惠、订单、排班等不同对象一律放进手机框里。

在导演方案中给每个教学单元写出：实际对象、需要看清的特征、起始状态、发生的操作、可见结果、顾客反馈或尚待确认的问题。按已确认旁白的实际词句安排这些事件，动作完成后停稳读图，不拉长动作凑时长。

## 已接入的代码素材

`course_tools.py asset-catalog` 列出真实实现。构图 `sceneGraph.materials` 可声明以下素材，configure 与 compile-modules 会展开到同一套普通场景图节点，预览、文字编辑、换图、定位和 MP4 导出使用同一引擎。

| 类型 | 可修改内容 | 当前边界 |
| --- | --- | --- |
| phone | 机型、正面/背面/侧面、配色、界面内容、屏幕状态和操作帧 | 通用直板/紧凑/折叠示意；具名 iPhone 18 Pro 另有独立几何与官方参考 |
| actor | `CourseActorsCute` 角色身份、发型穿搭、行走转向、口型与手势 | 统一使用 `actors_v3_cute.js`；店长/店员绑定原版 `kg-original.png`，顾客穿便装无员工标 |
| document | 文书或票据的标题、内容行、值、页脚及各行口播出现帧 | 课程自己的信息，不预填虚构价格、资格或承诺 |
| parcel | 外箱结构、信息标签、示意编码 | 内置条码是视觉示例，真实扫码必须使用真实条码 |

画面不在现有工厂中时，直接用普通场景图、Canvas 或实际原生渲染编写本课需要的素材，再接入同一工作台。不要因目录里没有某个素材就退回字卡。新增工厂须验证实际像素、编辑与导出；名称与数量不表示质量。

### iPhone 18 Pro

本次课程用户指定 iPhone 18 Pro。人物手持机、放大操作画面、背面及侧面必须显式使用 `model: "iphone-18-pro"`，当前配色为 `glacier-blue`，不要只把通用机标题改成型号。其他课程按其对象选择设备，不能擅自把本课选择变成所有课程的默认。

`workbench/device_models.py` 保存官网核对日期、来源、机身比例和四种配色；屏幕长宽比由显示分辨率约束。背面宽摄像头平台、三镜头、闪光灯与传感器、正面灵动岛和侧键分别是可编辑节点。几何是教学插画，镜头位置不是工程 CAD 测量值。

官方参考：[产品页](https://www.apple.com.cn/iphone-18-pro/)、[规格](https://www.apple.com.cn/iphone-18-pro/specs/)。以后修改具名机型先查当前官方资料，再修改几何；官网照片不打包冒充自绘素材。

界面现有 home/camera/gallery/battery/transfer/storage/support 七类。它们是可编辑的教学示意，**不是实际 iOS 截图**。介绍真实系统菜单、特定设置路径或官方功能时，先取得对应系统版本的实际参考或录屏，不把示意界面当操作事实。电量、迁移进度、储存值是情境数据，不能当产品规格或实测性能。

```json
{
  "id": "trial-phone", "kind": "phone", "sceneId": "S1",
  "x": 950, "y": 300, "scale": 1.05, "zIndex": 10,
  "data": {
    "model": "iphone-18-pro", "finish": "glacier-blue",
    "deviceId": "trial-01",
    "screenStates": [
      {"atFrame": 0, "mode": "home"},
      {"atFrame": 32, "mode": "camera"},
      {"atFrame": 62, "mode": "gallery", "data": {"note": "本次试拍结果"}}
    ],
    "interactions": [
      {"atFrame": 25, "durationFrames": 7, "target": "camera-app"},
      {"atFrame": 50, "durationFrames": 9, "target": "shutter", "capture": true}
    ]
  }
}
```

全部 atFrame 使用本课绝对源帧；首个状态等于素材起帧，后续递增且不越过素材末帧。操作位置绑定实际屏幕坐标，不能在空白区域播放点击。人物 `phoneModel`、`phoneFinish`、`deviceId` 与特写一致；`phoneScreenStates` 直接使用同一份状态数组。切到照片结果的时刻也应一致。

### 人物动作与表情

先看[角色指南](CHARACTERS.md)与[33-virtual-characters.md](../skills/corporate-training-motion/references/33-virtual-characters.md)，统一使用 `workbench/motion/actors_v3_cute.js`（`CourseActorsCute`）多部件可爱可动人物与 `workbench/acting.py`（`stage-acting` / `acting-check`）：

- 店长（黑色 Polo + `kg-original.png`）、店员（蓝色工服 + `kg-original.png`）与便装顾客（无员工标，通过发型与服饰明确区分）全部在同一套骨架内驱动走路、转身、招手、指点与对白口型；
- 原先的静态 PNG 人物（`C01..C03` / `M1-repaired` / `blue-cast`）与 `stage-character-rig` / `stage-contact-pose` 已全部归档下线，详见 [ARCHIVE.md](ARCHIVE.md)。
- 每次添加人物演绎须检查支撑脚接地、同场受话人朝向、胸标绑定及实际编码渲染画面，不能以单帧静态参数通过代替连续动作审阅。

### 文书与层级

document.data.rows 为 `[[项目, 内容], ...]`；rowFrames 可逐行对应口播，footerFrame 对应条件/结论出现时刻。文本与列位置都成为工作台普通字段。素材 zIndex 控制编译时前后顺序，例如背景 0、素材 10、解释和气泡 20；同层保持原顺序。生成后以编译节点及工作台保存字段为编辑真值，不要在恢复时重编译覆盖它们。

## 验证与交付

`compile-assets --spec 新构图.json --out 新展开构图.json` 可先查看普通节点与 contentAssets 来源哈希。输出存在即停止；configure 只初始化新草稿。真实课程仍须补齐 motionPlan 与 narrationLinks；素材生成不替代导演编排。

先检查当前段落的机型、屏幕、角色、接触与遮挡，再按正常速度看有声结果；编码后解码操作前/中/后帧，并核对素材与特写同步。不能以“生成了更多素材”“有 48 个效果”“运行回执通过”作为教学和审美验收。当前版本有代码与实际渲染回归，C01 修订持机姿态与带胸标 M1 已在 B2 展示体验短段落试接；新人物动作和整课质量仍分别审阅，不推定用户已经接受。

高亮框、同行文字和店长/蓝衣店员胸标统一按[文字边界与门店胸标](LAYOUT-UNIFORMS.md)检查；不要复用此前独立固定宽度高亮与无标蓝衣裁切。
