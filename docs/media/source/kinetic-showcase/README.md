# 酷果星创 · 64 秒鼓点版宣传与动效图谱

- **节奏**：参考旧宣传片约 120 BPM 的拍点和强弱起伏，新谱写底鼓、军鼓、踩镲和旋律，不复用旧录音。
- **画面**：先看懂规则、再看会操作、最后练判断。以前已公开的 17 支演示和一支翻页补样取真实画面并静音使用；再按六类快速展示正式版的 100 种原生动作。
- **图谱**：正式 v6.9.8 的工作台从每项真实动作导出 12 个相位，可单独播放、暂停、逐帧和按用途查询。动作清单和图谱为通用技术演示；不冒称一门实际课程的完整验收。
- **旧作品保留**：[36 秒设计短片](../kgxc-motion-promo.md) · [17 支独立样片](../../../SHOWCASE.md)。
- 本次更新展示资产与文档，不改变 Skill 6.9.8 / DSH 0.9.9 的安装包与原校验文件。

## 复现

在仓库根目录、Ubuntu 环境安装 ffmpeg、fonts-noto-cjk、python3-pil、python3-numpy。用已安装 requirements.lock 与 Playwright Chromium 的 Python 导出动效，其他命令用系统 Python：

    src=docs/media/source/kinetic-showcase
    python "$src/export_action_atlases.py" --repo . --chrome "$CHROME_HEADLESS_SHELL" --out dist/promo-atlases --version v6.9.8 --source-commit 7bfd2f9b3e3e0fec33b454c7f95de6b41135fa18
    /usr/bin/python3 "$src/kgxc-kinetic-score.py" --output dist/kinetic-score-64.wav
    /usr/bin/python3 "$src/kgxc-kinetic-showreel.py" --repo-root . --actions-root dist/promo-atlases --audio-file dist/kinetic-score-64.wav --output-dir dist
    python "$src/build_action_catalog.py" --atlas-root dist/promo-atlases --output dist/kgxc-motion-actions-100.zip

图谱 ZIP 包含 100 张动效图集及索引。播放器中的 12 相位是从真实动作抽样，不是补间后的全帧视频；可从独立原生工作台看逐帧连续运动。
