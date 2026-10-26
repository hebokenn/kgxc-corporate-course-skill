# 第三方与素材说明

- `skills/corporate-training-motion/libraries/web/`：原 code-video-director 实现，保留原 MIT 许可证及版权声明。
- `skills/corporate-training-motion/libraries/illustration/`：原 huashu-art-motion 实现，保留原 MIT 许可证及版权声明。
- 字体沿用各自许可，不由仓库通用声明覆盖；详见库内 `lib/fonts/LICENSES.md`、`OFL.txt` 和品牌字体 `assets/bookends/FONT-LICENSE.txt`。
- 示例中其他字体/绘画资产的原许可文件随对应目录保留，包括参考示范中的 ARPHICPL.TXT。
- 酷果星创 Logo、人物、业务术语、案例、R5/R8 包装与参考配乐保留现有企业用途及来源记录。本次由用户授权在公开仓库保留；公开可下载不代表第三方可冒用品牌，也不替权利方授予企业素材对外商业再授权。
- R5/R8 采用原始批准的固定背景、声音和独立标题合成。可分发背景是无损视频资源，不依赖开发者的临时帧目录；Blender 工程另行打包外部图片。来源见 `assets/bookends/packaging-provenance.json` 和 `approved-source.json`。
- `assets/sfx/kenney-interface-source`：Kenney Interface Sounds 100 个原始 OGG，CC0，保留 License.txt 与 source.json；`natural-ui-v1` 是其短切、EQ 与动作组合衍生，沿用 CC0。来源 https://kenney.nl/assets/interface-sounds 。
- `assets/voice/B2-reference.wav`：用户选定的 Qwen3-TTS VoiceDesign 合成参考，非真实人物身份；用于配音试听与可选参考克隆。
- `skills/corporate-training-motion/assets/voice/recommended/didi` 与 `pipi`：发布者依用户于2026-10-26的明确授权，公开这两套推荐参考WAV、对应文本与通用配置，用于本Skill的本地参考克隆；不附私人来源文件或原课程。`docs/media/voices`为同一通用文案的AI合成试听，记录实际模型与文件哈希。推荐仍可由安装者自行更换。
- Python/npm 依赖由各自包管理器从原注册表安装，沿用其许可证。Qwen3-TTS 保留官方项目链接，模型由安装器下载到使用者本地，不放入仓库或ZIP；可选 Remotion 保留为单独原型，使用者须自行核对适用许可。

本仓库没有为所有企业与第三方素材另行授予统一开源许可。各来源文件的许可证和企业内部用途说明继续适用。

## 5.7.0 visual libraries

Lucide 0.468.0: 30 SVG icons, ISC. Original LICENSE and exact source/hash are under `skills/corporate-training-motion/assets/open-source/lucide/`.

Kenney Furniture Kit 2.0: selected furniture fixtures only, 36 isometric PNGs and 9 GLB models, CC0. Original license and source archive SHA-256 are under `skills/corporate-training-motion/assets/open-source/kenney-furniture/`. Electronic merchandise from other brands is not bundled.

The 24 art-direction recipes are original code adaptations informed by linked official portfolios. Links do not grant rights to third-party videos, music, artwork or characters. Open Peeps and Rough.js are documented extension options; their full libraries are not bundled. unDraw artwork is not bundled. User retail photos and local derivatives stay private. Apple-family drawings and the four Blender material scenes are independently authored teaching illustrations, not Apple image files, exact specifications or teardown CAD. Same-source surface processing preserves existing authorized company characters and does not create a new identity.
