---
title: Video Player - Open Minesweeper
description: "The native replay player on Open Minesweeper, with custom counters and replay statistics."
---

# Video Player

Open Minesweeper uses its native player, which automatically handles compressed website replays. Download buttons save the original replay file.

## Native Player

The native player is built into the website. Its board is rendered by [`@putianyi888/vue3-minesweeper-board`](https://www.npmjs.com/package/@putianyi888/vue3-minesweeper-board), and replays are parsed by [`ms-toollib`](https://www.npmjs.com/package/ms-toollib). Besides playback, it supports custom counters using `expr-eval` syntax.

See [Replay Expressions](./replay-expressions) for fields, operators, conditional and logical expressions, built-in functions, and differences from analyzer counters and custom events.
