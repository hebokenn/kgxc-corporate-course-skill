# 酷果星创企业制课：让规则好读，让动作会说话

36 秒项目介绍片。示例完全虚构，不是门店制度，也不是实机界面录屏；不使用真实课程、客户资料或第三方角色。影片按静音观看编排，短提示音由代码合成，不使用第三方音乐或声音。

| 时间 | 内容 |
| --- | --- |
| 00:00–00:05.4 | 品牌和开场：把关键动作讲明白 |
| 00:05.4–00:12.2 | 同一条规则对照：从连续文字到动作、核对项和相邻限制 |
| 00:12.2–00:25.2 | 虚构数据迁移：保留旧机、卡片预备与弧线运动、落定、检查新机，再请顾客确认 |
| 00:25.2–00:31.0 | 制作的四项成果：讲稿、分镜、有声小样、整课 |
| 00:31.0–00:36.0 | 项目入口 |

- F 型图文扫读取自 [Nielsen Norman Group 原研究说明](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/)；用来优化规则页的扫描起点和读序，不要求所有镜头套 F 形。
- 动作参考经典迪士尼动画准则（[The Illusion of Life: Disney Animation](https://books.disney.com/book/the-illusion-of-life/)）：调度、预备动作、弧线、速度节奏和落定。仅用于解释一般动作方法，不含迪士尼素材或官方合作。
- 品牌图形为本仓库原版 `skills/corporate-training-motion/assets/brand/kgxc-logo.png`；只用非透明范围显示，不改图形颜色。中文字体用系统安装的 Noto CJK。

## 复现

在 Ubuntu 上安装 `ffmpeg fonts-noto-cjk python3-pil` 后，在仓库根目录运行：

```sh
/usr/bin/python3 docs/media/source/kgxc-motion-promo.py --repo-root . --output-dir dist
ffmpeg -v error -xerror -i dist/kgxc-motion-promo.mp4 -f null -
```

将额外参数 `--contact` 传给渲染器可输出分镜抽帧联系表；`--preview-only` 可只输出海报和联系表。视频为 H.264/AAC，1920×1080，30 fps。
