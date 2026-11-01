# Time 难度标记：金属刻条方案 v1

状态：未采用。用户明确不喜欢刻条方向，最新改为[左上角形状方案](../time-difficulty-corners-v1/README.md)。以下文件仅保留作历史参考。

按用户要求，仅展示 time（破境）的初级／中级／高级图案区别。直接编辑已确认的金色去外框模板，初级一道、中级两道、高级三道短金属刻条。颜色保持一致，本轮不加入成绩配色、Sub 数值、NF 副章或其他系列。

- [交互审阅页](./index.html)：三枚并排、单枚放大、浅深背景与 32／40／48／64／72px 实际尺寸。
- [浅色对照图](./overview-light.png)、[深色对照图](./overview-dark.png)。
- [逐枚清单](./review.json)、[完整提示词与生成源图记录](./generation-record.json)。
- 三枚透明 PNG：[初级](./templates/beginner.png)、[中级](./templates/intermediate.png)、[高级](./templates/expert.png)。

通过内置 imagegen 分别编辑 `front_end/src/assets/medal-templates/breakthrough.png`。要求保持上升折线箭头、碎片组合、金色切面与厚度，在箭尾下缘附近加入等宽、等厚的平行金属短条；数量分别为 1／2／3，条间保持透明空隙。

`templates/` 保存未经代码改图的生成结果，校验值记录于生成记录。`build_review.py` 只做缩放与展示排版，不更改生成原图。三枚沿用相同画布显示，不按各自包围盒重新放大，以免掩盖难度标记带来的尺寸变化。

本轮审阅重点是小尺寸下的条数辨识、刻条与箭头的整体关系，以及保留原图核心的程度。本方案已被用户否决，未替换正式基础模板或发布资源。
