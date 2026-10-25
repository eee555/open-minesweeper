---
title: Minigames - Open Minesweeper
description: Rules, timing, replays, rankings and offline play for left-click, multi-touch, flag-and-chord and missing cell training.
---

# Minigames

[Play minigames](https://openms.top/#/minigame) · [View rankings](https://openms.top/#/ranking/minigame)

These games practise clicking, flagging, chording and observation. Each uses its own rules and timing:

| Training | Goal | Timer starts |
| --- | --- | --- |
| Left-click | Click every safe cell individually | On the first valid left-button release |
| Multi-touch | Touch every safe cell | On the first touch down |
| Flag-and-chord | Flag and chord every question | On the first successful flag placement |
| Missing cell | Find the missing safe cell on 10 consecutive boards | On the first left-button release, revealing board 1 |

## Left-click Training

Choose Beginner **8×8**, Intermediate **16×16** or Expert **16×30**, each with a mine density of **1/2, 3/4 or 7/8**, for 9 modes in total.

Mouse only. Mines are visible, so you may inspect the board before starting. Each left-button release opens only the selected safe cell, with **no flood opening**. Hitting a mine loses; opening every safe cell stops the timer. Right clicks and chords have no effect.

Mine cells default to raised, with 50% mine opacity. Both can be adjusted in minigame settings.

## Multi-touch Training

Uses the same sizes, mine densities and win/loss rules as left-click training, but **accepts touchscreen input only**. You may inspect the board first. The first touch down starts timing; each finger opens its current cell on touch down. Moving or lifting a finger opens nothing. There is no pressed-cell preview. Contacts act independently, and playing with one finger is allowed.

Mine opacity and the pressed or raised mine-cell setting are shared with left-click training.

Drag with one finger to scroll the board and page, without stopping at the board edges. Scrolling stops while two or more contacts are held. Expert offers horizontal **16 rows × 30 columns** or vertical **30 rows × 16 columns**. Orientation is saved locally; changing it keeps the current game and replay.

Fullscreen removes the board frames and surrounding spacing. Enter the cell size in its toolbar; it is shared with minigame settings and saved, without automatic resizing. Scroll horizontally and vertically when needed. Fullscreen counters are display-only; use the toolbar restart button for a new game. Changing size or exiting fullscreen keeps the current game and cell size; exiting restores the counter-bar restart action.

## Flag-and-chord Training

Beginner has **4 questions on 8×8**; Intermediate has **15 on 16×16**. Every number is **1**, with one visible adjacent mine. Each question occupies its own non-overlapping 3×3 region.

Right-click to flag the mine, then use a [classic chord](./minesweeper/mouse-event) on the number: hold both mouse buttons and **release either one to trigger**. Opening its safe neighbours completes the question. The timer stops when the last question is complete.

Right-click again to remove an incorrect flag. A mismatched flag count makes a chord do nothing; a matching count with the flag in the wrong place loses. Single left clicks do not open cells.

## Missing Cell Training

Beginner uses **8×8 with 10 mines**, Intermediate **16×16 with 40**, and Expert **16×30 with 99**. The first click only starts the run: its left-button release reveals board 1 and starts timing.

Every safe cell except one is already open. The target and the mines are covered, and the visible numbers uniquely identify the target. It has no adjacent open zero cell, but may itself be zero.

Click the target to reveal the next board immediately. Complete **10 consecutive boards** to stop the timer; hitting a mine loses the whole run. Right clicks, chords and clicks on open cells have no effect.

## Restarting and Settings

The top-left counter shows clicks or questions remaining; the top-right counter shows seconds with three decimal places. Outside fullscreen, **click anywhere in the counter bar to restart**, or focus it with Tab and press Enter or Space.

Shared cell size and restart hotkey settings are available below the games and in the website's Minigames settings section. Cell size defaults to 32px and accepts a positive integer; the hotkey is unset. Left-click and multi-touch training share mine opacity and pressed or raised mine-cell settings. Preferences are saved in this browser; the mine-cell state is excluded from recordings. Changing these display settings keeps the current game, and replays use the current display settings. Changing level or game parameters starts a new game.

## Replays and Analysis

After left-click or flag-and-chord training ends, the replay below the board shows the mouse trace. Play, pause or drag the progress bar; playback stops at the end.

Multi-touch replays use the same playback controls, showing a separate path for each contact and markers for fingers currently held down. Different contacts are never connected into a single path.

- **Left-click:** mouse and click speeds use a trailing one-second window, measured in cells/s and clicks/s. The histogram below shows left-button press-to-release intervals, excluding the first click, in fixed 0.01-second bins.
- **Flag-and-chord:** the charts show mouse speed over a trailing one-second window and timing breakdowns for successful questions. Each bar's lower segment runs from that question's last flag placement to the left-button press; the upper segment runs from that press to the successful chord. Failed and ineffective chords are excluded.

Hover the speed chart to inspect values and the board at that time. Hover a flag-and-chord timing bar to locate that successful operation and mark it on the speed chart. Moving away restores the previous replay state.

After a successful 10-board missing cell run, the charts show each board's time and a stacked total-time breakdown. Hover a bar or segment to review that board with its target highlighted. The left counter shows boards remaining at that point; the right shows that board's time. Moving away restores the final view.

## Rankings and Local Results

After a successful game, click **Upload score and replay** below the board to submit it while logged in and not banned. **No real name, Minesweeper profile or linked account is required.** Each mode keeps your personal best time and its replay. Click a score column to sort the rankings, or hover a score to see when it was achieved. **Click a score to watch its replay**, without logging in. Online replays use the same interface and local display settings as your own completed games, initially paused at the end. Restart or change game parameters to start a new game. Links at the top connect each game with its rankings.

Successful left-click, multi-touch and flag-and-chord games retain replays in this browser; missing cell training retains each board, target and time. Failed and unfinished games are not saved. History browsing and replay downloads are not available yet. Restarting clears the current preview while keeping saved successful games; clearing browser site data deletes local records.

## Offline Play

Choose **Download offline** on a game page, extract the ZIP, and open `index.html` in Chrome or Edge to play without a connection. The offline version supports settings, replays and local results, but **uploads neither scores nor replays**.
