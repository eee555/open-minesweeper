# 分享棋盘图块

`cells.png` 复用 [minesweeper-board](https://github.com/putianyi889/minesweeper-board) 0.7.0 的默认 SVG 素材；授权见本目录 `LICENSE`。

图集为 264×24 像素，共 11 个 24×24 图块，依次为翻开空格、数字 1–8、翻开雷格、未翻开格。数字与雷叠加在 `celldown.svg` 上；未翻开格来自 `cellup.svg`。使用 resvg 2.6.2 一次性栅格化，不修改上游形状，不在生产运行 SVG 转换器或加载字体绘制数字。

后端用 Pillow 拼接图块，输出 16 色调色板 PNG。当前尺寸固定为 24px/格；修改图块、尺寸或渲染方式时须同步递增 `SHARE_PREVIEW_VERSION`，并检查公开图片 URL、OG 尺寸及缓存命名。

本轮生成脚本和安装记录位于仓库 `.tmp/checks/share-preview-implementation-20261124/`。运行时只依赖本目录 PNG，不依赖其他工作区、Node.js 或前端 `node_modules`。
