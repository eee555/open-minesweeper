# Analyzer 更新记录 / Analyzer changelog

## 0.2.0 — 2026-10-19

- 升级 ms-toollib 至 1.5.20，包含 RMV race_identifier 解析修复，并核对离线包许可证。
- 计数器和自定义事件支持逐事件 `pluck`；每次加载录像时分析一次，采样复用结果，视频导出跳过特征分析。新增默认脉冲事件 `pluck`，表达式为 `d(pluck)`。
- 棋盘自定义事件图层默认开启并选中 `pluck`；鼠标轨迹的按键 marker 默认关闭，可分别开启。新默认值不覆盖已有保存配置。
- 时间轴与棋盘分别共用一个 Tippy：脉冲显示时间及数字/字符串原值，布尔值省略；持续事件显示完整起止时间和持续时间。复用已有采样，离开或数据失效时隐藏，移除事件轴的原生 title。
- 自定义事件的标记大小仅影响棋盘；时间轴标记固定为 8px，形状、颜色及不透明度仍跟随事件设置。

- Upgrade ms-toollib to 1.5.20, including the RMV race_identifier parsing fix, and verify the offline license notice.
- Support per-event `pluck` in counters and custom events. Analyse once per loaded replay and reuse sampled values; export parsers skip the feature pass. Add the default `pluck` pulse with expression `d(pluck)`.
- Enable the board custom-event layer with `pluck` selected and disable mouse-trace button markers by default. Individual toggles remain available; saved configurations are preserved.
- Share one Tippy per event surface: pulses show time and numeric/string values, omitting booleans; spans show full start, end and duration. Reuse prepared samples, hide stale details and remove native event-axis titles.
- Apply custom-event marker size only to the board; timeline markers stay at 8px and retain shape, color and opacity settings.

## 0.1.3 — 2026-10-18

- 修复图层开关及显示设置触发全部计数器和自定义事件重新采样造成的卡顿；保留无关配置更新时的采样缓存。
- Fix stalls when toggling layers or changing display settings by retaining counter and custom-event samples across unrelated configuration changes.

## 0.1.2 — 2026-10-13

- 离线页面的信息区和浏览器标签页采用定制 Analyzer 图标，SVG 内联到 HTML，断网打开时无需外部图标文件。网站录像页的离线包下载按钮使用同一图标。
- Use the custom Analyzer icon in the offline info area and browser tab, inlined into the HTML for offline use. The website replay page uses the same icon for the offline package download button.

## 0.1.1 — 2026-10-13

- 离线包统一命名为 `OpenMinesweeperVideoAnalyzer-版本号.zip`，网站下载链接和保存文件名同步使用独立版本。
- Name offline archives `OpenMinesweeperVideoAnalyzer-version.zip`; the website download URL and filename use the same independent version.

## 0.1.0 — 2026-10-13

- 建立 Analyzer 独立版本基线；离线信息区显示版本，ZIP 附带同源版本文件。
- 包含现有本地录像解析、棋盘/计数器/plot、视频导出、中英文切换及包内帮助与许可声明。

- Establish an independent Analyzer version; display it in the offline info area and include the same version file in the ZIP.
- Includes local replay analysis, board/counters/plots, video export, language switching, and bundled help and license notices.
