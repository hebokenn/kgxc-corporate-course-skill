# 默认 B2 与可选配音

2026-10-21 用户要求后续新配音默认采用已确认整课的 **B2 清亮平和教学男声**。实际方案为 Qwen3-TTS VoiceDesign，固定描述、模型提交、seed 及 1.1 倍保音高交付参数在 `assets/voice/profiles.json`。原始生成速度 1.0，原 WAV 保留；工作台播放 1×，不重复加速。

这是默认选项，不是唯一选项。本次明确另选、个人已保存的声音和既有批准录音优先。脚本支持 CustomVoice 的九个预设、VoiceDesign 文字改声，以及 Base 参考音频克隆。不得把所有模式硬编码成 Aiden 或同一模型；默认配置在 Skill 外，权重不入工程/发布包。

```sh
python3 SKILL_DIR/scripts/qwen3_tts.py --list-voices
python3 SKILL_DIR/scripts/qwen3_tts.py --profile B2 --dry-run
python3 SKILL_DIR/scripts/qwen3_tts.py --text-file APPROVED.txt --out VOICE.wav
python3 SKILL_DIR/scripts/qwen3_tts.py --voice Aiden --text-file APPROVED.txt --out OTHER.wav
python3 SKILL_DIR/scripts/qwen3_tts.py --profile B2-clone --ref-audio REFERENCE.wav --ref-text-file REFERENCE.txt --text-file APPROVED.txt --out CLONE.wav
```

一次另选只作用于该次；明确“以后默认”才使用 `--set-default`，自动备份配置。更改音色用 `--instruct-file`；交付语速用 `--delivery-rate`；本地模型路径用 `--model`。克隆参考和逐字文本必须对应。完整安装可用 `--voice-profile` 准备对应模型；离线生成时不下载或换供应商。

输出不存在才生成，真实参数和原声/交付哈希写入 WAV 旁 JSON。长文用少量完整语义段，保持相同配置并实听衔接；首尾、数字、百分比和练习全文覆盖必须核对，token 上限和 ASR 不能替代听校。相同 seed 不证明声音身份稳定。改变声音方案先出本课实际有声小样，沿用仍有效的确认，不改已有冻结录音。

完整切换、模型安装、克隆、改声及速度示例随发布仓库 `docs/VOICE.md` 提供；本技能内的实际参数源是 `assets/voice/profiles.json` 和 `scripts/qwen3_tts.py`。
