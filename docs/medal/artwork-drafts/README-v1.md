# 勋章基础模板检阅

第一阶段交付 v1，覆盖当前 17 个系列。全部模板均为待检阅，统一采用中性示意色，供检查主符号、轮廓和小尺寸辨识度。正式成绩配色、档位映射和站点接入在用户明确同意后继续。

## 查看预览

- [交互检阅页](./index.html)：点击单枚放大，可切换深色背景、灰度、隐藏名称及实际尺寸对照。可以直接在浏览器打开此文件，无需构建前端。
- [浅色总览](./overview-light.png)与[深色总览](./overview-dark.png)：每枚包含放大图和 32px 小图。
- [浅色实际尺寸](./sizes-light.png)、[深色实际尺寸](./sizes-dark.png)与[灰度实际尺寸](./sizes-grayscale.png)：每枚按 32、40、48、64、72px 排列。浏览器或图片查看器设为 100% 时检查实际像素。
- [逐枚检阅清单](./review.json)：记录系列 code、模板路径、版本、检阅状态及反馈，初始均为待检阅。

## 逐枚模板

以下全部为 v1，状态均为待检阅，尚未收到用户反馈。

- 01 [破境](./svg/breakthrough.svg)：断门与箭头。
- 02 [神速](./svg/speed.svg)：宽折角闪电。
- 03 [通明](./svg/mastery.svg)：四角光芒。
- 04 [盲扫破境](./svg/breakthrough-nf.svg)：断门与统一断旗标记。
- 05 [盲扫神速](./svg/speed-nf.svg)：闪电与统一断旗标记。
- 06 [盲扫通明](./svg/mastery-nf.svg)：光芒与统一断旗标记。
- 07 [盲扫精工](./svg/precision-nf.svg)：圆形准星与断旗标记。
- 08 [标旗精工](./svg/precision.svg)：圆形准星与完整旗帜。
- 09 [三阶盲扫精工](./svg/precision-nf-three.svg)：三个相连节点与断旗标记。
- 10 [三阶标旗精工](./svg/precision-three.svg)：三个相连节点与完整旗帜。
- 11 [实名在册](./svg/registered.svg)：身份卡。
- 12 [录像过审](./svg/reviewed.svg)：录像播放框与审核勾。
- 13 [扫雷新秀](./svg/levels.svg)：三个逐级升高的台阶。
- 14 [盲扫新秀](./svg/levels-nf.svg)：台阶与断旗标记。
- 15 [走马观花](./svg/modes.svg)：四种几何图形。
- 16 [旧迹新篇](./svg/saolei.svg)：相扣的链环。
- 17 [原始股东](./svg/shareholder.svg)：种子幼苗与根基线。

## 模板约定

SVG 使用透明背景和 64 × 64 视图框，主线宽为 5 个单位，玩法标记线宽为 4 个单位。独立源文件默认采用中性蓝灰 `#475569`；深色预览采用浅灰 `#CBD5E1`。这两种颜色只保证背景对比，不表示成绩档次。

图形使用 `currentColor`，以便后续沿用同一套轮廓着色。玩法辅助标记下的遮罩保持透明；没有白色底块、位图、渐变、金属纹理和内嵌成绩。SVG 内的标题用于可访问名称，不是烘焙在图案内的文字。

`svg/` 是独立可编辑源文件，`png/` 是对应的 160px 透明 PNG。图形定义集中在 `build_templates.py`，`render_svg.cjs` 使用 sharp 栅格化；生成器只写本目录，重新运行时保留清单中已有的检阅状态与反馈。

## 检阅方式

可以按编号反馈，例如「01 保留，04 的标记换一种，17 需要更像纪念勋章」。整体风格、单枚轮廓和小尺寸标记均可分别修改。仅将用户明确同意的模板记录为已同意，修改过的模板需对应最新版本检阅。

本批资源独立于 `front_end/src/assets/medal-templates/` 和 `front_end/public/assets/medals/`，未改变正式组件或网站展示。

## 重新生成

需要 Python 与 Pillow、Node.js 与 sharp。使用可找到这两个依赖的环境，在本目录执行：

```powershell
python build_templates.py --node node --sharp sharp
```

`--node` 可指定 Node 可执行文件的绝对路径，`--sharp` 可指定 sharp 包目录的绝对路径。生成后检查两种背景、灰度以及五档实际像素预览，再提交用户检阅。
