# 配音：默认 B2，也可换声或克隆

[返回首页](../README.md) · [使用指南](USAGE.md)

新配音默认 **B2｜清亮平和教学男声**。它来自《门店销售转化率提升》中用户确认的 B2：有精神、亲切、讲步骤清楚，语调适中。B2 是合成声音方案，不指向某位真实人物。默认不限制选择：可用其他预设、用文字设计声音，也可用自己的参考音频克隆。

本版新安装默认 B2；更新已有安装时保留个人已选声音。要主动切换现有默认，运行下面的设置命令，或完整安装加 `--voice-profile B2`。当前课程的录音和已冻结课程不会随默认设置改变。

## 5.4.0 的配音制作要求

- **自然**：使用普通、正常的培训讲述，平实、亲切，不拖长音，不夸张表演、过度煽情或逐字重读，句尾及时收住。
- **标准**：标准普通话，专业名词、数字、单位和缩写准确；结合真实语境核对。
- **干脆**：语句利落，停顿帮助理解，速度不能太慢。以已确认的实际小样为准，不把一个倍率硬套不同生成结果。
- **连贯**：长课沿用同一已确认 speaker 或参考音频，以完整语义段连续生成，检查声线、语气、响度和接缝。每段重新做 VoiceDesign，即使描述和 seed 相同，也不能保证同一声线；可以先确认一次设计声线，再用其干净片段与准确文本进行 Base 参考克隆。

逐句核对内容是否完整，特别是每个生成段的最后一句。缺尾需要补录；可提供同声线的后续语境，在真实边界裁掉辅助内容。不能把缺失口播用字幕补齐。保留生成原声、实际处理参数和复核范围；ASR 与电平检查不等于实际听校。既有冻结配音不自动修改。完整规则见[课程工艺](../skills/corporate-training-motion/references/36-course-craft.md)。

## 用对话修改

- “这门课使用默认 B2。”
- “这门课改用 Aiden，保持原速；先给实际试听。”
- “用我提供的参考录音和逐字文本克隆配音，先做短样。”
- “B2 再平和一点，重音轻一些；先用同一段内容试听。”
- “把这个声音设为以后新课默认。”只有这类明确要求才修改全局默认；一次课程另选只影响该次生成。

## 三种生成方式

| 方式 | 模型变体 | 用途 |
|---|---|---|
| 默认 B2 / 文字改音色 | VoiceDesign | 根据固定中文描述生成教学男声，也可修改描述 |
| 其他预设 | CustomVoice | Aiden、Dylan、Eric、Ryan、Uncle_Fu、Vivian、Serena、Ono_Anna、Sohee |
| 自己克隆 / B2 参考克隆 | Base | 参考音频加逐字文本；`B2-clone` 使用包内 B2 参考 |

三种方式由同一脚本实际路由。权重不包含在 ZIP 中；完整安装只下载选中的模型。另选方式需提前安装对应模型。模型版本与声音配置在 [profiles.json](../skills/corporate-training-motion/assets/voice/profiles.json)，非敏感本机路径在 `~/.config/corporate-training-motion/voice.json`，也可用 `COURSE_CONFIG_DIR` 指定配置目录。

## 命令行切换

以下命令在解压后的 `kgxc-course-suite/` 或仓库根目录执行；`approved.txt` 是实际已确认的口播正文。输出必须使用新文件名，脚本不会覆盖旧录音。

```sh
# 仅查看声音、模型、默认参数，不下载或生成
python3 skills/corporate-training-motion/scripts/qwen3_tts.py --list-voices
python3 skills/corporate-training-motion/scripts/qwen3_tts.py --profile B2 --dry-run

# 本次用 B2，不修改个人默认
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --profile B2 --text-file approved.txt --out B2.wav

# 将 B2 设为以后默认；自动备份原 voice.json
python3 skills/corporate-training-motion/scripts/qwen3_tts.py --profile B2 --set-default

# 本次换成预设 Aiden；采用该预设自然交付速度 1.0
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --voice Aiden --text-file approved.txt --out aiden.wav
```

模型未准备时运行完整安装，例如 `./install.sh --voice-profile Aiden`；这是明确选择并安装该声音，保留其他已下载模型。`--skill-only` 只更新技能文件，不下载权重，也不改个人默认。安装环境尚未准备时先按[依赖说明](DEPENDENCIES.md)完成准备。

优先级为：本次命令参数 → 指定配置文件/个人配置 → 包内 B2。使用 `--profile` 或 `--voice` 会切到对应模型变体，不会把 B2 的 VoiceDesign 模型误配给 Aiden。已有课程继续沿用已确认声音。

## 克隆自己的配音

准备一段干净、单人、自然说话的参考 WAV，建议约 5–15 秒；另存一份与参考音频一致的逐字文本 `my-reference.txt`。这是制作建议，不是模型的硬性时长限制。使用自己的声音或有权使用的声音；参考音频留在本机，脚本不上传。

```sh
# 首次准备 Base 模型和配音环境，也会生成 B2 参考克隆探针
./install.sh --voice-profile B2-clone

# 本次改用自己的参考音频，不修改个人默认
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --profile B2-clone --ref-audio my-reference.wav \
  --ref-text-file my-reference.txt --text-file approved.txt --out my-voice.wav

# 想以后都用这个参考，增加 --set-default
# 想恢复默认，运行 --profile B2 --set-default
```

`B2-clone` 是可选路径，使用 [B2 原始参考](../skills/corporate-training-motion/assets/voice/B2-reference.wav)和[对应文本](../skills/corporate-training-motion/assets/voice/B2-reference.txt)。当前整课批准的是 B2 VoiceDesign；克隆后的相似度、发音和末句完整性须另试听，不能把配置相同当成同一声音的证明。

## 调整音色、语速和生成长度

B2 的固定描述、模型提交和 seed 保存在 `profiles.json`。默认 `temperature=0.65`、`top_p=0.9`、`repetition_penalty=1.05`、`seed=20261020`、非流式。模型原始生成速度为 **1.0**；B2 的交付默认 **1.1 倍保音高加速**，与已确认课程一致。原始 WAV 始终保留为 `.raw.wav`，工作台播放仍是 1×，不应再次叠加 1.1 倍。

```sh
# 本次恢复原始速度，不改音调
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --profile B2 --delivery-rate 1.0 --text-file approved.txt --out B2-natural.wav

# 将新的完整声音描述写入 voice-description.txt，再做试听
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --profile B2 --instruct-file voice-description.txt \
  --text-file approved.txt --out B2-revised.wav

# 少量较长语义段可提高上限；不是保证完整性
python3 skills/corporate-training-motion/scripts/qwen3_tts.py \
  --profile B2 --max-tokens 7000 --text-file section.txt --out section.wav
```

声音描述决定 VoiceDesign 的音色与表达；改“平和、从容、重音轻一些”比直接改音高更贴近本次需求。`--seed` 可调整采样；同一描述、seed 和版本也不保证每次音色主观完全一致。预设模式也可用描述调整风格；Base 克隆的音色来自参考音频，不接受 `--instruct-file`。

长课优先少量完整语义段，保持同一配置，听校衔接；不要机械逐句换声。达到 token 上限时脚本拒绝提交交付音频。核对首句、末句、计算数字、百分比、练习问答及全文覆盖后再排画面；未达到上限同样可能漏读。WAV 相邻 JSON 保存真实模型提交、参数、原声/交付哈希、参考哈希和待试听状态。

上述模型方式与 [Qwen3-TTS 官方说明](https://github.com/QwenLM/Qwen3-TTS)、[MLX Audio 实现](https://github.com/Blaizzy/mlx-audio)对应；本包固定版本，不自动追随上游变动。仅本地生成，无静默云服务替换。
