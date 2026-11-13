# 工作区、唯一最终版与清理

## 固定分层

工作区根目录仅放 README、项目集合及必要配置。课程放 courses/<course-id>/；可复用品牌母版和动画库放 libraries/；制作方法研究、外部材料与通用文档放 docs/training-production/；Skill 只放 .agents/skills/。其他独立作品保持项目边界。

```text
courses/<course-id>/
  README.md                 当前入口、规格、复验命令
  workspace.json            当前交付路径、SHA256、目录约定
  inputs/                   原始制度、原件、用户口径及原始确认
  project/                  唯一当前可修改工程
    project.json            生产设置与来源路径
    source_rules.json       有效规则台账（根文件为机器入口）
    script_segments.json    稿件、分镜、真实确认等少量结构数据
    storyboard.json
    source/                 渲染/复验/音频处理脚本、批准的录音文本/SSML
    assets/                 品牌、字体、授权素材、私有参考
    audio/                  raw原带、processed必要派生、母带、音效来源
    qa/                     仅当前有效报告、连续联系表、必要回归图
    work/                   临时帧、silent/pending、日志、锁（可清理）
    composition.html        实际引擎入口（也可为src/）
  delivery/                 唯一当前MP4、SRT、播放页、交付说明、manifest
  packages/                 唯一当前可修改工程包
```

原件只保存一份；台账与批准文本是派生数据，明确用途。根目录不放 v1/v2/v16 同级工程，不把音色试听放正式 audio/，不把过时 ZIP 留在 packages/。版本号写进成片名、manifest 与变更记录；活跃修改只用 project/，实际交付只用 delivery/。缓存、失败候选和试渲写 work/，绝不把 work/ 打包。

`workspace.json` 记录 layout_version、current_version、project_dir、delivery_dir、package_dir 与 retain_artifacts（课程根相对路径及SHA256）。工程不依赖同级旧版本；导入品牌母版时复制实际已确认素材并记录哈希。课程包必须离线拥有完整源码、原音、时间轴、字幕、来源与检查脚本，执行环境/字体另行明确；不依赖被清理版本的 HTML 模板。

## 新建、迭代、交付

1. scaffold 建工程，原件入 inputs/，所有本课资产入 project/。project.json.source_file 从 project/ 相对指向 ../inputs/原件。
2. 审核界面可有制作状态，成片只出现学员需要的信息。联系表和 QA 入 project/qa/，说明文档入 delivery/。
3. 活跃修改可在 work/ 暂存上一次可恢复产物；正在使用的当前交付不被失败渲染覆盖。无明确保留要求时不无限创建整套历史复制。
4. 最终输出先写 work/独立文件，检查后原子提交 delivery/。打包脚本按白名单收集 inputs/、project/、delivery/、workspace.json 和所需 Skill；跳过 work/、缓存、旧ZIP、私密配置与重复派生。
5. 收尾检查唯一成片、链接、断点跳转、源工程短帧渲染、最终哈希、ZIP CRC；workspace_check 检查整理结果。目录迁移而字节未变时明确写“沿用已绑定哈希的成片验收”，不要伪称重新渲染。

## 用户授权清理旧版时

先盘点精确路径/占用，确定当前成片、字幕、音轨、源码、来源与最终 QA；记录保留哈希及待删清单。检查所有运行脚本的旧路径、上游库、软链接和预览进程。先把最终工程变为自包含，验证移位后仍可打开和绘帧，再删除清单内的旧版/旧试听/失败中间片/重复压缩包。

仅操作这门课与明确归属其历史的审阅产物。共享品牌母版、素材许可、通用动画库和其他课程/作品不得因名字相似而删掉；跨目录共享资产先分辨使用者。用路径边界检查及显式清单，禁止未经核对的根目录通配删除。停止旧服务时核对 PID、命令与工作目录；不得广泛杀掉所有 Python/Node/Chrome。

清理结果写 project/qa/workspace-cleanup.json：删除路径、字节、保留哈希、依赖检查、当前预览、整理前后占用。此记录是清理凭据，不代替业务确认。旧报告中的版本名可作为历史证据保留；运行依赖和当前入口不可指向已删除路径。不为“安全”把所有旧版藏入 archive/，也不默认保留旧的试听音色与私有云日志。

## 可选旧工具兼容

既有工具仍可直接接收旧的单目录工程。规范工程传 COURSE/project；validator 自动识别父级 workspace.json 并到 ../delivery 寻找成片/字幕、到 audio/ 寻找冻结旁白。真实确认记录的文件路径以 project/ 为基准，边界限制为所属课程，不允许指向其他项目。
