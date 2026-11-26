# 分享棋盘图块

`WinmineXP.png` 直接使用用户指定的 [MS-Texture 原始素材](https://github.com/Minesweeper-World/MS-Texture/blob/main/png/cells/WinmineXP.png)，保留原始文件字节，不经过 SVG 栅格化、缩放或重绘。来源目录的说明见 [MS-Texture](https://github.com/Minesweeper-World/MS-Texture)，原始声明保存在本目录 `LICENSE`。

原图为 64×64 像素，4×4 布局，每格 16×16。以左上角为 `(列, 行) = (0, 0)`：数字 1–4 在第 0 行，5–8 在第 1 行；翻开空格为 `(0, 2)`、未翻开格为 `(1, 2)`、普通雷格为 `(2, 3)`。其余状态不用于完成棋盘。

后端用 Pillow 按原始尺寸取图块、拼接并输出 16 色调色板 PNG。该素材不含 SVG 栅格化产生的抗锯齿过渡色，数字 5 保持 `#800000`。当前为 v2、16px/格；修改图块、尺寸或渲染方式时须同步递增 `SHARE_PREVIEW_VERSION`，并检查公开图片 URL、OG 尺寸及缓存命名。部署时重新运行 `python manage.py prepare_share_preview` 准备 v2 共用占位图。

原文件 SHA-256：`094ba05a994f7b6bb51662616ae022ed163f775904ffd80f423f135a2ea9e6f7`。下载副本、颜色验证及样图位于 `.tmp/checks/share-preview-colors-20261125/`。运行时只依赖本目录 PNG，不依赖网络、其他工作区、Node.js 或前端 `node_modules`。
