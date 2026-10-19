# 单一Skill内部工具

统一工具入口为`scripts/course_tools.py`。它只调用本包实现，不搜索或加载其他Skill，本机已验证的运行器引用可放在安装目录外的`~/.config/corporate-training-motion/tools.json`，`COURSE_PYTHON`与`NODE`可覆盖；不安装依赖；输出、素材和QA均写当前课程。复用工程可继续使用其实际渲染器，不为统一方法而强迁引擎。

```sh
python3 scripts/course_tools.py inventory
python3 scripts/scaffold.py NEW_COURSE
python3 scripts/course_tools.py workbench configure NEW_COURSE --spec NEW_COURSE/project/source/course-composition.json
python3 scripts/check_workbench.py NEW_COURSE --runtime
python3 scripts/course_tools.py workbench import --course ORIGINAL_COURSE --out EDIT_COPY
python3 scripts/course_tools.py workbench serve EDIT_COPY
python3 scripts/course_tools.py prepare-web --destination COURSE/project/source/web
python3 scripts/course_tools.py render-web COURSE/project/source/web/composition.html --out COURSE/project/work/render --fps 30 --force
python3 scripts/course_tools.py diagnose-web COURSE/delivery/course.mp4 --style calm --out COURSE/project/qa/motion
```

网页引擎使用`window.seek(t)`、`window.ready`、固定种子；依赖从当前工作目录解析已有playwright/playwright-core和浏览器。导入代码模板只提供起点；原模板包含的默认主题和示例动作不是本课定稿。嵌套素材修改后使用`--force`或完整依赖指纹，避免复用旧帧。

## 插画与参数化动画

```sh
python3 scripts/course_tools.py prepare-illustration --destination COURSE/project/source/illustration
python3 scripts/course_tools.py render-illustration --engine-root COURSE/project/source/illustration --spec COURSE/project/source/clip.json --out COURSE/project/work/clip.mp4
python3 scripts/course_tools.py diagnose-illustration --project COURSE/project/source/illustration --out COURSE/project/qa/illustration
```

内置实现为`libraries/illustration/scripts/engine/`：scene绘画库、motion/diagram/typo、材质、相机、参数化片段、示范和字体许可；示范场景仅供理解API，实际课程须改内容。艺术语法参数卡在`libraries/illustration/materials/grammars/`，引擎示例在`libraries/illustration/scripts/engine/examples/`。代码画面、真实素材、三维和截图可按内容组合，保持当课一致的色板、字体与对象身份。

默认1920×1080/30fps。指定`--engine-root`时执行已复制工程的render.py；片段规范的width/height/fps/duration优先。未复制引擎也可直接用包内引擎渲染spec。复制不会覆盖已有非空目录。

## 其他阶段

| 工作 | 同包入口 |
|---|---|
| 新课目录与模板 | scripts/scaffold.py |
| 本地编辑与保存导出 | scripts/workbench.py；见27号工作台契约 |
| 本地Aiden原速 | scripts/qwen3_tts.py；见23号配音说明 |
| 音乐节拍 | course_tools.py beats MUSIC --json BEATS.json |
| 字幕单行无标点 | scripts/single_line_subtitles.py及single-line-caption.js |
| 分镜与内容检查 | check_visual_plan.py、check_course_completeness.py |
| 全程布局、角色与字幕避让 | check_layout_clearance.py、check_actor_clearance.py、实际编码复核 |
| 媒体、交付与目录 | media_check.py、release_checks.py、workspace_check.py |

最终课程验收只走企业课的统一检查。内部网页运动报告、插画QA保留原数值供诊断，不调用原艺术片deliver/film_gate作为企业课发布门禁。引擎测试成功不等于整课已获用户认可。

## 品牌资源

KGXC的R5/R8背景、配乐、字体和三维工程随本包分发于`assets/bookends/`，新课换字运行`scripts/bookends.py`，见16号说明。将生成的当课片段复制到课程并登记哈希，不再要求外部工作区或独立品牌Skill。历史批准资源仍保留原始指纹。

新课的最终导出默认使用工作台按钮或 `course_tools.py workbench export COURSE --server ACTUAL_LOCAL_URL`，检查成片与当前编辑工程绑定。render-web/render-illustration保留为本地原生实现及诊断工具；采用它们时仍需27号桥接，不能跳过工作台交付。


## 3.4可分发入口

本发布包内置已批准R5/R8的无损背景、原配乐、字体和可替换标题合成器。运行 `python3 scripts/bookends.py --title 课程名称 --subtitle 可选副标题 --out 当前课程/project/assets/brand/bookends` 生成当课片段及1080p30适配副本，不再要求开发者工作区的course-bookends目录。背景、Logo、动作和配乐沿用批准版本；只有课名和可选副标题变化，生成后检查标题及声音衔接。历史母版工程只用作来源记录，不作为新安装的运行依赖。

请安装Blender：<https://www.blender.org/download/>，用于打开和修改 `assets/bookends/blender/` 内的R5/R8三维源工程。例行更换课名不必重新渲染三维。随包Blender工程已打包外部图片，包含几何与灯光，不冒称每个原始后期工序都可在Blender单独复刻。
