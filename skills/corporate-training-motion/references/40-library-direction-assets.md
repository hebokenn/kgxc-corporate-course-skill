# 100种动效、24种视觉风格与门店素材

按需查找：本文件负责选用策略、可调用入口和扩展；`motion-catalog` 是动作清单，`style-catalog` 是美术配方，`asset-catalog` 是可编辑工厂。条目声明不代替实际预览。

## 课程中怎么选

1. 从已确认逐字稿确定本句目的：顾客对话、操作、结构、数量关系、证据、流程或判断。运行 `recommend-visuals --intent "顾客 对话 操作"`；中文或英文标签均可。
2. 按同一段课程内容生成三个实际美术方向供现有风格确认流程使用。整课沿用一套美术规范，按教学内容组合人物讲解、动画演示、界面操作和内容讲解。既有确认有效时直接沿用。
3. 先找业务对象和状态，再选动作。把“点击”“递交”“筛出”“归位”“核验”与实际旁白词句绑定；完成后停稳看结果，不把动作时长拉成旁白时长。
4. 保存所选风格ID、配方、产品参考、实际素材ID和动作到构图及导演记录。`sceneGraph.styleScenes` 经普通场景图编译，与已有 `modules/materials/nodes` 混合使用；编译后节点是编辑真值，不恢复时重编译覆盖工作台改动。

新课的配色与这些材质/构图配方分开：[先抽取并保存课程色板](47-course-palette.md)，编译时绑定 `coursePalette`。原配方色值保留用于目录及旧课，不能让 `scene-toon`、`editorial` 等名字重新带入灰绿默认色；同课混用构图仍沿用同一色板。

常用映射：对话用 dialogue/tooltip-point；操作用 cursor-click/drag-drop/scroll-window；表单用 table-row-insert/cell-update/checklist-tick；信息流转用 handoff/lane-distribute/dependency-unlock；数量关系用 ratio-normalize/waterfall-step/funnel-narrow。`motion-catalog`每项附门店示例任务、可见结果与对象类别，便于按语义选用。8种文字与强调、89种教学动作及3种符号合计100种；缓动、配色和风格不另算动作。

## 24种可编译美术配方

这是根据2026-10-23查到的官方作品介绍、作品画面与开放项目作的**设计归纳**，不是平台官方分类，不表示逐条完整播放过视频。只学习视觉组织，不下载第三方影片、人物或配乐冒充自有资产。24项由实际构图与材质共同区分；颜色、字体或背景变化不另算风格。金属、黏土、低多边形门店、透明亚克力已分别用本地Blender建立不同几何，保留PNG、blend和构建脚本；它们是可调用静态素材，课程动作仍由场景节点驱动，不冒称完整3D镜头动画。

| ID | 名称与呈现家族 | 实际美术规则 | 参考 |
| --- | --- | --- | --- |
| `retail-toon` | 品牌赛璐璐讲师 / 角色讲解 | 大轮廓、完整人物、实体体验桌；知识点与指向同场 | [Crash Course](https://thecrashcourse.com/) · [实例入口](https://www.youtube.com/@crashcourse) |
| `scene-toon` | 门店平涂场景 / 情境演示 | 门店通道中使用蓝衣KG店员，人物与既有桌群分离；情境对象与知识点同场 | [TED-Ed](https://www.ted.com/about/programs/ted-ed) · [实例入口](https://www.youtube.com/@TEDEd) |
| `flat-cosmos` | 暗场霓虹科普 / 动画演示 | 嵌套尺度、几何隐喻、前后景分层，不借用参考角色 | [Kurzgesagt](https://kurzgesagt.org/) · [实例入口](https://www.youtube.com/@kurzgesagt) |
| `pen-whiteboard` | 钢笔纸本 / 内容讲解 | 笔迹、箭头和连续知识地图，按讲解逐笔显露 | [RSA Animate](https://www.thersa.org/videos/rsa-animate-changing-paradigms/) · [实例入口](https://www.youtube.com/@RSAorg) |
| `chalk-blackboard` | 粉笔黑板 / 内容讲解 | 深色黑板、彩粉笔式线路、推导留痕 | [3Blue1Brown](https://www.3blue1brown.com/) · [实例入口](https://www.youtube.com/@3blue1brown) |
| `handdrawn-story` | 水彩绘本 / 角色讲解 | 双页实体绘本、纸层与水彩角色；顾客与KG店员同源原形象，实际体验桌和iPad另有站位 | [TED-Ed](https://www.ted.com/about/programs/ted-ed) · [实例入口](https://www.youtube.com/@TEDEd) |
| `paper-cut` | 纤维纸雕 / 动画演示 | 独立纸层、可见叠压、折角，前后层次固定 | [TED-Ed](https://www.ted.com/about/programs/ted-ed) · [实例入口](https://www.youtube.com/@TEDEd) |
| `collage-documentary` | 报刊证据拼贴 / 证据讲解 | 照片框、来源条、纸条、标记与实物证据并置 | [The Pudding](https://pudding.cool/) · [实例入口](https://www.youtube.com/@ThePudding) |
| `comic-panels` | 网点漫画 / 角色讲解 | 顾客提问、蓝衣KG店员邀请与共同核对的连续三格；原角色网点处理，人桌分开，气泡有实际问答 | [Crash Course](https://thecrashcourse.com/) · [实例入口](https://www.youtube.com/@crashcourse) |
| `isometric-store` | 木质门店沙盘 / 场景演示 | 木纹落在桌面、桌沿和桌腿；等距地台、物件与区域标记，不只替换背景 | [Animagraffs](https://animagraffs.com/) · [实例入口](https://www.youtube.com/@animagraffs) |
| `technical-blueprint` | 蓝晒工程图 / 结构演示 | 网格、编号、结构轮廓与尺寸式引线，标明示意 | [Animagraffs](https://animagraffs.com/) · [实例入口](https://www.youtube.com/@animagraffs) |
| `technical-cutaway` | 金属结构演示 / 结构演示 | 本地3D外观分层特写；正面显示、金属机身与背面镜组分离，不借示意宣称内部拆机事实 | [Branch Education](https://www.branch.education/) · [实例入口](https://www.youtube.com/@BranchEducation) |
| `soft-volume` | 黏土立体演示 / 动画演示 | 本地3D黏土AirPods与Apple Watch，圆台座、捏塑边缘、粗糙哑光和接触阴影 | [Aardman Academy + Blender local material](https://academy.aardman.com/stop-motion-clay) · [实例入口](https://www.aardman.com/attractions-live-experiences/animate-with-aardman/) |
| `lowpoly-diorama` | 低多边形门店沙盘 / 场景演示 | 本地3D完整门店：深灰门头、木地板、白色陈列墙、体验桌；直边几何与正交空间 | [Branch Education](https://www.branch.education/) · [实例入口](https://www.youtube.com/@BranchEducation) |
| `pixel-quest` | 像素任务世界 / 流程演示 | 整数像素、关卡站点、任务道具、完成反馈 | [Red Blob Games](https://www.redblobgames.com/) · [实例入口](https://www.redblobgames.com/pathfinding/a-star/introduction.html) |
| `data-editorial` | 丝网印刷数据 / 内容讲解 | 数据为主角、统一基线、来源与单位、克制注释 | [The Pudding](https://pudding.cool/) · [实例入口](https://www.youtube.com/@ThePudding) |
| `math-dark` | 透明亚克力关系图 / 内容讲解 | 本地3D斜置透明亚克力面板；iPhone、iPad、Mac轮廓不同，底网格可透视，不复用金属竖板构图 | [3Blue1Brown](https://www.3blue1brown.com/) · [实例入口](https://www.youtube.com/@3blue1brown) |
| `ui-lab` | 玻璃界面实验台 / 操作演示 | 固定设备视窗、实际点击目标与状态变化、放大局部 | [Red Blob Games](https://www.redblobgames.com/) · [实例入口](https://www.redblobgames.com/pathfinding/a-star/introduction.html) |
| `photo-annotation` | 门店实拍标注 / 现场讲解 | 实拍作上下文，矢量框线绑定具体位置；照片从本地素材库取 | [Animagraffs](https://animagraffs.com/) · [实例入口](https://www.youtube.com/@animagraffs) |
| `minimal-type` | 白瓷极简讲解 / 内容讲解 | 大字与留白、关键对象大比例、层级不靠卡片堆叠 | [The Pudding](https://pudding.cool/) · [实例入口](https://www.youtube.com/@ThePudding) |
| `ink-map` | 石墨知识图 / 内容讲解 | 纸纹、双线轮廓、节点枝干、墨线留痕 | [Rough.js](https://roughjs.com/) · [实例入口](https://github.com/rough-stuff/rough) |
| `kinetic-type` | 凸版文字讲解 / 内容讲解 | 文字块成为比较对象，字距、大小与位置体现逻辑 | [Crash Course](https://thecrashcourse.com/) · [实例入口](https://www.youtube.com/@crashcourse) |
| `flow-map` | 毛毡流程图 / 流程演示 | 地图式路线、角色泳道、跨边界交接，终点可检查 | [Red Blob Games](https://www.redblobgames.com/) · [实例入口](https://www.redblobgames.com/pathfinding/a-star/introduction.html) |
| `simulation-board` | 塑胶规则沙盘 / 动画演示 | 个体身份可追踪、规则先说明、逐轮状态与结果并列 | [Nicky Case](https://ncase.me/) · [实例入口](https://ncase.me/trust/) |

### 调用与调整

```sh
python3 SKILL_DIR/scripts/course_tools.py style-catalog
python3 SKILL_DIR/scripts/course_tools.py surface-catalog
python3 SKILL_DIR/scripts/course_tools.py recommend-visuals --intent "顾客 对话 操作"
python3 SKILL_DIR/scripts/course_tools.py stage-style-assets COURSE --style comic-panels --out COURSE/project/source/comic-assets.json
python3 SKILL_DIR/scripts/course_tools.py compile-modules --spec 本课构图.json --out 本课展开.json
```

```json
{"sceneGraph":{"styleScenes":[{"id":"welcome-art","sceneId":"S1","style":"retail-toon","data":{"title":"先了解用途，再邀请体验","labels":["了解用途","邀请体验","核对结果"]}}]}}
```

先将 `stage-style-assets` 结果中的 `assets` 合并到构图顶层 `assets`，将返回的 `data` 合并到本条 `styleScenes.data`，再编译；JSON示例省略了这组实际文件绑定。该入口按原角色身份暂存材质衍生图和需要的3D素材。讲师默认M1、店员S01，顾客使用C01等原批准身份；`data.roleIdentities` 可按岗位指定已批准的M1/S01/S02/COACH/C01/C02/C03；缺文件直接报错，不能静默换成橙衣代码人。`stage-company-character` 仍用于可编辑原图与胸标绑定。

`styleScenes`是起点构图，可增添本课角色、真实屏幕与新物品；不强迫套示例标题。`photo-annotation.data.photoAsset` 必须绑定本课实际图片ID，同时提供 `photoSize:[宽,高]` 和 `annotations:[{"label":"具体物件","point":[0到1的横坐标,0到1的纵坐标]}]`；标注点基于当前图像内容，不能把“了解用途”等步骤词随意连到天花板或桌腿，缺绑定时报错。公开画廊使用明确标注的本地3D示意图；通过 `visual_library_gallery.py --photo-id 用户素材ID --annotations 标注JSON` 才使用私有实拍，不能把3D示意冒充门店照片。

漫画使用连续事件与实际问答，绘本使用双页场景；不把三个同姿态人物加标签当成三个镜头。人物与家具之间按可见轮廓留出空间，人物按alpha裁切后的脚底落地；设备的底座以 supportBinding 绑定 supportSurface 实际桌面点，并逐帧检查接触。立体图标签使用真实相机投影与图像实际显示矩形，说明放独立安全区，禁止与人物鞋、桌腿或标签混排。设备放在明确桌面或角色已验证接触姿态中，不能悬浮到人物腿前假装手持。背景只用安静材质，玻璃反光、木纹、纸层等应落在相应物件上；不把高光贴图平铺整页。

复制 `workbench/visual-styles.json` 中一项为独立JSON，改 `id/title/palette/font/outline/rules/tags/motions/surface`，用 `register-style --file 风格.json` 保存到用户配置的 `visual-styles/`。支持CourseHan、CourseHand、CourseSerif、CourseHeavy四种已打包字体。现有用户配方可直接编辑同一文件；增加全新布局时在 `visual_styles.py` 增加编译实现与可见示例，再登记 `LAYOUTS`。不自动加载任意外部代码。新材质须在 `motion/surface-materials.js` 实现，再加入校验清单并生成真实示例，不能只登记名称。按本段教学用途选择动作，保存对象的起态、触发、过程、终态；同一风格可以用对话、流程、表单、设备操作等不同构图，不强迫全课复用小样的三张卡片。

## Apple产品、门店人物与实拍

产品限定Apple及无其他品牌的Apple适配配件。`retail-catalog`公开列出iPad、MacBook Air、iMac、Apple Watch、AirPods、HomePod mini、Magic Keyboard、Magic Mouse、Apple Pencil、MagSafe、USB-C电源与线、iPhone适配壳膜和iPhone体验展架。外形按官方参考核对，并明确是产品族教学插画；精确型号、尺寸、功能和OS菜单仍需本课实际参考。Magic Mouse无滚轮分键；保护膜是前屏片，不能复用保护壳后摄开孔。现有 `phone` 入口新编译只接收具名Apple型号 `iphone-18-pro`，不再输出通用折叠/直板产品。旧冻结视频与已编译节点不自动改写。

26种代码物件涵盖Apple主机/配件与门店桌、凳、陈列墙、服务台、门头、价签和文书；另有前景/店内/空间示意3种门店配方。顾客有成人、长者、儿童、商务顾客4种身份，各有5个动作和5种表情，合计100个已导出的SVG/PNG组合。它们是可选的代码虚构顾客，不是实拍人物复刻；不能充当店员、店长或Coach，也不替换原批准的C01/C02/C03顾客。默认风格与业务动效画廊使用原批准人物。

```json
{"id":"ipad-demo","kind":"retail-prop","sceneId":"S1","x":800,"y":300,"scale":1.2,"data":{"object":"ipad","brand":"Apple"}}
```

可编辑工厂入口是 `sceneGraph.materials`，kind为`retail-prop/retail-person/store-scene`；人物data用identity/pose/mood，门店data用view/sign/screenTitle。所有节点进入同一工作台。`assets/retail-v1/catalog.json`包含129项透明SVG/PNG的原始配方、来源说明与哈希，新增状态先扩工厂，再重新导出到新目录并检查结果。

### 本地素材库与后续扩展

```sh
python3 SKILL_DIR/scripts/asset_library.py import-photo --file 门店.jpg --id store-01 --title 门店正面
python3 SKILL_DIR/scripts/asset_library.py register --file 新物品.svg --id apple-prop-v2 --title Apple配件 --category product --brand Apple --product-family magsafe
python3 SKILL_DIR/scripts/asset_library.py register --file 新保护壳.png --id iphone-case-v2 --title iPhone适配壳 --category product --brand Apple-compatible-unbranded --compatible-with iPhone
python3 SKILL_DIR/scripts/asset_library.py catalog
python3 SKILL_DIR/scripts/asset_library.py stage COURSE --id store-01-ink --out COURSE/project/source/store-asset.json
python3 SKILL_DIR/scripts/asset_library.py stage COURSE --id retail:airpods --out COURSE/project/source/airpods-asset.json
python3 SKILL_DIR/scripts/asset_library.py stage COURSE --id lucide:camera --out COURSE/project/source/camera-asset.json
python3 SKILL_DIR/scripts/asset_library.py stage COURSE --id kenney:table-NE --out COURSE/project/source/table-asset.json
```

将stage结果assets合并到构图assets，并为返回node补上sceneId、位置和大小。以原ID哈希区分含点/横杠的ID，防止不同物品覆盖。素材源保存在用户配置的 `asset-library/`；`COURSE_CONFIG_DIR`可选择独立库。原图保留，局部更新用新ID，stage检测哈希并保留课程中已有修改。不要把用户实拍、参考对话截图与私人路径写入公共Skill。通过本地中值滤波、色彩量化及轮廓叠加生成平涂/线稿照片衍生版，无生图；它保留照片视角，不是可编辑三维重建。

### 开源与本地工具

- [Lucide](https://lucide.dev/license)：已打包30个SVG，保留ISC许可与逐文件来源/hash；产品图标只作通用操作符号，不替代Apple商品造型。
- [Kenney Furniture Kit](https://kenney.nl/assets/furniture-kit)：已打包36个透明家具视角PNG与对应9个GLB，仅作为桌、椅、书柜等门店设施；保留CC0原许可和源包哈希。没有加入通用/其他品牌电子产品。
- [Open Peeps](https://www.openpeeps.com/)：官网声明CC0，可按来源许可另取；本包没有冒称已下载该人物全集。
- [Rough.js](https://roughjs.com/)：可用于手绘Canvas/SVG扩展；当前手绘配方由本地节点实现，不声称已接入其运行库。
- [unDraw许可](https://undraw.co/license)限制素材包再分发，不收入本安装包。

```sh
python3 SKILL_DIR/scripts/render_blender_asset.py --model SKILL_DIR/assets/open-source/kenney-furniture/models/table.glb --out 新目录
python3 SKILL_DIR/scripts/export_retail_assets.py --out 新SVG目录 --png
```

另有 `assets/role-surfaces-v1/`：7位原批准人物的56份本地材质衍生PNG，附源图、身份、KG/MyCoach与哈希；原图保持独立。`scripts/stage_surface_assets.py --out 新目录` 可从同一人物原图重新制作纸本、水彩、漫画和像素处理，使用本地Pillow/OpenCV，不新造人物。

`assets/material-heroes-v1/` 的4份PNG和对应blend分别是金属设备分层、AirPods/Apple Watch黏土陈列、完整门店沙盘、透明斜置设备面板；`scripts/build_material_heroes.py` 可在本地Blender重新构建。使用 `blender -b --python-exit-code 1 --python SCRIPT -- 新目录`；脚本异常须退出失败，不能只凭Blender进程退出码0认为已更新素材。生成后检查实际图像和素材哈希。公开模型为独立教学示意，不是产品CAD或拆机规格。

Blender为可选本地工具，实际发现后调用，GLB导出入口返回透明PNG与可编辑blend，源GLB保留。新增Apple产品3D模型需 `--category apple-product --apple-reference 官方URL`，并实际核对模型；家具模型不当Apple商品。SketchUp没有作为已验证能力声明。没有Blender仍可调用内置SVG/PNG与可编辑工厂。

## 验证边界

`motion_gallery.py`逐项提供有身份、有对象、有结果的门店业务演示；禁止三色块兜底充作用户示例。`verify_motion_library.py`检查同一渲染器的100种动作调用、实际像素变化、倒序定位、动作前中后20个采样帧及标题/页脚禁入区域；另保存四相位图作业务审阅。这是采样检查，不能声称遍历所有帧或自动判定审美。`cluster-pack`按实际卡片宽高、`gapX/gapY`、容器边界核验终态，不允许用clip掩盖最终对象重叠或丢失。其他移动、旋转、箭头与笔尖同样需要查看最大外延。`visual_library_gallery.py --mode styles/retail/people`分别生成24风格、29类物件/场景和100顾客组合的实际画面。去掉效果的负例须失败。扩展时对新增条目重复相应检查，保持原有文字编辑、换图和位置编辑有效。独立试用覆盖字体/轮廓、素材ID、滚动裁切与Apple品牌拒绝。完整课程仍需旁白对应、正常速度视听、编码检查和用户验收；资源库演示通过不等于现有课程已重制或通过审美验收。
