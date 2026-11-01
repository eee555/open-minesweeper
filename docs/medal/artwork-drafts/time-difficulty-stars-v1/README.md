# Time 左上角星级模板稿 v1

本版已按用户要求调整：星级拆为[独立资源](../difficulty-overlays-v1/README.md)，三星为上方一颗、下方两颗的三角排列，并扩展到全部单难度系列验证。以下仅保留作旧稿。

根据用户最新要求，time（破境）的难度标记统一改为五角星数量：初级一颗、中级两颗、高级三颗，放在左上角横排。保持金色主体与材质相同，以便直接比较星数区别。

- [交互对照页](./index.html)：三枚并排、放大、浅深背景与 32／40／48／64／72px。
- [浅色对照](./overview-light.png)、[深色对照](./overview-dark.png)。
- 透明 PNG 模板稿：[初级一星](./templates/beginner.png)、[中级二星](./templates/intermediate.png)、[高级三星](./templates/expert.png)。
- [逐枚清单](./review.json)、[完整提示词及源图校验记录](./generation-record.json)。

使用内置 imagegen，以上一版 `time-difficulty-corners-v1/templates/expert.png` 的金色五角星和破境箭头为编辑目标，将左上角的大星替换为一／二／三颗较小的同款五角星。提示词要求各星保持相同大小、材质和朝向，从同一左侧位置横向排列，保留箭头、原有碎片与真实透明背景。

`templates/` 为生成结果的逐字节副本；`build_review.py` 只缩放、合成展示底色和排版文字。生成原图不经代码换色、抠图或重绘。预览以相同画布显示，不按各自包围盒单独放大。

当前为待检阅模板稿，未替换正式源模板、成绩配色稿或站点发布资源。此前三角形／菱形／五角星方案及刻条方案保留作历史记录。
