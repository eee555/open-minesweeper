# 去外框全套模板检阅

全套 17 个系列已按用户确认的去外框方向完成。2026-10-30 用户同意全套，并要求保存为模板、替代之前的模板。17 枚透明 PNG 已原样保存到 [正式源模板目录](../../../../front_end/src/assets/medal-templates/README.md)。主体沿用原图，移除统一的大圆框、四方装饰尖角及圆形背景底板，保留金属切面、厚度与必要的蓝色部分。

- [交互检阅页](./index.html)：17 枚总览、有框／去框并排、单枚放大、浅深背景、灰度以及 32、40、48、64、72px 对照。
- [浅色总览](./overview-light.png)与[深色总览](./overview-dark.png)。
- [浅色对照长图](./comparison-light.png)与[深色对照长图](./comparison-dark.png)。
- [浅色实际尺寸](./sizes-light.png)、[深色实际尺寸](./sizes-dark.png)与[灰度实际尺寸](./sizes-grayscale.png)。
- [逐枚清单](./review.json)与[内置 imagegen 编辑提示词记录](./generation-record.json)。

## 17 枚模板源图

- 01 [破境](./templates/breakthrough.png)：保留立体折线上升箭头及少量碎片，透明空隙随折线形成。
- 02 [神速](./templates/speed.png)：保留弧形速度轨迹与尾迹，去掉共同圆形底板，轨迹间保持透明。
- 03 [通明](./templates/mastery.png)：保留中心方形亮格与八向放射光芒。
- 04 [盲扫破境](./templates/breakthrough-nf.png)：折线上升箭头与简化金边的禁旗副章。
- 05 [盲扫神速](./templates/speed-nf.png)：弧形速度轨迹与禁旗副章。
- 06 [盲扫通明](./templates/mastery-nf.png)：中心方格、八向光芒与禁旗副章。
- 07 [盲扫精工](./templates/precision-nf.png)：中心方格、四向内聚箭头、分段目标环与禁旗副章。
- 08 [标旗精工](./templates/precision.png)：中心方格、四向内聚箭头与分段目标环，空隙透明。
- 09 [三阶盲扫精工](./templates/precision-nf-three.png)：三枚内部圆章的三角组合，保留禁旗副章。
- 10 [三阶标旗精工](./templates/precision-three.png)：保留内部三枚方格光芒圆章，移除最外围大圆章与共同背景。
- 11 [实名在册](./templates/registered.png)：折角证件、头像与简化边框的认证勾章。
- 12 [录像过审](./templates/reviewed.png)：胶片齿孔、播放三角与审核勾章。
- 13 [扫雷新秀](./templates/levels.png)：三层透视雷盘与三面红旗，层间透明。
- 14 [盲扫新秀](./templates/levels-nf.png)：三层无旗雷盘，层间透明。
- 15 [走马观花](./templates/modes.png)：环绕的六面雷盘、蓝色格子与中心光点。
- 16 [旧迹新篇](./templates/saolei.png)：旧雷盘窗口、迁移箭头与蓝色站点徽标。
- 17 [原始股东](./templates/shareholder.png)：保留档案盒、记录卡、站点标志与主体蓝色侧面，轮廓随盒体与卡片形成。

全部通过内置 imagegen 逐枚编辑 v2 透明 PNG，同族盲扫变体另参考去外框主系列稿。`templates/` 为未经代码改图的生成原图；先行四枚保留原文件，新增模板不覆盖它们。`build_review.py` 只制作显示缩略图和对照排版。原有 v2、原始勋章及正式组件均保留。

本轮已完成基础源模板替换；旧源模板（含替换前本地修改）备份在 [original-templates](../original-templates/)，并附 SHA256 清单。生成器改为直接保留透明通道，不再按颜色抠背景。尚未开始成绩档次配色、正式发布图更新或站点接入。全套同意状态记录于 `review.json`。原四枚样例的页面、清单与对照图另以 `four-samples` 后缀保留，历史快照以当时状态为准。
