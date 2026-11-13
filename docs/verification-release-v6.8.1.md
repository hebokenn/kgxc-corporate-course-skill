# 正式发布验证：DSH 插件 0.8.23 / 制课核心 6.8.1

日期：2026-11-09。联合包教学设计模块为 2.0.6。

[主页](../README.md) · [插件使用说明](PLUGIN.md) · [完整更新历史](CHANGELOG.md)

## 验证边界

本次只验证插件代码和隔离合成课程。没有启动、接管或修改真实课程，没有调用外部模型，没有更改模型或收费来源，也没有替换正在使用的本机 DSH 安装。原有工作区修改保留，正式历史、旧标签与附件保留；6.5.0 草稿不作为本次正式版本。

macOS Apple 芯片；使用安装器已有的 Python 3.12.13 运行环境和已安装的 Chromium / DSH 原生依赖。系统 Python 缺少 Playwright / OpenCV 的初轮环境错误单独保留，最终结果以下述正确运行环境实测为准。

## 功能实现核对

| 要求 | 实际实现与证据范围 |
| --- | --- |
| 当前阶段当前方案一次盲审 | `ai_review.py` 的持久阶段/方案周期与调用预约防止再次盲审；重开、新哈希、升级和次数不限不清零。只有真实人工改选新方案才建立新周期，旧累计保留。 |
| 固定清单集中处理 | 盲审意见冻结到 `issue_ledger`；制作端集中修改，再按固定问题、当前证据与直接回归进行定向验收。不能以开放式第二次盲审替代。 |
| 只审已选方案 | `blind_review.py` 对当前成品进行白名单投影；未选备选及未来义务不进入本阶段阻断范围。个人偏好 advisory 保留为建议；缺省、固定关键项与关键未知仍阻断。 |
| 高质量写稿前置 | 作者规范与 `script_quality.py` 在首次盲审前检查问候遗漏、占位及明显重复；自然口语、有效信息、场景动作、示范与练习反馈由制作端自检，不冒称程序证明语义质量。 |
| 原件对照与真实确认 | `source_coverage.py` 保留全部登记独立要点为分母，舍弃及新增理由与依据、critical 关键项分别呈现。读取不足/未知不填100%。人工核对拆点与语义，回执绑定当前 source/script/report SHA；任一变化失效，历史保留。模型工具只读/保存，不提供代确认。 |
| 角色隔离和版本证据 | 独立原生审阅 agent、零工具及当前成品边界；制作与监督身份分离。实际输入、失败、未知用量、累计预算、版本哈希与宿主绑定分别保存。 |

发布前审计额外修复：拒绝未知 finding 严重性，防止个人偏好一律变成关键阻断；拒绝 QA 模拟上下文假冒用户改选方案。新增对应合成回归。

## 本次执行结果

在仓库外快照及合成配置中实际执行，修复冻结后再次核对快照与当前代码字节一致：

| 命令 / 检查 | 本次结果 |
| --- | --- |
| `python -B -m unittest discover -s tests -p 'test_*.py' -v` | 340 / 340 通过，68.176 秒，退出 0、无跳过。 |
| `node --test tests/test_*.mjs` | 115 / 115 通过，33.725 秒，退出 0、无跳过。 |
| `python -B -m unittest discover -s skills/corporate-training-motion/scripts -p 'test_*.py' -v` | 306 / 306 通过，107.455 秒，退出 0、无跳过。 |
| 实际 Chromium 页面 | 36 项计入 Python 340：review_ui 30、native_studio 4、production_progress_ui 2；不是额外累计。 |
| 分支 / 分镜工作流 | 24 / 14 项计入核心 306，不重复计数。 |
| 主页结构和本次文档链接 | “版本更新”位于最后；主页、插件说明、变更历史和本版报告的本地链接逐一存在。 |
| 发布边界与确定性打包 | 新增及既有 18 项定向检查通过，并计入上述完整回归；涵盖 config 白名单、隐藏目录、符号链接、ZIP/TGZ 内容及重复构建字节稳定。 |

实际 DSH 包管理器在合成 profile 中完成安装，冷加载已安装模块注册 10 个工具、2 个 Skill，并实际调用环境工具返回插件 0.8.23 / 核心 6.8.1；没有调用模型或新建课程。profile 的自定义字段、原 cordis 配置字节保留。空白临时 desktop profile 的首次尝试按宿主规则被拒绝，初始化合成 profile 后通过，失败日志保留。

独立 Skill 联合包候选构建已实际成功，两个模块逐文件清单分别为 1267 / 13 项。解压后使用实际安装器在临时 dest/data/config/bin 首次安装两模块返回 `installed`，重复安装返回 `already_current`，全部文件 SHA 与清单一致，工具和声音配置哨兵字节保留。未下载模型或新建媒体运行环境。

此后只补本版公开验证文档并重新构建最终发行包；发布端继续对最终 ZIP 的 CRC、完整逐文件清单、源码对应、外部 SHA 和实际隔离安装进行核对。若任何关键步骤失败，修复后重建，不上传候选包替代。最终包的具体哈希以本次正式 Release 的校验附件及线上回读回执为准。

## 公开内容与安装边界

公开源码和包仅含通用代码、文档、自造测试与已有明确授权的公共资源；新版本没有新增私人媒体。素材授权及限制见 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)。本机试验宿主注册入口不随本次发布，账号配置、凭据、真实课程资料、课程工程及私人审阅记录不入包。

构建对 config 采用通用文件白名单，排除隐藏父目录、符号链接、缓存、课程及私人路径；安装包有逐文件 SHA 清单、ZIP CRC 与外部 SHA256 校验文件。DSH ZIP 包含完整公开文档和合成测试；宿主实际安装 TGZ 只保留运行文件、Skill 与公开说明。隔离安装不等于当前真实课程通过或模型服务可用。

## 下载及校验

- [DSH 插件 0.8.23 安装包](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v6.8.1/kgxc-course-plugin-v0.8.23.zip) · [PLUGIN-SHA256SUMS](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v6.8.1/PLUGIN-SHA256SUMS)
- [独立 Skill 6.8.1 联合包](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v6.8.1/kgxc-course-suite-v6.8.1.zip) · [SHA256SUMS](https://github.com/hebokenn/kgxc-corporate-course-skill/releases/download/v6.8.1/SHA256SUMS)

正式发布后，由发布端另存线上回读回执：主分支与标签 SHA、Release 状态和附件列表、主页版本与下载链接、公共完整下载字节及 SHA。该回执不写回当前安装包，避免校验自引用。
