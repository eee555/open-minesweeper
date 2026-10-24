小游戏离线包 / Offline minigames

解压 ZIP，用 Chrome 或 Edge 打开 index.html。无需服务器或网络连接。
Extract the ZIP and open index.html in Chrome or Edge. No server or internet connection is required.

棋盘左上角显示剩余点击数或题数，右上角显示用时（秒，三位小数）。
The top-left counter shows clicks or questions left. The top-right counter shows elapsed seconds with three decimal places.
点击上方任意计数器或中间空白开始新一局；也可用 Tab 选中该区域后按 Enter 或空格。
Click anywhere in the counter bar to start a new game, or focus it with Tab and press Enter or Space.
格子大小默认 32px，在小游戏设置中统一调整，所有小游戏共用，自动保存在本地。
Cell size defaults to 32px. Adjust it in minigame settings; all games share the size, which is saved locally.
所有小游戏共用重开热键，默认未设置。点击热键输入框后按键设置，支持组合键；点击「清除」取消。设置保存在浏览器本地，输入参数时不触发重开。
The restart hotkey is shared by all games and is unset by default. Focus its field and press a key or combination to assign it; choose Clear to remove it. The setting is saved in browser storage and is inactive while editing settings.

左键训练 / Left-click training
选择初级 8×8、中级 16×16 或高级 16×30，以及 1/2、3/4 或 7/8 的雷密度。
雷默认以 50% 不透明度显示，可在小游戏设置中调整为 0%（完全透明）至 100%（不透明），设置自动保存在本地。逐个左键点击安全格，点到雷即失败；不会自动展开，也不显示相邻雷数。
可以先观察棋盘；首次有效左键弹起时开始计时，最后一个安全格完成时停止。
右键与双键不执行操作。切换模式或点击上方计数器栏会生成新棋盘。

Choose Beginner 8×8, Intermediate 16×16 or Expert 16×30, and a mine density of 1/2, 3/4 or 7/8.
Mine opacity defaults to 50%. Adjust it in minigame settings from 0% (transparent) to 100% (opaque); the setting is saved locally. Left-click every safe cell individually. Hitting a mine ends the game.
There is no flood opening or adjacent mine count. You may inspect the board before playing.
Timing starts on the first valid left-button release and stops on the final safe cell.
Right clicks and chords have no effect. Changing mode or clicking the counter bar creates a new board.

左键训练和标双训练结束后，可在棋盘下方点击播放/暂停图标或拖动进度条。拖动后保持原播放状态，播至末端停止。轨迹从开局保留至当前时间，遮罩完全透明，操作标记大小为 1/4 格。
左键训练下方依次显示鼠标移速与点击速度折线图、按下至抬起时长直方图（首次点击不计，每桶固定 0.01 秒）。移速单位为格/秒，点击速度单位为次/秒，采用最近 1 秒窗口。
悬停折线可查看数值和该时刻的棋盘，移开后恢复回放。重开或切换游戏清空当前回放预览，成功局的本地记录保留，暂不提供录像下载。

After left-click or flag-and-chord training ends, use the play/pause icon or drag the progress bar below the board. Seeking preserves the previous playback state; playback stops at the end. The trace retains all movement from the start to the current time, with a transparent mask and quarter-cell action markers.
Left-click training shows mouse and click speeds, followed by a press-to-release duration histogram excluding the first click, with fixed 0.01-second bins. Speeds use a trailing one-second window, measured in cells/s and clicks/s.
Hover the line chart to inspect values and the board at that time. Moving away restores playback. Starting another game clears the current preview while retaining locally saved successful games; recording downloads are not available yet.

标双训练 / Flag-and-chord training
初级 8×8 固定 4 题，中级 16×16 固定 15 题。所有数字均为 1，每题周围只有一颗雷。
每题占独立的 3×3 区域，位置和雷位随机。
右键插旗或取消，标好周围雷后对数字进行左右双键操作，首次弹起时触发。
旗数不匹配时双键无效果，旗数匹配但位置错误时失败。普通左键无效果。
首次有效插旗开始计时，完成最后一题时停止。

Beginner 8×8 has 4 questions; Intermediate 16×16 has 15. Every number is 1, with exactly one adjacent mine.
Each question occupies an independent 3×3 region with a randomized position and mine.
Right-click to toggle flags, then press both mouse buttons on the number. The first release triggers the chord.
A mismatched flag count does nothing; matching the count with incorrect flags loses. Single left clicks do nothing.
Timing starts on your first flag and stops when the final question is completed.

标双训练下方依次显示鼠标移速折线图、成功标双操作的堆叠条形图。每条从下到上分别表示该题最后一次插旗至左键按下、左键按下至成功双键触发的间隔。失败和无效果的双键不计。
悬停堆叠条形可查看时间明细，在折线图标记该操作，并回看成功触发时的棋盘。

Flag-and-chord training shows mouse speed followed by stacked bars for successful operations. The lower segment runs from the question's last flag to the left press; the upper segment runs from that press to the successful chord. Failed and ineffective chords are excluded.
Hover a stacked bar to inspect its timings, mark the operation on the speed chart, and review the board at its successful trigger.

漏雷训练 / Missing cell training
初级、中级、高级分别使用 10、40、99 雷。点击棋盘任意位置，在首次左键弹起时显示第一局并开始计时。
每局所有安全格均已打开，唯独漏开一格；目标与雷都盖住，可见数字足以唯一确定目标。
目标周围不会有 0，但目标本身可能为 0。左键点中目标立即显示下一局，连续完成 10 局停止计时。
点到雷则整轮失败；右键、双键及已打开格无效果。上方计数器显示剩余题数与总用时。
完成后，棋盘下方依次显示每局用时条形图和总用时堆叠条形图，均按第 1 至第 10 局从左到右排列，无图例。
悬停任一柱或堆叠段可回看该局棋盘并高亮目标，左侧计数器显示该局的剩余题数，右侧显示该局用时；移开后恢复最终棋盘和总用时。

Beginner, Intermediate and Expert use 10, 40 and 99 mines. Click anywhere on the board to reveal the first puzzle and start timing on the first left-button release.
Every safe cell except one is open. The target and the mines are covered, and the visible clues uniquely identify the target.
The target has no adjacent zero cells but may itself be zero. Click it to reveal the next board immediately; complete 10 boards to stop the timer.
Hitting a mine ends the run. Right clicks, chords and clicks on open cells do nothing. The counters show boards left and total elapsed time.
After completion, the charts below the board show per-board times and a stacked total-time breakdown, ordered from board 1 to board 10, with no legends.
Hover a bar or segment to review that board with its target highlighted. The counters show boards remaining at that point and that board's time. Move away to restore the final board and total time.

所有训练共用按下预览：按住左键时鼠标所在格显示压下；双键时鼠标周围 3×3 格显示压下。两种预览均仅排除旗格，旗格始终凸起；松开后恢复。
All games preview a held left button on the cell under the cursor, and held chords on the surrounding 3×3 region. Both previews exclude only flagged cells, which stay raised. Releasing clears the preview.

可切换训练游戏、中文/英文及浅色/深色主题。切换游戏放弃当前局。所有成功局的成绩、模式和完成时间自动保存在当前浏览器：左键及标双保留回放轨迹，漏雷保留逐局棋盘、目标和用时。失败及未完成的对局不保存，暂不提供历史查看。离线版不上传；网站登录且未封禁时，可在成功后点击“上传成绩与回放”提交至小游戏排行榜，无需实名，服务器保留个人最佳成绩对应的回放。清除浏览器站点数据会删除本地记录。
Switch games, Chinese/English and light/dark themes. Switching games discards the current round. Every successful result is saved in this browser with its mode and completion time: left-click and flag-and-chord games retain replay data, while missing cell training retains each board, target and time. Failed and unfinished games are not saved. History browsing is not available yet. The offline version uploads nothing. On the website, click "Upload score and replay" after a successful game to submit it while logged in and not banned; a real name is not required. The server retains the replay for each personal best. Clearing browser site data removes local records.

版本见页面及 version.json。版权与许可见 COPYRIGHT.txt、LICENSE、THIRD_PARTY_LICENSES.txt / .json 和 licenses/。
The version is displayed on the page and in version.json. See COPYRIGHT.txt, LICENSE, THIRD_PARTY_LICENSES.txt / .json and licenses/ for copyright and license notices.
