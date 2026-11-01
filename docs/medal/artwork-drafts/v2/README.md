# 保留原图核心的勋章模板 v2

按用户反馈重做全部 17 个系列，保留原图主体、组合与金属珐琅质感，主要收减背景密网格、多重边框、细碎装饰和光效。全部为待检阅，尚未制作正式成绩配色或替换站点资源。

## 检阅入口

- [交互检阅页](./index.html)：默认原版／v2 并排，可放大查看、切换浅深背景、灰度与实际尺寸。
- [浅色总览](./overview-light.png)、[深色总览](./overview-dark.png)及[原图对照长图](./comparison.png)。
- [浅色实际尺寸](./sizes-light.png)、[深色实际尺寸](./sizes-dark.png)、[灰度实际尺寸](./sizes-grayscale.png)：按 32、40、48、64、72px 排列。
- [逐枚清单](./review.json)记录状态与反馈；[编辑提示词及原图来源](./generation-record.json)记录内置 imagegen 的生成方式与提示词。

## 模板源图

以下均为 v2 透明 PNG，状态均为待检阅。

- 01 [破境](./templates/breakthrough.png)：保留上升折线箭头。
- 02 [神速](./templates/speed.png)：保留弧形速度轨迹。
- 03 [通明](./templates/mastery.png)：保留中心方格与光芒。
- 04 [盲扫破境](./templates/breakthrough-nf.png)：折线箭头与禁旗圆形副章。
- 05 [盲扫神速](./templates/speed-nf.png)：速度轨迹与禁旗圆形副章。
- 06 [盲扫通明](./templates/mastery-nf.png)：方格光芒与禁旗圆形副章。
- 07 [盲扫精工](./templates/precision-nf.png)：方格、内聚箭头、目标圆环与禁旗副章。
- 08 [标旗精工](./templates/precision.png)：方格、内聚箭头与目标圆环。
- 09 [三阶盲扫精工](./templates/precision-nf-three.png)：三枚方格圆章与禁旗副章。
- 10 [三阶标旗精工](./templates/precision-three.png)：三枚方格圆章的三角组合。
- 11 [实名在册](./templates/registered.png)：竖向折角证件与认证勾章。
- 12 [录像过审](./templates/reviewed.png)：胶片齿孔、播放按钮与审核勾章。
- 13 [扫雷新秀](./templates/levels.png)：三层雷盘与三面红旗。
- 14 [盲扫新秀](./templates/levels-nf.png)：三层无旗雷盘。
- 15 [走马观花](./templates/modes.png)：环绕的六面雷盘与蓝色格子。
- 16 [旧迹新篇](./templates/saolei.png)：旧雷盘窗口、迁移箭头与站点徽标。
- 17 [原始股东](./templates/shareholder.png)：历史档案盒、记录卡与站点徽标。

## 来源与复现

图像通过内置 imagegen 逐枚编辑 `front_end/src/assets/medal-templates/` 下的原图，部分同族模板使用本轮主系列稿作为风格参照。提示词里的风格参照是制作参考，不表示用户已同意。原版对照图是现有发布 WebP 的未修改副本。

`templates/` 保存生成工具原始透明 PNG，未通过代码修改图案。这些是高分辨率审稿源图，发布编码、资源预算和色档映射待模板同意后处理。`build_review.py` 只排版、缩略显示与导出检阅长图，不生成或修改主体。

重新排版需 Python 与 Pillow，执行 `python build_review.py`。继续修改图案应使用编辑提示词及对应原图，通过图像编辑流程完成。
