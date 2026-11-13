# 课程动作音效

新音效默认 **teaching-native-v1**，随包内置用户确定的两款原库素材：《提示音》（叮）与《嘟咚，提示音1》。原始MP3字节、48kHz立体声PCM16副本、来源ID/哈希和 `assets/sfx/teaching-native-v1/audition.html` 一并提供。新课直接使用；花字、移动、划线、条件与总结的设计先读[花字与动作选音](46-flower-text-and-native-sfx.md)。15类动作角色复用这两款音源，不是15款独立音色；不每字一响，连续移动和阅读可以静音。

叮用于重点、依据与完成；嘟咚用于弹出、交接和轻提醒。`natural-ui-v1` 保留15类×3变体的45个CC0 WAV及Kenney的100个原件，作为明确选用的备选；`soft-tactile-v1` 保留恢复旧课。新默认不修改已有计划、批准混音或冻结视频。

```sh
python3 SKILL_DIR/scripts/course_tools.py sfx-catalog
python3 SKILL_DIR/scripts/course_tools.py sfx-catalog --palette natural-ui-v1
python3 SKILL_DIR/scripts/course_tools.py sfx-plan COURSE --events COURSE/project/source/sfx-events.json
python3 SKILL_DIR/scripts/course_tools.py sfx-mix COURSE --plan COURSE/project/audio/sfx-plan.json --narration audio/narration.wav --out audio/course-mix.wav
```

源时间轴使用绝对整数帧。默认把实际素材峰值对齐事件帧；`align=start|peak|end` 分别对齐动作启动、接触和完成点。素材自身的起始空白不等于动作延迟，依实际可闻起音复核。长动作只在需要的启动或落位给短音，不循环持续噪声。

```json
{"palette":"teaching-native-v1","events":[
  {"id":"point-arrived","frame":96,"role":"move","align":"peak","gainDb":-2},
  {"id":"option-a","frame":140,"role":"appear","groupId":"equal-options"},
  {"id":"option-b","frame":200,"role":"appear","groupId":"equal-options"},
  {"id":"check-complete","frame":280,"role":"confirm","assetId":"confirm-native","gainDb":-2},
  {"id":"practice-thinking","frame":310,"role":"none"}
]}
```

`role` 支持click、build、move、zoom-in、zoom-out、appear、disappear、rotate、grow、shrink、reveal、focus、confirm、transition、warning；旧enter映射appear。新库固定映射，旧自然库按课程/事件ID稳定轮换，可用 `assetId` 固定同角色素材。事件 `gainDb` 范围-18到6，叠加库内推荐基准后将实际增益写入计划。`groupId` 约束平等选项同素材同设置，实际局部避让取组内共同的较低增益，回执保存 `appliedGains`；不同素材或增益混入同组会拒绝规划或混音。

路径与哈希在计划中冻结，素材变化会拒绝混音。自定义库用新ID，放在课程 `project/audio/sfx/ID/palette.json`：目录/资产字段沿用内置库结构，登记真实来源、许可、格式、哈希和以采样帧计的峰值；渲染WAV为48kHz单声道或立体声PCM16。用 `sfx-catalog COURSE --palette ID` 查看。不覆盖旧库文件，不把自定义素材写进公共安装包；公开分发需有本次对应授权。

新课未configure时，先在构图spec保存实际 `sourceDurationFrames`，再规划；可用 `--spec` 指定课程内实际构图，不能使用1帧占位。混音等长后写入spec的 `media.audio` 再configure。

既有课程获得音效修改授权后，`sfx-mix --bind` 保存原文档并增加revision，只替换音轨绑定，保留旁白、字幕、镜头与时间轴。输入必须是干净旁白或分轨，不在含旧音效的成品上叠加。输出独立音效分轨和来源记录，只局部降低音效以避让人声；削波拒绝输出，不统一压低整条旁白。

实际正常速度听看音源、混音与编码视频，检查短促、尾音、对位、抢词与密度。峰值、频谱、ASR和文件存在仅为技术证据，用户听感反馈优先。既有品牌首尾与冻结成片不因安装新默认自动修改。
