# 每门新课默认内置的内容工作台

工作台是企业课程Skill的一部分，入口`scripts/workbench.py`或`course_tools.py workbench`。新课默认接入；国补课适配器仅用于历史导入。服务只监听127.0.0.1，不上传素材，不自动安装依赖。

## 新课制作顺序

以下命令从Skill目录运行，COURSE和SPEC使用实际路径：

```sh
python3 scripts/scaffold.py COURSE
python3 scripts/workbench.py serve COURSE
# 在展示的工作台地址中查看可打开的初始草稿
python3 scripts/workbench.py configure COURSE --spec COURSE/project/source/course-composition.json
python3 scripts/check_workbench.py COURSE --runtime
python3 scripts/workbench.py export COURSE --server ACTUAL_LOCAL_URL
python3 scripts/check_workbench.py COURSE --require-runtime --video ACTUAL_FINAL_MP4
```

1. scaffold创建规范课程目录、`project/workbench.json`、`project/native/`画布和`project/editor/`独立启动器。模板内`workbench.required=true`，不能为通过检查改成false。未生成内容与声音的草稿可以打开，导出按钮停用；草稿不是成片。
2. 在来源与逐字稿阶段沿用原课程方法。导演方案先选视觉语言、场景和动作，再选实现；不因为通用画布而采用一套标题加卡片或强制地图。
3. 生成本地Aiden原速口播，按实际音轨定帧。制作`source/course-composition.json`并configure；它是初始化输入，实际编辑后`workbench.json`是唯一当前数据，不能反复configure覆盖编辑改动。脚本拒绝重置已经ready或有保存历史的工程。
4. 通用画布自动为文字与对象位置登记fields，图片按稳定assetId引用。替换图片与改文字会进入画面。更换为其他引擎时实现下述统一桥接，不能只把播放器包在一个页面里。
5. 启动serve，展示实际打印的本地URL。工作台默认贯穿制作，用户不必再说“增加工作台”。独立打开可运行课程目录内的`python3 project/editor/scripts/workbench.py serve .`；无需保留Skill安装路径。
6. 运行`check_workbench.py --runtime`，检查全部场景、字段/素材绑定及正反向seek；保存实际文档和渲染源码哈希。新课preview/final阶段及正式发布检查核对当前证据。文档、素材、音轨或渲染代码变化后，旧证据自动失效。
7. UI或export命令从同一份已保存数据和CourseRenderer导出。声音、单行字幕、句尾停留和品牌包装共享时间轴，不把另一个旧视频当成本次成片。源码/媒体在导出中改变会阻止提交成功。
8. 检查最终MP4编码及解码、字幕字形安全区、真实内容和声音；交付MP4、SRT、工作台URL、源码和可恢复工程ZIP。全量导出建立当前工程运行记录；片段导出不冒充整课验证。
9. 解压工程ZIP，在新目录运行`python3 project/editor/scripts/workbench.py serve .`，验证字幕、素材和音轨，再保存并导出一个区间。首次采用新引擎或修改打包规则时实测这个闭环。技术结果与人工听看、用户验收分别报告。

已有国补旧课：`python3 scripts/workbench.py import --course ORIGINAL --out EDIT_COPY`，随后serve副本。其他旧工程需要迁移桥接；这项历史限制不适用于按本版流程新建的课程。冻结旧课不自动修改。

## 通用构图输入

配置格式使用和workbench相同的场景、字幕及媒体键。例如：

```json
{
  "title": "订单核对",
  "sourceDurationFrames": 150,
  "scenes": [{"id":"S01","title":"核对订单","chapter":"收货核对","sourceStartFrame":0,"sourceEndFrame":150}],
  "captions": [{"id":"C01","sceneId":"S01","text":"先核对订单与商品","startFrame":0,"endFrame":150}],
  "media": {"audio":"audio/course-mix.wav","intro":null,"outro":null},
  "assets": [{"id":"order","label":"订单原图","path":"assets/order.png"}],
  "sceneGraph": {"background":"#f3f2ec","nodes":[
    {"id":"heading","sceneId":"S01","type":"text","text":"核对订单","x":130,"y":150,"fontSize":72},
    {"id":"order-image","sceneId":"S01","type":"image","assetId":"order","x":200,"y":300,"width":1100,"height":550},
    {"id":"package","sceneId":"S01","type":"rect","x":1400,"y":420,"width":250,"height":220,"fill":"#cfb58e","motion":[{"property":"x","from":1500,"to":1350,"startFrame":0,"endFrame":45}]}
  ]}
}
```

这是数据结构示例，不是整课视觉模板。audio必须是真实已生成的课程混音，5秒示例时长需要与实测一致，否则configure拒绝。单行字幕无标点，画面标题按内容保留。可用text、image、rect、ellipse、line、path、group，支持嵌套children、sceneId、起止帧、透明度、旋转、缩放及绝对时间motion。path使用Canvas Path2D数据；image支持contain或cover。sceneId为空的对象跨场景保留。时间从0开始，end不包含该帧。

有品牌片头片尾时，media提供实际文件，introFrames和bodyEndFrame使用实测帧边界，audio包含完整包装及正文混音。没有品牌时两者为null，边界为0和总帧数；不能为通过导出伪造片头。如果project.json已指定品牌资产，验收会核对工作台使用的实际资产。

可以在configure前于课程内写好自定义native源码。configure不覆盖native；已经ready后的构图与复杂动效由本Skill修改当前源码/sceneGraph，并保留用户在fields/assets/captions中的改动，重测相关时间轴。UI目前不提供任意关键帧曲线、原有片段重排或复杂图形重绘。

## 其他引擎的统一桥接

选择`adapter=seek-bridge-v1`，声明fields及assets，并由`project/native/index.html`提供固定1920×1080 Canvas及以下接口；所有依赖放课程内。网页、插画、三维各自保留实际绘制方法，统一编辑接口不统一画风。

```js
window.courseWorkbench = {
  version: 1,
  async apply(document) {
    // 将全部fields文字/偏移及assets当前路径应用到真实场景对象
    // 资源加载完成后才返回，不能只回报ID而忽略参数
    return {fields: appliedFieldIds, assets: appliedAssetIds};
  },
  async seek(seconds) { /* 从绝对时间绘制，等待媒体定位完成 */ },
  frameKey(seconds) { return 'frame-' + Math.round(seconds * 30); }
};
window.ready = true;
```

默认逐帧key最稳妥；只有证明画面在区间内完全相同时才缓存稳定key。渲染器核对apply是否登记全部ID，实际绑定由运行及编辑样例复验。复杂引擎须在代表场景改字、换图、移动参数再导出，不能只凭字段存在声称可编辑。模型/插画/截图中本来烘焙的图像内容可替换素材；需要经常改动的正文文字应独立保留。现有内置网页/插画工具仍可作为原生实现，但最终交付走统一桥接和工作台导出，不能因使用第三方引擎跳过这一步。

## 编辑、保存与打包

字幕支持正文、起止、拆分合并、样式及无标点整理；时间轴拖动字幕及两端把手。画面面板编辑登记文字和位置；素材面板替换PNG/JPEG/WebP（25MB以内）并保留原文件。句尾停留会冻结画面、插入等长静音、顺延后续字幕与画面，原配音速度保持1.0。改稿不会自动重配音，需要另行调用Aiden并重定时间轴。

撤销/重做保留当前会话；保存追加历史，版本冲突拒绝静默覆盖。恢复历史先成为草稿，再保存新版本。秒数输入允许任意小数，提交时量化整数帧，字幕不得重叠、越界或超单行安全区。

文件职责：

| 路径 | 内容 |
|---|---|
| project/workbench.json | 当前编辑数据：status、adapter、scenes、sceneGraph、fields、assets、captions、media、holds、cuts |
| project/native/ | 真实画布、桥接、字体与随课依赖 |
| project/assets/ 与 audio/ | 图片、实际配音/混音与生成记录 |
| project/editor/ | 随课程内置的独立工作台启动器与运行源码 |
| project/workbench-history/ | 保存历史 |
| project/work/workbench/ | 波形、同步音轨、导出快照与日志 |
| project/qa/workbench-runtime.json | 当前文档及渲染源码的运行验证 |
| delivery/ 与 packages/ | MP4、SRT、JSON绑定记录及可恢复ZIP |

fields使用稳定id、objectId、sceneId、property、text、dx、dy；assets使用id、path、originalPath；所有路径在工程内。工作台中的编辑值不写回初始化spec，不维护两份并列当前状态。

新课ZIP保留规范课程结构及project/editor独立启动器（早期国补兼容包仍使用根目录editor）。ZIP携带冻结workbench.json、当前原生源码、实际assets/audio/media/source及项目配置，附editor内的当前工作台。缓存、保存历史和用户私有运行器配置不打包；不会遗漏放在新课assets/audio目录的媒体。解压后若要再次验收，运行 `python3 project/editor/scripts/check_workbench.py . --runtime` 重建证据。运行环境仍用已有Python、ffmpeg/ffprobe、Python Playwright和Chrome，本机配置在安装目录外。

新课每次成功导出后，之前由工作台生成的交付自动保存在project/work内的历史任务中，delivery和packages保留当前版本，原下载地址仍可读取历史文件；retain_artifacts明确冻结的文件不移动。


## 同步裁剪空白与停留（3.3）

时间轴点击“剪辑”或右侧“剪辑”页，输入起止秒数，或把播放头分别设为起点、终点。按住Shift在波形或刻度上拖动可选区；点击绿色“停留”片段直接选中该段。选区覆盖全部轨道，先“试听选区”，再“裁掉选区并前移”。裁后清空选区，避免再次点击误裁相邻内容。

这会同步删除所选时段的画面、原混音或新增静音，后续画面、波形和字幕一起前移。完全处于区间内的字幕移除，跨边界字幕缩短；剩余文案不会自动猜测或重写。剪入正在说话的内容时，人工核对字幕和声音接缝。没有自动跳过全部静音或只裁单独一条轨道；原声速度仍为1.0。

`cuts`是原始时间轴上的有序、合并、互不重叠整数帧区间，使用`startFrame / endFrame`，不含终点。没有cuts的旧工程按空列表处理。`holds`只保存剩余停留长度；裁剪停留直接减少该长度，不把静音误当成原录音。每次在当前编辑时轴选区，通过timeline模块反算原始保留片段，避免重复裁剪后坐标漂移。字幕时间仍是当前编辑时轴，场景和动画仍使用原始时间轴。

同一帧映射用于预览、波形、片头片尾定位和逐帧导出；混音按相同保留片段在48kHz进行样本级拼接，不变速。裁剪保持原始音轨、画布和素材文件不变；撤销/重做、磁盘历史、ZIP重开都保留裁剪数据。保存后重新导出才能更新成片与运行验证。
