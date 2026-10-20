# 实际效果示例文件

[返回首页效果](../../README.md#实际效果) · [工作台使用指南](../USAGE.md) · [V5 验收记录](../V5-VERIFICATION.md)

本目录保留实际工作台、实际导出与原生 WorkBuddy 的技术样例。首页海报由真实截图与品牌片段画面排版，未用概念稿冒充产品界面。

## v5 课程与分支示例

| 文件 | 内容与来源 |
| --- | --- |
| v5-course-demo.mp4 / v5-course-demo.srt | 原生 WorkBuddy 执行已准备的技术夹具后实际导出的 9.033 秒、5 场景 H264/AAC 正文；复用已登记的 Aiden 原声，本次未新生成 TTS |
| v5-editor.png | 对同一 v5 工程的真实浏览器截图，定位到 3.2 秒的 SN 与外包装核对场景；选字幕和缩放时间轴只改变查看状态，没有保存工程或修改确认 |
| v5-confirmations.png | 实际共创工作台保留的风格选择、小样确认与完整交付；保留 QA 操作者、原说明和时间，没有伪造企业批准 |
| courseware-demo.html | 原生 WorkBuddy 实际生成的独立 6 页 HTML 课件；原样保留“虚构验收用途”说明及逐字稿哈希，供讲授或自行录制参考 |
| courseware-cover.png / courseware-overview.png / courseware-exercise.png | 对上项 HTML 的实际第 1、4、5 页截图，分别展示封面、三项信息讲解和练习反馈 |
| styles/live-action-preview.png | 原生任务生成的工位实拍质感方案示意，使用 AI 生成图片，不代表真实拍摄现场 |
| styles/flat-mg-preview.svg / .png | 同一段讲解的二维工程图示方案；PNG 为原 SVG 的浏览器渲染结果 |
| styles/iso-diorama-preview.svg / .png | 同一段讲解的等距场景方案；PNG 为原 SVG 的浏览器渲染结果 |
| hero.png | 首页海报，组合实际品牌片头帧与实际 v5 编辑器截图；可编辑排版源文件见 source/hero.html |
| embeds.json | 三段原生内嵌视频的稳定 GitHub 附件地址，以及仓库原文件的 SHA-256、字节数 |
| showcase-manifest.json | 本次新增展示文件的 SHA-256、大小与图片/视频信息 |

收货内容、编号、数量、单据和练习均为虚构技术样例，不能当成正式企业制度、业务审批或完整课程学习效果。共同教学前段来自明确标注的 QA 种子工程；原生整片任务执行了 Codex 准备的技术夹具，不将此结果表述为宿主模型已自主完成完整课程创作。实际宿主经过、发现和边界见 [V5 验收记录](../V5-VERIFICATION.md)。

## 品牌包装与保留的 v3.4 示例

| 文件 | 内容与范围 |
| --- | --- |
| intro-poster.png / intro-preview.mp4 | 已批准 R5 片头背景与原配乐，换为“收货核对流程 / 酷果星创门店课程”，片头 10.5 秒 |
| outro-poster.png / outro-preview.mp4 | 已批准 R8 片尾背景与原配乐，同一课名，片尾 7 秒 |
| workbench-overview.png / workbench-cut.png | 保留的 v3.4 真实编辑器与 4.2 至 4.7 秒裁剪选区截图；截图时没有保存数据修改 |
| course-demo.mp4 / course-demo.srt | 保留的 v3.4 三场景有声技术样例，约 9 秒；首页正文视频使用上方 v5 五场景版本 |
| manifest.json | 上述历史示例的原始大小、SHA-256和实际探测信息，继续保留 |

品牌预览带原配乐。正式课程的固定欢迎语、结束语由当课配音加入，再按完整课程流程检查。品牌与第三方资源沿用[原用途及许可说明](../../THIRD_PARTY_NOTICES.md)。

## 内嵌与重新导出展示图

首页使用 GitHub 原生视频附件播放器，稳定地址记录在 embeds.json，保留对应 MP4 原文件供独立核对。播放器默认静音时，可点击音量图标打开声音；不把 GIF 冒充有声视频。原生附件上传参考 [GitHub 官方说明](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)。

安装课程媒体环境后，使用该环境的 Python 执行：

```sh
python docs/media/source/render.py
```

这会根据已入库素材重新导出海报、课件截图与 SVG 预览。需要重新采集自己的技术样例工作台时，可传入运行中的编辑页 URL：

```sh
python docs/media/source/render.py --workbench http://127.0.0.1:PORT/edit.html
```

示例截图定位针对本目录的“收货核对”技术工程。工具仅操作查看位置，不调用保存、确认或导出。新电脑仍需准备对应的 Playwright 浏览器环境。

本次更新仓库展示与安装入口，不改动已发布 v5.0.0 的 Skill 内容、标签或安装附件。
