# 更新记录 / Changelog

## 0.6.5 — 2026-10-25

- 左键和多指训练可设置雷格按下或弹起，默认弹起；共用本地设置，切换保留当前局，回放按当前设置显示。
- Left-click and multi-touch training share a local setting for pressed or raised mine cells, defaulting to raised. Changing it keeps the current game; replays use the current display setting.

## 0.6.4 — 2026-10-25

- 多指训练的成功局自动保存本地历史，保留压缩回放，并支持按完成时间和成绩索引读取。
- Successful multi-touch games now save local history with compressed replays, indexed by completion time and score.
- 多指训练高级方向保存为本地显示设置，切换时保留当前局及回放；纵向通过交换横纵坐标显示，回放统一使用横向坐标。
- Expert orientation in multi-touch training is saved as a local display setting. Switching preserves the current game and replay; vertical display swaps the axes while recordings retain horizontal coordinates.
- 灵感来源补充扫雷联萌（League of Minesweeper）。
- Added League of Minesweeper to the inspiration credits.

## 0.6.3 — 2026-10-25

- 多指训练全屏时移除棋盘内外边框及周围留白。
- Fullscreen multi-touch training removes the inner and outer board frames and surrounding spacing.
- 多指训练全屏时计数器只作显示，通过顶栏重开按钮开始新一局，避免误触。
- Fullscreen counters are display-only; a restart button in the toolbar starts a new game to prevent accidental resets.
- 格子大小改为直接输入正整数，所有小游戏共用并保存；多指训练全屏顶栏也可调整，取消自动缩放，调整尺寸时保留当前局。
- Cell size accepts a positive integer shared and saved across all games. Multi-touch fullscreen also offers it in the toolbar, with automatic resizing removed; changing the size keeps the current game.

## 0.6.2 — 2026-10-25

- 多指训练取消按下预览，触摸和平移时仅显示实际棋盘状态。
- Removed pressed-cell previews from multi-touch training; touching and panning display only the actual board state.

## 0.6.1 — 2026-10-25

- 多指训练支持单指滚动，多指按住时停止滚动；高级增加横向和纵向选项。新增全屏自适应棋盘，高级沿短边填满并允许沿长边滚动。
- Multi-touch training supports one-finger scrolling, suspended while multiple fingers are held, and horizontal/vertical Expert layouts. Fullscreen fits the board automatically; Expert fills its short axis and scrolls along the long axis.

## 0.6.0 — 2026-10-25

- 新增多指训练，仅接受触屏，按下开格并开始计时，支持多个独立触点；沿用左键训练的棋盘参数、胜负规则和雷不透明度设置。左键训练改为仅接受鼠标。
- 多指训练支持播放、暂停、拖动回放，独立显示各触点轨迹；测试期间仅保留本局回放，不保存本地历史。
- Added touchscreen-only multi-touch training: touch down opens a cell and starts timing, with independent concurrent contacts. It shares left-click board settings, win/loss rules and mine opacity. Left-click training now accepts mouse input only.
- Multi-touch games support replay playback, pausing and seeking with separate contact paths. During testing, replays remain in the current session without saving local history.

## 0.5.1 — 2026-10-24

- 修复旧录像格式转换失败时阻塞新成绩保存的问题：将原 JSON 整体压缩保留，继续升级其他记录；无法解析的回放仍报告损坏。
- Fixed old replay conversion failures blocking new results: preserve the complete original JSON in 7z and continue upgrading other records. Unreadable replays still report parsing errors.

## 0.5.0 — 2026-10-24

- 历史录像格式升级时显示优化提示和进度，禁止通过 Escape 或遮罩关闭，完成或失败后自动关闭。
- Historical replay upgrades now show an optimization notice and progress. Escape and backdrop dismissal are disabled; the notice closes automatically on completion or failure.
- 所有小游戏自动在 IndexedDB 保存成功成绩，按完成时间和用时建立索引。回放使用 v1 紧凑格式并压缩为 7z 二进制，旧本地记录自动升级；左键与标双保存压缩棋盘和差分鼠标事件，读取时重建快照和统计；漏雷保留 10 局雷位、目标坐标和用时。暂不提供历史可视化。
- All minigames now save successful results in IndexedDB, indexed by completion time and score. Replays use the compact v1 format stored as 7z binary, with automatic upgrades for older local records. Left-click and flag-and-chord games store compressed boards and delta-encoded mouse events, rebuilding snapshots and statistics for playback. Missing cell training stores its 10 mine layouts, target coordinates and times. History visualization is not available yet.
- 标双训练固定为初级 8×8、4 题及中级 16×16、15 题，全部使用数字 1；移除高级、题数及数字比例配置。
- Flag-and-chord training now uses 4 questions on Beginner 8×8 and 15 on Intermediate 16×16, all with the number 1. Removed Expert, custom question counts and number ratios.

## 0.4.0 — 2026-10-23

- 左键训练和标双训练新增本局回放，支持播放／暂停和拖动定位；使用全长鼠标轨迹、透明遮罩及四分之一格大小的操作标记。
- 左键训练新增鼠标移速／点击速度折线图，以及固定 0.01 秒桶宽的点击时长直方图。
- 标双训练新增鼠标移速折线图及成功标双操作的分段用时图；悬停图表可定位棋盘与鼠标，移开恢复播放状态。
- 设置页新增小游戏分区，所有游戏共用格子大小及重开热键；左键训练支持调整雷的不透明度，默认 50%。单键按下预览仅排除旗格。
- 简化训练界面，移除重复标题、独立重开按钮、统计及结果提示文本；版权说明补充灵感来源。

- Added replay for left-click and flag-and-chord training, with play/pause, seeking, a full mouse trace, a transparent mask and quarter-cell event markers.
- Added mouse/click speed lines and a click-duration histogram with fixed 0.01-second bins to left-click training.
- Added a mouse speed line and timing breakdowns for successful flag-and-chord operations. Hovering charts previews the board and cursor; leaving restores playback.
- Added a Minigames section to Settings with shared cell size and restart hotkey preferences. Left-click mine opacity is adjustable, defaulting to 50%. Single-button press previews exclude flagged cells only.
- Simplified training pages by removing repeated titles, separate restart buttons, statistics and result messages; credited the sources of inspiration.

## 0.3.0 — 2026-10-23

- 页面整体水平居中，大棋盘可横向滚动。
- 新增所有小游戏共用的重开热键，支持单键及组合键，默认未设置，保存在 localStorage；输入参数时不触发，长按不重复重开。
- 漏雷训练完成后，在棋盘下方按局次显示用时条形图与总用时堆叠条形图。两图均无标题和图例；条形图不显示纵轴，横轴仅保留基线，堆叠条不显示 tooltip。
- 悬停任一柱或堆叠段可回看该局棋盘并高亮目标，计数器同步显示该局剩余题数和耗时；移开恢复最终棋盘和总成绩，重开清空结果。

- Centered the page layout with horizontal scrolling for wide boards.
- Added a restart hotkey shared by all games, supporting single keys and combinations. It is unset by default and saved in localStorage. It is inactive while editing controls; holding it restarts only once.
- Missing cell results show per-board times and a stacked total-time breakdown below the board. Both charts omit titles and legends; the bar chart has no vertical axis and only a horizontal baseline, and the stack has no tooltip.
- Hover a bar or segment to review its board with the target highlighted and its remaining count and time in the counters. Moving away restores the final board and total time; restarting clears the results.

## 0.2.0 — 2026-10-23

- 新增标双训练：独立随机题目，支持自定义题数和数字 1／2 的固定比例。
- 新增漏雷训练：连续完成 10 局计总用时，保证目标唯一可判断，排除邻接 0 的目标，允许目标本身为 0。
- 统一 Example 风格的棋盘及数码计数器布局；点击计数器区域重开。级别使用互斥按钮，格子默认 32px。
- 在线与离线版共用三种训练、经典操作自动机和双键预览；旗格保持凸起。

- Added flag-and-chord training with independent random questions, adjustable question counts and a fixed ratio of 1s to 2s.
- Added missing cell training with one timer across 10 boards. Targets are uniquely identifiable and cannot border a zero, but may themselves be zero.
- Unified the board and digital counter layout with the Example style. Click the counter bar to restart. Levels use radio buttons and cells default to 32px.
- Online and offline builds share all three games, the classic mouse state machine and chord previews. Flagged cells stay raised.
