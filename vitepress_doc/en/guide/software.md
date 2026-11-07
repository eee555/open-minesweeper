---
title: Minesweeper Software - Open Minesweeper
description: Supported minesweeper software and replay formats on Open Minesweeper, including EVF, RMV, AVF, MVF and replay eligibility rules.
---

# Minesweeper Software

Open Minesweeper currently supports the `EVF`, `RMV`, `AVF`, and `MVF` replay formats. `EVF` and `RMV` are general Minesweeper replay formats, `AVF` is specific to Minesweeper Arbiter, and `MVF` is specific to Minesweeper Clone.

If you want Open Minesweeper to support more Minesweeper software, you can choose to generate `EVF` or `RMV` files, or help `ms-toollib` support your custom format.

See the [MetaSweeper User Guide](./minesweeper/metasweeper.md) for installation, settings, and keyboard shortcuts.

## Replay Eligibility

For fairness, Open Minesweeper only accepts Minesweeper replays played under specific rules.

### Unsupported non-traditional features

- Left-button double click is not supported.
- Recursive chording is not supported.
- Replays must contain complete mouse paths. Touch-screen replays are not supported.

### Supported non-traditional features

- Locking the mouse inside the border. This feature was first supported by Minesweeper Arbiter and can greatly improve beginner times. MetaSweeper now also supports it. Although it affects fairness, in practice it improves the competitiveness and fun of the beginner level. Also, some other software such as [Magpie](https://github.com/Blinue/Magpie) can lock the mouse inside any rectangular region, so you can also use this behavior with other software.

## FAQ

### Why are touch-screen replays not supported?

We know there are many touch-screen Minesweeper players, but touch-screen replays make cheat detection much harder. They cannot include the movement of the hand; they only show the cursor jumping around, which can be difficult to distinguish from automated play. Mouse paths are important evidence for judging whether the operation was performed by a real person.

### Why is left-button double click not supported?

Historically, Minesweeper chording has meant pressing the left and right buttons together. Left-button double click was invented to support touch-screen Minesweeper. When used with a mouse, it is easier and more forgiving than traditional left-right chording, so it is unfair on the same leaderboard.
