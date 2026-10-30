---
title: 录像播放器 - 开源扫雷网
description: 开源扫雷网的原生录像播放器，支持自定义计数器和丰富的扫雷数据字段。
---

# 录像播放器

开源扫雷网使用原生播放器播放录像，自动处理站内录像的压缩格式。下载按钮保存原始录像文件。

## 原生播放器
原生播放器是网站自带的录像播放器，棋盘由 [`@putianyi888/vue3-minesweeper-board`](https://www.npmjs.com/package/@putianyi888/vue3-minesweeper-board) 渲染，录像由 [`ms-toollib`](https://www.npmjs.com/package/ms-toollib) 解析。除了基本的录像播放功能，还支持使用 `expr-eval` 语法的自定义计数器。

字段、运算符、条件与逻辑运算、内置函数，以及与录像分析页计数器和自定义事件的差异，详见[录像表达式参考](./replay-expressions)。

