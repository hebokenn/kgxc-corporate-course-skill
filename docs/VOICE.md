# 配音：推荐 didi 男声、pipi 女声，可试听、调整与克隆

[返回主页](../README.md) · [使用指南](USAGE.md) · [安装与依赖](DEPENDENCIES.md)

## 推荐声音与试听

从 **v5.8.6** 起，完整新安装默认推荐 **didi 男声、pipi 女声**；未指定性别时使用 didi。这是制作者选过、较适合常见培训讲解的两套声音，方便先开始制作，再按课程需要调整。推荐不限制你的选择：可切换男女声、其他预设、文字设计的新音色或自己的参考克隆。

两套声音的参考 WAV、准确逐字文本和配置均随源码及安装包提供。完整安装准备同一个本地 Qwen3-TTS Base 模型，即可使用两者，无需另找参考录音或填写 TTS API Key。仅复制 Skill 的 `--skill-only` 安装仍需已有媒体及配音环境。

| 推荐声音 | 适合先尝试的场景 | 试听及对照 | 调用 |
| --- | --- | --- | --- |
| didi · 教学男声 | 任务说明、步骤讲解、重点提醒；声音清晰轻亮，有自然起伏 | [试听 MP3](media/voices/didi-audition.mp3)、[WAV](media/voices/didi-audition.wav) | `--gender male` 或 `--voice didi` |
| pipi · 教学女声 | 课程导入、概念解释、服务情境；声音清楚亲切 | [试听 MP3](media/voices/pipi-audition.mp3)、[WAV](media/voices/pipi-audition.wav) | `--gender female` 或 `--voice pipi` |

[双播放器试听页](media/voices/audition.html)需下载该目录后打开；GitHub 源码页不会执行 HTML。两段试听使用[同一段通用文案](media/voices/audition.txt)，均为 AI 合成，以 `1.0` 交付倍率生成。先比较音色、语气、发音与节奏，再用自己的课程内容试听。推荐是制作起点，不代表不同文本下的效果完全一致。

**已有安装升级保留个人选择与原录音。** 如果你以前选择了 B2、Aiden 或自己的声音，升级不会强制改成 didi。B2 VoiceDesign、B2-clone 与其他预设继续可用；历史课程不自动重新配音。

## 先用自然语言选择

- “这门课用推荐男声 didi，先给一段含提问、步骤和英文名称的试听。”
- “这门课改用 pipi 女声，语速稍快一点，先比较同一段文案。”
- “保留这个音色，把停顿和重音调整得更适合这句话。”
- “用我有权使用的这段录音及准确文本克隆，先做短样。”
- “把这个声音设为以后新课默认。”只有明确要求保存默认时才改变个人设置；本次另选只作用于本次生成。

同一讲师尽量使用同一已确认参考或预设，以完整语义段生成。真实课程中的数字、专业词、英文名称、句尾与接缝仍要试听核对；字幕、ASR 和电平检查各有用途，不代替听感判断。

## 命令行开始使用

先在终端指定实际安装目录。Codex 默认路径如下；WorkBuddy 使用 `$HOME/.workbuddy/skills/corporate-training-motion`，自定义安装则替换为实际路径。

```sh
SKILL_DIR="$HOME/.agents/skills/corporate-training-motion"
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --list-voices
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --gender male --dry-run
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --gender female --dry-run
```

`--dry-run` 只核对最终选择、参考文件、模型及参数，不合成、不下载、不改默认。将本段口播写入 UTF-8 的 `sample.txt`，再生成；输出文件名应使用新的名字，脚本会保护已有录音。

```sh
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --gender male --text-file sample.txt --out didi-sample.wav
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --gender female --text-file sample.txt --out pipi-sample.wav
```

`--gender` 优先使用你保存的该性别默认，没有个人配置时用随包的 didi / pipi。`--voice didi`、`--voice pipi` 是本次明确选择；如果你已在私有库注册同名声音，个人版本优先，损坏时会报错，不静默换回另一套参考。

## 怎样调试语速、节奏和发音

先取一段完整而有代表性的课程文字，保留原样对照，每次只改变一个因素。先检查文字是否适合讲述，再判断声音需要什么调整。

| 想调整的效果 | 建议做法 | 需要注意 |
| --- | --- | --- |
| 略快或略慢 | 用 `--delivery-rate` 调整交付倍率，例如 `1.05` 稍快、`0.95` 稍慢 | didi / pipi 默认 `1.0`；倍率越大越快，使用保音高处理，原声另存，避免再次叠加提速 |
| 提问、提醒和总结的节奏 | 调整完整句子的表达、标点、分句及参考录音，比较同一段内容 | Base 克隆主要跟随参考表现；不能用不支持的情绪指令承诺保持原音色又精确改变表演 |
| 尝试另一个生成结果 | 保留同一参考，使用另一个 `--seed` | 相同参数也不保证每次主观听感完全一致；先试听再选 |
| 产品名称、字母缩写或数字读错 | 保留标准讲稿与字幕，为配音输入单独记录读法或别名，重生成完整语义段 | 如 Mac 与 SN 的读法不同；检查所有重复位置及前后接缝 |
| 换一种音色 | 另选预设、VoiceDesign 或参考克隆 | 音色设计与原音色克隆是不同路径，新候选应分别试听 |
| 句尾缺字或段落太长 | 检查实际音频，拆成较少的完整语义段；必要时合理提高 `--max-tokens` 后重生 | 上限参数不保证内容完整，不能用字幕补齐缺失口播 |

例如，保持 didi 音色，比较原速与略快版本：

```sh
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice didi --delivery-rate 1.0 --text-file sample.txt --out didi-rate-100.wav
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice didi --delivery-rate 1.05 --text-file sample.txt --out didi-rate-105.wav
```

原始生成速度保持 `1.0`。有后期变速时，`.raw.wav` 保留原录音，输出 WAV 是实际交付速度，旁边 JSON 记录参数与哈希。工作台用正常 `1×` 播放，不再次乘相同倍率。整课后期提速或升调需同步画面、字幕与章节，见[后期与时间线规则](../skills/corporate-training-motion/references/37-cover-and-delivery-finish.md)。

## 怎样换预设或用文字设计音色

| 路径 | 对应模型 | 用途 |
| --- | --- | --- |
| didi / pipi、个人参考克隆、B2-clone | Base | 以参考音频和准确文本复用声音特征 |
| Aiden、Dylan、Eric、Ryan、Uncle_Fu、Vivian、Serena、Ono_Anna、Sohee | CustomVoice | 选择现有预设；需准备该模型变体 |
| B2 与文字改声 | VoiceDesign | 用描述生成新的候选音色；需准备该模型变体 |

完整安装默认准备 Base。想用其他变体时，先在解压后的安装包目录执行相应安装命令：

```sh
./install.sh --voice-profile Aiden
./install.sh --voice-profile B2
```

这是明确选择并准备相应声音的安装操作，会保留已下载模型。之后仍可单次指定 `--voice didi` 或 `--voice pipi`。离线生成不自动下载缺少的模型。

把想要的新音色描述写入 `voice-style.txt`，例如“成年培训讲师，标准普通话，清晰亲切，语气自然，句尾干脆”。先生成新的短样比较：

```sh
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --profile B2 --instruct-file voice-style.txt --delivery-rate 1.0 --text-file sample.txt --out designed-sample.wav
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice Aiden --text-file sample.txt --out aiden-sample.wav
```

`--instruct-file` 用于支持指令的模式；本工具在 Base 克隆模式会拒绝它。反复独立设计即使描述和 seed 相同，也可能有音色变化；选中一个设计声线后，可保留干净录音与逐字文本，再用 Base 克隆维持后续参考。模式区别见 [Qwen3-TTS 官方说明](https://github.com/QwenLM/Qwen3-TTS#readme)。

## 怎样克隆自己的声音

准备你有权使用的短参考录音，优先选择单人、干净、完整语义片段；避免音乐、混响、多人重叠、削波和被截断的词。另备 UTF-8 文本，准确写出参考音频里真正说出的内容。参考文本描述录音，`sample.txt` 则是要新合成的内容，两者用途不同。

如果原件是其他音频格式，可以先转换成便于处理的 WAV，原件继续保留：

```sh
ffmpeg -n -i my-recording.m4a -ac 1 -ar 24000 my-reference.wav
```

只在这一次使用参考，不改变默认：

```sh
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --profile B2-clone --ref-audio my-reference.wav --ref-text-file my-reference.txt --delivery-rate 1.0 --text-file sample.txt --out my-clone-sample.wav
```

想以后按名称复用，就注册到私有本地库：

```sh
python3 "$SKILL_DIR/scripts/voice_library.py" register --id my-teacher --audio my-reference.wav --text my-reference.txt --label "我的教学声音" --origin "本人提供或已获授权的参考录音" --delivery-rate 1.0
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice my-teacher --dry-run
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice my-teacher --text-file sample.txt --out my-teacher-sample.wav
```

也支持中文名称，例如 `示例讲师`；ID 为 1–64 个英文字母、汉字、数字、下划线或连字符，不使用路径。注册保存参考副本与哈希，不覆盖同名项、不自动改默认。原参考改变会报错，修订时用新的 ID 注册并重新试听。

## 怎样保存默认、恢复推荐

本次单独换声使用 `--voice` 即可。如果明确想把当前主声音保存为以后默认，先试听再执行：

```sh
python3 "$SKILL_DIR/scripts/qwen3_tts.py" --voice pipi --set-default
```

要分别保存男女声并选择未指定性别时的主声音，使用：

```sh
python3 "$SKILL_DIR/scripts/voice_library.py" set-defaults --male didi --female pipi --default-gender male --evidence "我选择 didi 为默认男声、pipi 为默认女声"
python3 "$SKILL_DIR/scripts/voice_library.py" defaults
```

恢复推荐的男女声名称组合也可使用上面的命令；同名私有参考仍按个人优先，不会被删除或覆盖。把相应 ID 替换为已注册私有声音，即可建立自己的男女声组合。选择会备份原 `voice.json` 与已有默认配置，保留本机运行环境；不会重录历史课程，也不会改写随包参考文件。

## 文件、隐私和实际验证

这次明确公开的推荐素材仅为 didi / pipi 的参考 WAV、逐字文本、通用配置和通用试听；其他个人录音、参考片、声音库及课程原件继续留在本地，不随公共包发布。参考路径在安装后解析到包内资源，不依赖制作者电脑。私有库换机时需另行迁移获授权的参考 WAV、文本与 profile。

声音参数、参考哈希、模型模式、音频解码和安装检查属于技术验证；ASR 可辅助检查内容。音色喜好、自然度和当前课程的适配仍应实际试听。本版实际验证范围见 [v5.8.6 验证记录](V5.8.6-VERIFICATION.md)。
