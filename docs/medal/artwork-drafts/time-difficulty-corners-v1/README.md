# Time 左上角难度标记 v1

本版已按用户最新要求调整为[左上角一／二／三颗五角星](../time-difficulty-stars-v1/README.md)，此目录保留作历史参考。

按用户确认的方向，在 time（破境）已确认的原金色去外框模板左上角加入独立金属切面：初级三角形、中级菱形、高级五角星。主体、颜色与构图沿用原模板，仅展示三种难度的图案区别。

- [交互对照页](./index.html)：三枚并排、放大、浅深背景、32／40／48／64／72px。
- [浅色对照](./overview-light.png)、[深色对照](./overview-dark.png)。
- 透明 PNG 模板稿：[初级](./templates/beginner.png)、[中级](./templates/intermediate.png)、[高级](./templates/expert.png)。
- [逐枚清单](./review.json)、[完整生成提示词与源图校验](./generation-record.json)。

三枚均通过内置 imagegen 直接编辑 `front_end/src/assets/medal-templates/breakthrough.png`。要求保留上升折线箭头、原有碎片、金属切面和厚度，新增标记位于左上角透明留白，保持相近占位与材质。五角星采用饱满粗壮的五个尖角，以便缩小时识别。

`templates/` 为 imagegen 生成结果的逐字节副本。排版脚本 `build_review.py` 仅进行展示缩放、底色合成与文字排版，不抠图、不重绘、不覆盖生成源图。三枚使用相同画布大小显示，不分别按包围盒缩放。

本轮为模板审阅稿，待用户检阅具体效果。未替换正式基础模板、配色稿或站点发布资源。
