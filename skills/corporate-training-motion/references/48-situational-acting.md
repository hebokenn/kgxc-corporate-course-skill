# 情境怎样演得自然：编排、人物与可复用实现

用于顾客接待、带教、管理沟通、正反案例等需要人物演出的片段。所有人物统一使用 `workbench/motion/actors_v3_cute.js`（`window.CourseActorsCute`），不调用外部生图，不使用任何静态 PNG 人物或已删除的旧版 `acting.js` / `actors_v2.js` 模型。

## 1. 先把一段戏排出来

先为每人写一句当前意图，如“走近询问”“听出顾虑”“指给对方看”“让开位置”。用起始站位、关键动作、结果站位串成完整片段。

一个典型接待节拍：

| 节拍 | 人物怎样做 | 配合对白与观看焦点 |
| --- | --- | --- |
| 进场 | 顾客调用 `computeGroundedWalk` 向店员迈步靠近（方案 B 自动转侧身面向行进方向） | 先让观众认清谁来了、找谁 |
| 停步回正 | 到达站位 `walkWeight → 0`，人物在 `0.2s` 内自动丝滑转回 3/4 正面朝向对方 | 问候接在对视建立之后 |
| 提问与倾听 | 说话者启用 `speaking: true` 与短手势（`wave`/`welcome`/`point`/`push_away`）；听者保持注视与情绪表情（`happy`/`neutral`/`tense`/`cold`） | 自己的对白驱动自己的嘴 |
| 转身离场 | 先切换 `facing` 朝向出口，再启动下一段 `computeGroundedWalk` 迈步离开 | 转身完成再起步，不倒退滑步 |

## 2. 唯一可复用实现：`CourseActorsCute`（`workbench/motion/actors_v3_cute.js`，8.0.0 强契约）

- **不滑步落地步态 `computeGroundedWalk` / `computeMoodWalk`（必须传入 `walkState`）**：
  - 调用 `computeMoodWalk(fromX, toX, sceneT, startT, mode, scale)`（`mode`: `'stroll' | 'brisk' | 'rush' | 'cold_exit'`），把返回的 `ws` 原样作为 `walkState: ws` 传给 `paint()` / `paintExpressive()`。
  - **严禁传 `walkPhase` 或 `strideAmp`**，也严禁在无 `walkState` 时平移 `x`（8.0.0 运行期直接抛错，且 `DirectorStage` 遥测会以 `floating_walk` 阻断交付）。
  - 世界坐标支撑脚绝对锁地（ZERO foot-sliding），并按 `dir` 对称分配前后脚，彻底杜绝左行 X 形交叉腿。
  - 输出非对称 4 拍重踩曲线 `bobOffset`（着地 → Down 下沉缓冲挤压 → Passing/Up 推起 → 着地）。
- **强枚举表情与手势（非法值直接抛错）**：
  - `mood`：`happy` / `neutral` / `tense` / `confused` / `cold` / `anxious` / `sad` / `shy` / `sweat` / `worried`
  - `gesture`：`idle` / `welcome` / `point` / `wave` / `push_away` / `explain` / `present` / `worry` / `reject`（所有手势避让胸前原版 KG 标）
- **方案 B 转身绘制 + 实时包围盒 `getActorBounds(st)`**：
  - 行走期间随 `walkWeight` 平滑收窄躯干至侧身、五官/眼镜/衣领转正看向行进方向、双臂自然弯曲摆动；双腿全程走软性 2-Bone IK，停步自动回正 3/4 正面。
  - `paint()` / `paintExpressive()` 直接返回 `bounds`（含 `headX / headY / headRect / bodyRect / exclusionRect`），供 `VisualMetaphors.drawSmartSpeakerBubble`、`placeAvoidingActors` 与 `DirectorStage` 碰撞审计使用，彻底消除文字压人脸。
- **扩展新人物**：
  - 在 `actors_v3_cute.js` 的 `drawCuteHead` / `paint` 中直接扩展 `hairStyle`、服装 `role` 与配饰即可；顾客固定 `showKG: false`，员工（`staff` / `manager`）绑定原版 `kg-original.png`。

## 3. 交付前连续帧核对

- 重点抽看：**起步前静止帧、迈步中段（确认无交叉腿/穿模/背景顺色）、停步回正帧、对白气泡箭头指向、柜台遮挡与脚底接地阴影**。
