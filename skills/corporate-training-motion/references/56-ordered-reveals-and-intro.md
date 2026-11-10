# 编号顺序、具体锚点与片头节奏

适用于逐条出现的编号内容、上下篇开场/目录/总结的同类返修，以及品牌片头的时长调整。沿用本课已选讲稿、配色、声音与计费来源；规则修复不代表课程已验收，不重开同阶段盲审，不删除历史。

## 先把语义、布局和时间对齐

编号组使用 `orderedRevealGroups`，每个实际文字/标记节点带 `orderedList: {group_id, index}`。支持纵向与横向布局；复杂网格应拆成有清晰阅读顺序的组，不假报为受支持布局。

- `mode: sequential`：布局数组中的 `number` 必须连续为1、2、3；每行自己的真实词时严格递增。上一条保留到组结束，不能出现第三条先入场或编号断层。
- `mode: simultaneous`：整页编号可以同时完整呈现，实际节点的首次可读帧必须相同；不把随后旁白依次讲解误判为逐条出现。不能只改这个标签来掩盖实际错序。
- 旁白若依次讲总结、风险、行动，布局、编号与进入时刻也按这个语义顺序设计。禁止按时间排序旧数组、改编号不移布局，或用 `max` 钳制时间来遮住错位。

共用白板编译器的 `data.numberedMode` 默认为 `sequential`：每行必须有独立、递增的实际节拍，缺行不能复用最后一拍。明确选为 `simultaneous` 时，全页条目使用同一入场节拍。

示意字段（仅说明结构；实际词时和图像探针来自本课当前产物）：

```json
{
  "orderedRevealGroups": [{
    "id": "work-steps", "mode": "sequential", "layout": "vertical", "end_frame": 240,
    "rows": [{
      "number": 1, "event_id": "check-facts", "node_id": "facts-row", "stable_frame": 45,
      "sound_required": true, "sound_event_id": "facts-sound",
      "probe": {"region": [100, 300, 60, 60], "rgb": [40, 80, 140], "tolerance": 25, "minimum_pixels": 300}
    }]
  }]
}
```

`probe` 描述标记/文字所在区域的实际颜色存在性，不是OCR。区域、颜色、阈值须对应真实实现，不能随意填值冒充看过。当前像素检查验证指定区域是否出现；数字是否写对、内容是否讲清仍须当前画面观察。

## 每行绑定具体段落、句子和出现次数

使用现有 `requirements.direction.semantic_alignment` 的当前脚本/音频与逐字映射，额外保存：

- `script_path / script_sha256`；词时映射同样绑定当前 `script_sha256` 和 `audio_sha256`。
- 映射中每段有稳定 `id / paragraph_id / narration / words / char_map`。
- 每个事件有 `segment_id / paragraph_id / sentence / sentence_span / quote / raw_span / occurrence / trigger_frame`。
- 所有原文区间为从0开始、末位不含的Unicode字符位置。句子必须是当前原文的精确切片；触发词区间位于该句内，`occurrence` 明确选择本段的哪一次出现。

“这节课”“接下来”等泛化过渡词不能单独触发编号教学条目。改开场或衔接句后，旧脚本摘要或原文区间应失败；重新定位受影响的行、花字、音效和字幕。缺失、歧义、比例估时、首次模糊命中、排序/钳制均不得静默兜底。

```sh
python3 SKILL_DIR/scripts/course_tools.py reveal-plan --input current-list-input.json --out new-list-plan.json
python3 SKILL_DIR/scripts/course_tools.py reveal-check --project COURSE/project \
  --spec upper.json lower.json --video upper.mp4 lower.mp4 --purpose final --out new-order-check.json
```

`reveal-plan` 输入包含当前真实 `mapping, groups, events`，输出保留声明行序，遇歧义退出2。`reveal-check` 一并检查传入的相关各篇；发现一处问题时应将上下篇所有开场、目录、总结及共用实现纳入这一固定同类清单。它不会擅自扫描无关课程，也不新增模型盲审。未产生旁白的分镜只检查编号/布局，音频与编码项目保留为后续未开始。

## 验当前编码，不只看末态

每行要求出现前一帧、出现帧和稳定后的帧；同时检查此前条目仍在。程序从实际主视频流按解码帧号取证，排除 `attached_pic`，关闭输入格式变化时的过滤器重初始化，防止拼接视频的 `n` 计数重置。取证结果绑定当前视频SHA与实际像素摘要。

音效引用的 `frame / visual_event_id` 必须跟随本行真实事件，不能继续指向改稿前的落点。完整 `production-check` / 正式出口还会执行原库音效的实际编码信号核验；单独的列表计划检查不代表已经听到声音。

程序不自动理解所有栅格字或任意外部自定义画布；未声明的图形需制作端登记和实际画面复核。静态末态、抽帧、波形或技术检查不代替完整连续看听，不证明声音自然度，也不生成用户确认。

## 片头检查整个等待，不规定全局硬时长

本课可在 `introPolicy` 记录用户选定的 `max_seconds / max_static_seconds / source_ref / reason`。要核对整个品牌包装及标题停留，并检查短标题之后是否仍然长时间等到正文；不能只缩某一静帧而保留其余等待。没有本课选择时不自动套用一套秒数；某课选择1—2秒并实现为1.5秒，不升级为所有课程的统一模板。

```python
from intro_pacing import timing_bindings
# 先实际重算字幕、chapterTable、音效与音频时间线，再记录这些当前依赖。
doc['introPolicy'] = {
    'max_seconds': selected_total_budget,
    'max_static_seconds': selected_static_budget,
    'source_ref': actual_user_choice_ref,
    'reason': teaching_reason,
    'first_speech_source_frame': actual_first_narration_frame,
    'max_speech_gap_seconds': selected_gap_budget
}
doc['introPolicy']['timing_bindings'] = timing_bindings(doc, contract, project)
```

```sh
python3 SKILL_DIR/scripts/course_tools.py intro-check --project COURSE/project \
  --spec upper.json lower.json --video upper.mp4 lower.mp4 --purpose final --out new-intro-check.json
```

检查整体显示轴时长（包括剪切/停顿）、选定的正文间隙、当前字幕/章节/音频及速度/SFX/总时长的依赖，并对实际编码测量静止区间。帧率不符、越界或无法解码均保持未验证，不能用更大的假帧率把等待“算短”。该边界仍依赖真实制作时间线和当前语音语义检查，不能单凭标题图片判断正文何时开始。

缩短包装时保持本课选定的讲解语速；从绑定的原速源和处理回执判断已有降速，不能把已处理的0.9倍音频再次乘0.9。外部缩略图封面默认只在第0帧，之后进入品牌片头，与片头本身的停留分开验收。旧包、原声、分镜、小样和失败记录保留。
