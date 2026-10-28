# 新课随机选色与持续沿用

用于新课选色、用户指定品牌色或提出禁用色、以及排查重复套用绿色模板。配色选择由制作端执行，随既有分镜与小样一起审阅，不增加独立确认环节。

## 选择逻辑

- 用户明确指定的色板、品牌规范和实际已确认小样优先。已有课程恢复时读取已有记录；不因安装更新自动抽色或改写旧画面。
- 未指定色板的新课，在六套完整、已检查文字对比的候选中随机抽一套。默认候选不含绿色，包含明、暗两类画布。它们是起点，用户仍可明确指定包括品牌绿在内的其他合格色板。
- 用户提出的禁用色在抽取前筛选；没有候选就报告具体缺口，不忽略禁用色、不反复挑种子。背景、正文、强调、辅助、容器和线条一起选，不每页随机，不把每段不同颜色当不同表现方案。
- `project/palette-plan.json` 保存种子、筛选后的完整候选池、禁用色、选中结果及版本。恢复、重跑编译或重新生成分镜均沿用同一文件，不重新抽取。需要换色时记录实际要求并保留旧记录。
- 调色只影响教学画布；人物衣服与胸标、Apple设备、实拍和真实界面保持对象本色。白色与中性灰的审阅界面独立于课程色板。

## 制作端调用

正常 `kgxc_course.py start` 建档会自动保存随机色板；下面的 `palette` 在已有记录时只返回原结果。用户说“随机配色，不要绿色”时由制作端执行，不要求用户操作终端：

```sh
python3 SKILL_DIR/scripts/course_tools.py palette-catalog
python3 SKILL_DIR/scripts/course_tools.py palette COURSE
python3 SKILL_DIR/scripts/course_tools.py palette COURSE --exclude green --redraw --evidence "用户要求本课排除绿色"
```

`--redraw` 必须提供原因；换色同步分镜色值，使受影响美术确认过期，保留逐字稿确认与片段表现选择。已有记录未重抽时不接受悄悄更改禁用色或替换色板。`--exclude` 可重复，支持 `green`、`pale-green`、`blue`、`purple`、`red`、`orange`、`yellow`、`pink`。对比检查覆盖正文、强调、辅助、次要文字与错误文字在画布、容器和浅/深辅助面上的4.5:1下限；实际构图仍要查看。

用户指定完整品牌色板时，文件含 `id`、`name` 和九个角色：`canvas`、`ink`、`accent`、`secondary`、`soft`、`stroke`、`muted`、`surface`、`error`。可以复制 `palette-catalog` 中一项作为起点，再按真实品牌规范调整：

```sh
python3 SKILL_DIR/scripts/course_tools.py palette COURSE --file 本课色板.json --redraw --evidence "用户指定的品牌色板"
```

这里的随机结果是制作候选，不代表分镜或有声小样已获认可。已有小样配色确认时，选色命令会保留确认；需要改色则走现有受影响范围的返修与新小样确认，不能覆盖旧记录。

## 进入真实画布

制作端读取保存的记录，把 `coursePalette` 绑定到实际构图。`authoring.configure` 自动读取本课记录；独立编译时先绑定再展开：

```python
from course_palette import bind, read_plan
from teaching_modules import expand
spec = expand(bind(spec, read_plan(course)))
```

新课的17类教学构图与24种风格配方使用绑定色板。旧配方里的颜色只服务旧课与风格目录，不能被当成新课的默认墨绿、浅绿。构图需要其他教学色时先更新本课合格色板，保留实际依据；设备或人物的真实本色在对应对象上注明 `contentColorReason`，不能用这个字段豁免整张教学卡片。

导入、保存与导出前检查画布是否与记录相符、色板绑定是否匹配、教学色是否超出已保存范围或命中禁用色。分镜页展示同一套实际色值。位图内容和特殊原生渲染仍须查看当前实际画面；声明、结构检查和编译通过不代表已经完成动态、美观或用户验收。
