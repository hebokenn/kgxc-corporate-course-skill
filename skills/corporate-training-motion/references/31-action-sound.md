# 自然界面动作音效

新音效默认 **natural-ui-v1**：按点击、构建、移动、放大、缩小、出现、消失、旋转、增长、收拢、揭示、聚焦、确认、切换、提醒 15 类动作选择，共 45 个常用 WAV；同包保留 Kenney Interface Sounds 的 100 个 CC0 原始素材、许可证和来源哈希。常用库经过短切、柔化高频、淡入淡出及少量构建/转动组合，不再以滤波白噪声生成位移声。旧 soft-tactile-v1 仅供恢复旧工程，不作为新默认。

`assets/sfx/natural-ui-v1/audition.html` 可离线逐项试听三种变体，并观察对应动作；每个 WAV 是实际调用素材。选音按对象的实际变化，不每字一响，不给所有入场统一叮声，也不要求所有运动都发声。增长/缩放用对应方向，完成点用确认/落位；思考停顿、阅读和不需要声音的动作保留静音。

```sh
python3 SKILL_DIR/scripts/course_tools.py sfx-catalog
python3 SKILL_DIR/scripts/course_tools.py sfx-plan COURSE --events COURSE/project/source/sfx-events.json
python3 SKILL_DIR/scripts/course_tools.py sfx-mix COURSE --plan COURSE/project/audio/sfx-plan.json --narration audio/narration.wav --out audio/course-mix.wav
```

源时间轴以绝对整数帧计。默认把实际素材峰值对齐事件帧；`align` 可为 `start` / `peak` / `end`，分别对齐动作启动、接触和完成点。长动作可只在开始或落位处给短音，不循环铺持续噪声；不要把运动的每一帧或每个数字都映射成声音。

```json
{"palette":"natural-ui-v1","events":[
  {"id":"button-pressed","frame":45,"role":"click","gainDb":-2},
  {"id":"object-arrived","frame":96,"role":"move","align":"end","gainDb":-1},
  {"id":"chart-growth","frame":140,"role":"grow","align":"end","gainDb":-3},
  {"id":"camera-detail","frame":220,"role":"zoom-in","gainDb":-2},
  {"id":"check-complete","frame":280,"role":"confirm","assetId":"confirm-2","gainDb":-2},
  {"id":"practice-thinking","frame":310,"role":"none"}
]}
```

`role` 为上述英文角色；旧事件的 `enter` 在新库映射到 `appear`。`gainDb` 范围 -18 到 6。可指定同角色的 `assetId` 固定某个声音，省略时按课程和事件 ID 稳定轮换，避免同类相邻重复。路径与哈希在计划中保存；原库不能偷偷替换后复用旧哈希。自定义素材应作为新的课程库版本登记来源、格式及哈希，再重新规划，不覆盖已冻结素材。

新课未 configure 时先在构图 spec 保存实际 `sourceDurationFrames`，再准备计划；可用 `--spec` 指定实际构图文件，不能使用空画布 1 帧占位。混音等长后写入 spec 的 `media.audio` 再 configure。

既有课程获得音效修改授权后，`sfx-mix --bind` 保存原文档并增加 revision，只替换音轨绑定，原声音、字幕、镜头和时间轴保留。输入必须是干净旁白或分轨，含旧音效的成品不能直接叠加新音假装替换。输出独立音效分轨和来源记录；有声段按实际局部能量避让，削波拒绝输出，不统一压低整条旁白。

正常速度核对声音是否自然、短促、与动作对位、是否抢词或过密，并听实际混音和编码后视频。峰值、频谱、ASR 和文件存在仅是技术证据；用户的听感反馈优先。既有品牌片头片尾与冻结成片不因安装新默认自动修改。
