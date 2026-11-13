# 素材库的使用证据

资料页的文件列表取自当前课程已登记的原件，不扫描其它目录。原件对照只表示对应业务要点在讲稿中的取舍，不证明图片已上屏；分镜图片台账只表示计划。没有当前实际画面证据时显示「待核对」。不回填旧课，不因换版本自动沿用旧画面记录。

制作端实际播放当前输出后，可将逐项素材复核保存到当前课程 `project/material-video-usage.json`。当前不自动生成这份记录；场景图的引用和文件存在不足以自动认证。以当前小样或成片自己播放器的秒数记录从可辨认出现到消失的区间，不使用整课绝对时码标注独立的小样文件。

```json
{
  "schema": "material-video-usage/1",
  "materials": [
    {
      "source_id": "SRC-<当前原件ID>",
      "source_sha256": "<原件字节SHA-256>",
      "placements": [{
        "stage": "pilot",
        "artifact_path": "../delivery/样片.mp4",
        "artifact_sha256": "<实际视频字节SHA-256>",
        "start_seconds": 3.4,
        "end_seconds": 6.2,
        "segment_label": "开业前一日：门店检查",
        "method": "encoded-video-viewing",
        "evidence": "实际播放输出，画面在此区间清楚展示门店检查照片。"
      }]
    },
    {
      "source_id": "SRC-<另一原件ID>",
      "source_sha256": "<原件字节SHA-256>",
      "status": "excluded",
      "reason": "与已保留的现场照片重复，不提供额外教学信息。"
    }
  ]
}
```

资料页只接受当前工作台仍在展示的对应阶段视频、相同文件路径及 SHA-256，且已有当前编码元数据和合法时间范围的记录。视频被换版后，旧位置自动失效；证据不冒充人工确认。明确排除需要原件 SHA-256 和具体原因，也可沿用 `source_images.json` 中已复核、能和当前原图明确绑定的排除项。
