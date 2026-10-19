# 内部包的运行与范围

本包含Skill入口、引用、Python脚本、Canvas单行字幕适配器、内置网页及插画引擎、可选Remotion静音原型、合成测试夹具及酷果独立配置/原图/已批准头尾片段。Python基础检查用标准库；媒体检查需本机已有ffmpeg/ffprobe，品牌像素比较另需已有Pillow/numpy；可选Remotion需已有Node/依赖和适用许可。正文优先使用已获许可字体；内置插画引擎随附原实现字体及其LICENSES说明，不引入其他系统字体或自动下载。发布安装器可按用户安装指令准备媒体运行环境；课程制作本身不静默安装依赖或触发付费服务。

本项目新配音默认使用本地Qwen3-TTS的Aiden原速，读[本地Aiden](23-local-qwen3-voice.md)并调用`scripts/qwen3_tts.py`。完整发布安装器会自动部署MLX、mlx-audio、numpy、soundfile与固定提交模型并生成短句自检；仅手动复制Skill时须另行准备这些依赖；机器运行器引用保存在安装目录外的用户配置，不随包内置权重或Python环境。

3.3.0内置同步区间裁剪，延续每门新课默认接入工作台的流程，见[工作台操作](27-content-workbench.md)。启动与保存使用Python标准库；波形与媒体检查需要已有ffmpeg/ffprobe，导出使用本机配置的Python Playwright和浏览器；3.4完整安装默认准备独立Chromium。安装Skill后由本入口运行内置启动器并显示本地URL，不会因为复制Skill而自动运行后台服务。scaffold创建的课程自带独立启动器，交付检查要求实际编辑数据及运行验证。工作台导出的课程ZIP含该课私有源码、素材和音轨，仅用于用户授权的本地编辑；它与这里不含课程资料的通用Skill安装包不同。

运行例：`python3 scripts/test_single_line_subtitles.py`、`python3 scripts/check_layout_clearance.py --self-test`、`python3 scripts/check_skill_package.py .`。`scaffold.py DESTINATION`新建酷果工程，带品牌配置和原始素材；不自动生成配音或成片。需要酷果时按`assets/profiles/kgxc/profile.json`复制资源，路径相对配置目录解析，不使用开发机历史绝对路径。

检查角色动作前加载19，字幕读20，已知失败与边界读21。发布计划由当前项目实际文件生成，传给`release_checks.py PLAN.json --out REPORT.json`：video/captions/caption_metrics各含相对path和sha256，assets列所用原件，caption_safe为实际字幕区域，duration为成片时长。brand_required为真时需actual_brand_comparison指向本次比对证据；visual_review/normal_speed_playback/human_audio_review分别记录status、video_sha256与scope。technical_ok与release_ready分别报告，未人工听审保持pending。

用户已授权公开本仓库并保留企业信息；品牌与企业案例的用途仍为酷果星创内部课程，第三方实现与字体沿用原许可。没有API key、凭证、用户聊天日志、原业务PDF/原课程逐字稿、整课音轨或大型渲染帧缓存。合成例子不是企业政策，历史头尾烘焙文字不能直接编辑；3.4通过内置无损背景、原配乐、跟踪和独立标题合成器实现换课名，不需要外部工程。
