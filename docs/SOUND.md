# 自然界面音效库

[返回首页](../README.md) · [逐项试听 HTML](../skills/corporate-training-motion/assets/sfx/natural-ui-v1/audition.html) · [动作调用与混音](../skills/corporate-training-motion/references/31-action-sound.md)

默认使用 `natural-ui-v1`。基础素材来自 [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds)，100 个音效以 CC0 发布，原始 OGG、[许可证](../skills/corporate-training-motion/assets/sfx/kenney-interface-source/License.txt)和[来源/哈希](../skills/corporate-training-motion/assets/sfx/kenney-interface-source/source.json)随包保留。常用库整理为 **15 类 × 3 个变体 = 45 个 48kHz PCM16 WAV**，不用原来的滤波噪声合成器。

| 调用角色 | 听感与用途 | 示例 |
|---|---|---|
| `click` | 短促轻触 | 按钮按下、确认选择 |
| `build` | 两次柔和模块落位 | 构建关系、拆分组合 |
| `move` | 短滑动 | 物件移动、路径交接 |
| `zoom-in` / `zoom-out` | 推进 / 退回 | 放大局部、缩回全貌 |
| `appear` / `disappear` | 轻开 / 轻合 | 对象出现、退出 |
| `rotate` | 三段轻微转动卡位 | 旋转归位 |
| `grow` / `shrink` | 向上展开 / 收拢 | 柱条增长、范围收缩 |
| `reveal` | 短拨动展开 | 揭示结果或局部 |
| `focus` | 更轻的选择声 | 聚焦某个对象 |
| `confirm` | 完成反馈 | 核对结果、落定结论 |
| `transition` | 短切换 | 场景或责任交接 |
| `warning` | 柔和短提醒 | 条件不符、需回看 |

解压完整包后打开 `skills/corporate-training-motion/assets/sfx/natural-ui-v1/audition.html`。可单独试听、比较三个变体或连续播放，页面显示实际动作与声音。GitHub 源码页不执行 HTML，请下载后打开。原库另含其他点击、开关、滚动等声音；常用库未默认选入 glitch、scratch 等噪声类素材。

[下载动作音效试听 MP4](media/natural-ui-audition.mp4)适合直接查看本版 15 类的动作与声音；这只是库试听，是否适合某门课仍要听课程实际混音。

## 调用、修改、替换

按[动作音效参考](../skills/corporate-training-motion/references/31-action-sound.md)写事件文件，选角色、事件帧、对齐方式和音量。`assetId` 可固定具体变体；`none` 保留静音。计划生成后复制实际 WAV 并登记哈希，恢复后不会随机换音。

- 想更轻：降低该事件的 `gainDb`，再从干净旁白重混。
- 想换同类声音：例如 `role=click` 配 `assetId=click-3`，重新生成计划。
- 想调对位：用 `align=start|peak|end`，按真实动作启动、接触或完成点设置帧。
- 想用自己的素材：先登记为新的课程库版本，保留来源/许可和哈希，统一 48kHz 单声道 PCM16；不要直接覆盖既有库文件并沿用旧计划。
- 想恢复旧课程：显式指定原 `soft-tactile-v1`，旧计划仍按原素材读取；不会因安装更新自动重混。

混音工具保持原旁白文件与时间轴，另存音效分轨、混音和来源记录。有声段轻度避让；练习思考和阅读留白。更换现有课程音效要从保留的干净分轨重做，不能在旧成品上叠加。听感需在实际正常速度混音中判断，技术检查不代填用户认可。

## 从来源重建

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import sys
from pathlib import Path
root=Path('skills/corporate-training-motion')
sys.path.insert(0,str(root/'workbench'))
from sound import build_palette,PALETTE
build_palette(root/'assets/sfx'/PALETTE)
PY
```

使用包内 100 个原始素材和本机 FFmpeg，离线生成。EQ、短切、淡出、构建及转动组合在 `workbench/sound.py`；固定来源可复核，跨 FFmpeg 版本不保证字节完全一致，应重新保存素材哈希与计划。CC0 素材可以随本包分发；其他品牌和字体素材沿用各自原说明。
