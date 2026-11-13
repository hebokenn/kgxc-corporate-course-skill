# 花字与课程动作音效

[返回首页](../README.md) · [默认两款音效试听](../skills/corporate-training-motion/assets/sfx/teaching-native-v1/audition.html) · [动作调用与混音](../skills/corporate-training-motion/references/31-action-sound.md) · [花字设计](../skills/corporate-training-motion/references/46-flower-text-and-native-sfx.md)

## 安装后默认直接使用的两款声音

新音效默认库为 `teaching-native-v1`。用户选定并明确要求随Skill提供《提示音》（叮）与《嘟咚，提示音1》，安装者无需重新寻找音源。包内保存原始MP3字节、48kHz立体声PCM16渲染副本、来源ID、哈希、推荐增益与离线试听。渲染副本只做解码/重采样，不加EQ、变调、拉伸、噪声层或混响。

| 默认音源 | 来源 | 常见用法 |
| --- | --- | --- |
| [叮：提示音](../skills/corporate-training-motion/assets/sfx/teaching-native-v1/ding-original.mp3) | 黑罐头，ID `7888c6c8af55469792f3371251ac4f8e` | 重点标记、依据定位、划线完成、总结落点 |
| [嘟咚：嘟咚，提示音1](../skills/corporate-training-motion/assets/sfx/teaching-native-v1/dudong-original.mp3) | 黑罐头，ID `5a04b6d43e0743f5b9b74dc3e8cb2348` | 花字弹出、条件和轻提醒、需要提示的交接 |

15类动作角色复用这两款声音，仅有两款独立音色。动作持续过程可静音；连续划线可只在组首和完成点发声。平等选项使用相同素材和 `groupId`，旁白避让也取组内共同的较低音量。反复提问、否定边界和阅读段可以不发声。花字、声音与正常速度讲解一起审阅，不增加独立审批。

[观看约73秒花字与原库音效样片](media/flower-native/README.md)可比较实际课程中的对位、密度与留白。试听单音不等于已检查课程混音，技术扫描也不能代填用户认可。

## 调用与替换

```sh
python3 skills/corporate-training-motion/scripts/course_tools.py sfx-catalog
python3 skills/corporate-training-motion/scripts/course_tools.py sfx-plan COURSE --events COURSE/project/source/sfx-events.json
python3 skills/corporate-training-motion/scripts/course_tools.py sfx-mix COURSE --plan COURSE/project/audio/sfx-plan.json --narration audio/narration.wav --out audio/course-mix.wav
```

按[实际事件格式](../skills/corporate-training-motion/references/31-action-sound.md)设置整数帧、角色、对齐与增益。默认素材峰值对应实际动作落点，原始文件带的起始空白不能忽略。`none` 保留静音；事件 `gainDb` 调整库内推荐基准，计划和混音回执分别保存实际增益。`groupId` 保证同组选项同素材同增益，混入不同设置会被拒绝。

音效更换从干净旁白或分轨重新混音，保留原人声、字幕、画面与时间线；独立输出音效分轨和实际混音。不能在旧成品上叠加新声音假装替换。已有课程的冻结计划和声音不因安装更新自动修改；用户明确另选音源时再登记新的本地库ID、来源、许可与哈希。

## 保留的备选与旧课恢复

`natural-ui-v1` 的15类×3变体共45个WAV仍随包提供，来自Kenney Interface Sounds的100个CC0原始OGG，许可证和来源哈希均保留。可在用户明确选用后使用；它不再是新音效默认。`soft-tactile-v1`只供恢复相应旧课。

```sh
python3 skills/corporate-training-motion/scripts/course_tools.py sfx-catalog --palette natural-ui-v1
```

[自然界面库逐项试听](../skills/corporate-training-motion/assets/sfx/natural-ui-v1/audition.html) · [历史库动作试听片](media/natural-ui-audition.mp4) · [Kenney许可证](../skills/corporate-training-motion/assets/sfx/kenney-interface-source/License.txt)

## 离线重建与来源

维护者可运行 `python3 scripts/build_teaching_sfx.py`，从包内两份冻结原始MP3重建立体声WAV与角色映射；校验原件哈希，不进行联网搜索。跨FFmpeg版本不保证衍生文件字节一致，重建后应重新生成文件清单和音效计划。旧自然库继续由 `sound.build_palette` 重建，其ID固定为 `natural-ui-v1`。

新默认来源、资产ID、原件哈希及用户明确纳入分发的原话见[来源记录](../skills/corporate-training-motion/assets/sfx/teaching-native-v1/source.json)。这两款第三方素材保留原来源权利说明，不因纳入本包变为CC0；[第三方说明](../THIRD_PARTY_NOTICES.md)继续适用。
