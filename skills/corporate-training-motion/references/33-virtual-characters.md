# 创建、修改与使用虚拟角色

需要全身行走、转身和情境交流时，先读[情境怎样演得自然](48-situational-acting.md)。所有人物统一调用随包唯一人物引擎 `workbench/motion/actors_v3_cute.js`（`window.CourseActorsCute`）：**3.3 头身简洁可爱风、不滑步世界坐标落地步态、方案 B 行走转侧身与停步回正、防弹膝 2-Bone IK 与防背景混色外轮廓**。

> **已彻底清理并禁用旧人物模型**：旧版整张静态 PNG 人物（`C01..C03` / `M1-repaired` / `blue-cast` / `MyCoach` / `role-surfaces-v1` / `retail-v1` 静态人物）以及旧版 `acting.js` / `actors_v2.js` / `V01..V03` 细长站桩模型已全部从 Skill 移除，严禁重新引入、参考或回退。

## 当前默认：同一套 3.3 头身可爱可动人物（可扩展）

1. **现有起点角色（4 套配置，非固定上限）**：
   - 店员：`role: 'staff'`，`hairStyle: 'bun_pony'`，蓝衣配原版 `kg-original.png` 胸标。
   - 店长：`role: 'manager'`，`hairStyle: 'manager_short'`，黑衣配原版 `kg-original.png` 胸标。
   - 便装男顾客起点：`role: 'cust_jacket'`，`hairStyle: 'casual_short'`，圆框眼镜、灰蓝外套 + 浅雾蓝 `#D5E1EE` 内搭，无 KG 标。
   - 便装女顾客起点：`role: 'cust_knit'`，`hairStyle: 'fluffy_bob'`，耳环、橘棕针织衫，无 KG 标。
2. **新课按情境自由扩充顾客与员工**：
   - 已有顾客只是起点，不是每课固定班底。可用 `workbench/layered_customers.py` 的 `design_for_course(course_id, identity, appearance)` 生成起点，或在 `actors_v3_cute.js` 内直接新增发型、便装款式（如卫衣、衬衫、长裙等）与配饰。
   - **同场不同人必须在外貌上有清楚区分**（至少在发型或服装款式/配色上有明显差异，不能只换名字共用同一外貌）。
   - **同课同一人物跨镜头保持连续**，顾客一律穿便装、不带员工胸标。
   - **服装防混色铁律**：任何内搭、外衣或裤鞋颜色都不得与当前画布背景色接近或顺色（如暖白墙面下禁止使用 `#FFFBF5` 等纯白/浅米白做无明确对比色块的内搭），必须保持清晰外轮廓描边（`#3A3438`）与 `ctx.clip()` 内廓裁剪。

## 行动、朝向与交付自检

- **行走与朝向（方案 B）**：`CourseActorsCute.computeGroundedWalk` 负责生成世界坐标不滑步落脚点与非对称 4 拍重踩节奏；`CourseActorsCute.paint` 随 `walkWeight` 自动将躯干、五官与衣领转向行进方向，停步自动丝滑回正 3/4 说话态。
- **同场对话与遮挡**：说话人开口前完成朝向，受话人在场倾听；柜台遮挡严格按远景员工 → 柜台 → 近景角色分层。
- **渲染验证**：修改发型、服装或动作后，必须使用真实无头浏览器渲染静止、迈步、停步及手势关键帧并目视核对。
