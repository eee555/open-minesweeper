# 初级 time 配色审阅稿 v1

2026-10-31：用户反馈此配色不够色盲友好，已停止作为推荐默认。[新版色觉友好配色与自定义审阅](../time-color-accessible-v2/README.md)与[离线 HTML](../time-color-accessible-v2/exports/time-color-accessible-preview-offline.html)已交付，本目录保留历史记录。

2026-10-30，按用户要求，以已确认的 v3 破境去外框模板制作初级 time（`ability.time.b`）的具体成绩配色。当前全部为待检阅，不视为正式配色已获同意。

- [交互审阅页](./index.html)：全部 11 档、五种配色放大、浅深背景、灰度和 32／40／48／64／72px。
- [单文件离线 HTML](./exports/time-color-preview-offline.html)：可直接打开或复制到其他电脑，图片已内嵌，支持深色、灰度、点击放大和透明原图下载。运行 `export_review.py` 可重新导出。
- [浅色总览](./overview-light.png)、[深色总览](./overview-dark.png)。
- [逐档门槛与颜色映射](./review.json)、[完整生成提示词与源图校验记录](./generation-record.json)。

## 本轮映射提案

门槛直接核对 `back_end/saolei/medal/utils.py` 的 `TIME_SECONDS[BEGINNER]`，初级共有 11 档。SubX 表示用时严格小于 X 秒；`stage` 使用毫秒，不能把它当作档位序号。

- 青绿 `#0F766E`：[tier1](./templates/tier1.png)，Sub20、Sub15、Sub12。
- 蓝 `#2563EB`：[tier2](./templates/tier2.png)，Sub10、Sub8。
- 紫 `#7C3AED`：[tier3](./templates/tier3.png)，Sub6、Sub5。
- 橙 `#B45309`：[tier4](./templates/tier4.png)，Sub4、Sub3。
- 玫红 `#BE185D`：[tier5](./templates/tier5.png)，Sub2、Sub1。

五色来自[美术与配色计划](../../勋章美术与配色改版计划.md)。计划尚未固定具体分界，本稿提出 Sub10／Sub6／Sub4／Sub2 四个换色节点，供用户连同实际效果检阅；不按序号等分，不据此宣称跨系列、跨难度的能力等价或排名，不改变发放门槛。

初级／中级／高级由明确难度文字区分；颜色表达各难度自己的成绩档次。同一颜色不意味着相同用时。当前仅制作初级，各档在页面标注「初级」。中级、高级尚未制作或映射。

## 源图与范围

使用内置 `image_gen`，每色独立编辑已确认的 `front_end/src/assets/medal-templates/breakthrough.png`。提示词要求只改金属色相，保留上升折线、碎片组合、切面、厚度、明暗及真实透明背景。色值为主色方向，实际亮暗面随材质变化。

`templates/` 的五张透明 PNG 为生成结果的逐字节副本，不经代码抠图或换色。`build_review.py` 仅缩放、合成展示底色与排版，不覆盖源图。11 个门槛复用这五张源图，精确名称及 Sub 数值在图片外显示，避免把每个门槛烘焙成一张新底图。

本次只交付审阅稿，未替换已确认的基础模板、正式 WebP、运行时换色和发放规则。后续应以用户对色相、质感、分界及难度标记的实际反馈为准。
