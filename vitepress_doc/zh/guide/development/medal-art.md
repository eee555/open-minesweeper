# 勋章图片

勋章页面会在低带宽环境下同时展示多枚图片。后续新增系列、档位或一次性勋章时，必须使用统一生成脚本和资源预算，不能把模板原图直接放到页面。

## 文件与生成方式

源模板放在`front_end/src/assets/medal-templates/`，发布文件由`front_end/scripts/build_medal_art.py`生成到`front_end/public/assets/medals/`。

脚本先在320×320画布完成裁切，再把底图缩小为128×128。每个系列只发布一张金色底图。初级和中级不另存图片：`front_end/src/services/medalRecolor.ts`在浏览器里把偏金的像素换成铜或银，白高光和蓝青色中心保持原色。档位数字由`MedalArt.vue`用 CSS 画在底图上。页面最大展示72×72，左栏展示48×48；128px底图让高像素密度屏幕上的图案更清楚。当前模板是有金属渐变和纹理的PNG/JPG位图，没有可用的矢量原稿；不要将细节自动描摹为大量SVG路径，以免文件膨胀或纹理失真。发布格式固定为带透明通道的WebP，编码参数为`quality=50`、`alpha_quality=45`、`method=6`。底图必须经过`save_art()`。

路径约定：

- 每个系列一张：`{系列目录}.webp`。
- 不按难度、档位或金属色拆文件。

图片不烘焙系列名、难度名、档位数字和说明文字。页面用本地化文本显示完整称号。

## 资源预算

生成后的资源必须满足：

| 检查项 | 上限 |
| --- | ---: |
| 单张图片 | 8KiB |
| 全部勋章图片 | 160KiB |
| 左栏6枚底图的保守上限 | 44KiB |

生成脚本会在每张图片写入后立即检查8KiB上限，超出时指出具体文件并终止。新档位和新的金属色不增加图片。新增系列可以增加一张底图，但不能绕过单图上限，也不能恢复成每一档或每种金属色一张整图。若全库预算不足，应先优化图片或页面加载方式，并提供新的传输量测量，再调整预算。

## 前端引用

`MedalArt.vue`用`medalArtUrl()`取金色底图。初级、中级和原始股东的铜、银在组件里换色。数字用 CSS 叠在图上。底图写明`width`和`height`，使用`loading="lazy"`、`decoding="async"`。同一路径的内容或编码参数变化后，提高该 URL 的资源版本参数，避免浏览器继续使用旧文件。

## 检查步骤

从仓库根目录执行：

```powershell
.\back_end\saolei\.venv\Scripts\python.exe front_end\scripts\build_medal_art.py
.\back_end\saolei\.venv\Scripts\python.exe -m unittest discover -s front_end\scripts -p test_medal_art.py
```

自动检查覆盖WebP格式、128×128尺寸、透明通道、文件可解码和各项体积预算。提交前还要在浅色和深色背景下，以48×48和72×72检查底图轮廓、铜银换色、数字位置及透明边缘。
