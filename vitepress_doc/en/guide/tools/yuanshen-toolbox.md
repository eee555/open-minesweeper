---
title: Yuanshen Toolbox - Open Minesweeper
description: Yuanshen Toolbox is a Windows desktop tool that reads MetaSweeper evf and Minesweeper Arbiter avf replays locally, tracks PBs, daily practice and LSF, and uploads results to Open Minesweeper manually or automatically.
---

# Yuanshen Toolbox

Yuanshen Toolbox (元神工具箱) is a Windows desktop tool that reads MetaSweeper (`.evf`) and Minesweeper Arbiter (`.avf`) replays on your own computer, tracks PBs, daily practice and LSF, and uploads results to Open Minesweeper.

The author is a player on this site (Saolei.wang #27415, Open Minesweeper #3). **This is a third-party tool with no affiliation with Open Minesweeper, MetaSweeper or Minesweeper Arbiter**: it only reads local replays, only calls this site's public interfaces, uploads nothing beyond the replays themselves, and never modifies or deletes replay files.

The interface is currently Chinese only; this page shows the Chinese labels with English meanings.

## Download

Download the latest `YuanshenToolbox.exe` (single file, about 34 MB) from [Releases](https://github.com/Corday-nkusky/yuanshen-toolbox/releases/latest). No installation — double-click to run.

The file name is fixed and carries no version number: to update, overwrite the file in place and desktop shortcuts keep working. The current version is shown in the window title.

## First launch

1. **Place it**: put the exe in MetaSweeper's `Metasweeper<version>` folder, next to `replay`. If you don't know where `replay` is, open MetaSweeper's menu 查看 → 录像目录 (View → Replay directory, shortcut `W`) and go up one level.
2. **Run it**: double-click. The program first reads the `replay` folder next to the exe; if absent, it searches every `Metasweeper*` under `%APPDATA%` and `%LOCALAPPDATA%`; only if nothing is found does it ask you to pick a folder once, which it then remembers.
3. **Wait for the first scan**: the first scan replays every game — about 3 minutes for 20,000 games, with progress and remaining time at the bottom. Later scans use the cache and finish in seconds. Scanning runs in the background; the window stays responsive.

Arbiter's replay folder is **not added automatically**; add it manually via 路径 (Paths), and make sure every replay inside is your own.

## The six tabs

| Tab | What it does |
| --- | --- |
| 概览 (Overview) | Games per level, best time / 3BV/s / Stnb; recent games compared with your PBs |
| 每日 (Daily) | One row per day: game count, session span, time / 3BV/s / Stnb distribution; right-click to copy a summary image |
| PB 表 (PB table) | The fastest game for every (level × 3BV), as one 3BV grid |
| lsf | Top 5 per level per metric, plus your personal LSF card |
| 上传 (Upload) | Pick scopes and upload local results manually |
| 自动上传 (Auto upload) | Uploads new replays automatically |

### Daily

- A game belongs to the day it **started**; games crossing midnight count toward the start day. Timestamps come from the replay header, not the file's modification time, so copying or extracting files changes nothing.
- The middle column is the **arithmetic mean**, the same convention as Arbiter's Daily Review. One level at a time, Expert by default.
- Double-click a day to list its games; double-click a game to play it in MetaSweeper.
- **Right-click a day** to copy a summary image or a detailed review image: a portrait card that displays 1:1 on a phone screen, for the current level or all levels combined, and for past dates too. The detailed card reviews the day — best game and PB badges, three metrics against your last 7 minesweeper days, a 3BV × time scatter plot with your PB curve, fastest 5 games and pace segments.

### PB table

- All three levels share one vertically scrolling 3BV grid: rows are tens bands of 3BV, columns are units, one 3BV per cell. Bands you never played keep a full empty row, so gaps are visible at a glance.
- Cell values switch between time / 3BV/s / Stnb / national rank; the color shows where that 3BV stands **nationally**. Without login it falls back to local 3BV/s terciles.
- Click a cell for details (including "held for N days · took M days to break"); double-click to play the replay in MetaSweeper.
- Search only **outlines** matching cells and never hides the others — hiding would create fake gaps in the grid.

### lsf

- Top 5 per level for time / 3BV/s / Stnb, filtered by the official 3BV thresholds by default (Beginner 10 / Intermediate 30 / Expert 100, adjustable on the page); see [top and LSF Rankings](../top-lsf.md) for the ranking rules.
- The card at the top shows your LSF, tier and equivalent et. 明细 (Details) shows which five games back each entry, plus LSF computed from only your best 1 / 5 / 25 games — the closer the three, the more consistent your play.
- After login the tables merge in the site's top rankings, with a source column marking local / site / both.
- The LSF reference follows the site's live anchors by default; you can switch to 固定基准 (fixed baseline, the built-in S6 season anchor) in 设置 (Settings).

## What counts

- **Standard mode only.** No-guess, guessable, win7, upk and custom-board replays never enter the statistics; unfinished games don't count.
- **Copies of one game count once**: duplicates are detected by identical file bytes (Arbiter's record exports and archive copies are often byte-identical to the original). No file on disk is touched.
- **Two boards**: the overall PB board takes the fastest game in any style; the NF PB board only takes [NF](../minesweeper/terminology.md) games. FL has no board of its own — it is only a style label.
- After login the PB table merges in your site PBs, keeping the faster of local and site per cell, marked local / site / tied.
- **Strict no-guess is the exception**: excluded from the statistics, but uploadable on its own (the site has separate rankings for it) — see [Auto upload](#auto-upload).

## Upload

The first time, click 登录… (Log in) on the Upload tab and enter your Open Minesweeper username, password and captcha. Keep 保持登录 90 天 (stay logged in for 90 days) checked and you won't need the password again.

- Scopes stack: PB (overall / NF), top rankings (overall / NF), all finished games. After login, local records slower than your site PBs are excluded automatically.
- **No duplicate uploads**: each candidate is compared against the replays already on the site using the site's own deduplication rule; matches are marked "already on site".
- **Identifier mismatches are blocked locally**: if the replay's identifier does not exactly match any entry registered in your account (spaces and full/half-width characters all count), it is marked as mismatched — uploading it would enter no ranking. Fix it per [Player Identifiers](../identifier.md) first.
- A confirmation dialog lists the batch's level / time / 3BV / size / file name before anything is sent.
- Single failures retry automatically; if you close the program mid-batch, reopening resumes without re-uploading successes. Only account-level problems (expired login, full quota, etc.) stop the whole batch.
- The 含阿比特录像 (include Arbiter replays) checkbox decides whether `.avf` files join the batch; checked by default.

## Auto upload

New results are noticed within a second or two of landing in the folder and uploaded if they match the enabled scopes. No popups and no focus stealing.

- Three independent switches: ranking games (games that would improve your site top rankings; requires login), overall PB, NF PB. The first two are on by default.
- Results from **before** a switch was enabled are not back-filled; games played while the computer was off are caught up on the next launch.
- Only MetaSweeper `.evf` files are uploaded. Games with mismatched identifiers or that would be frozen are skipped — they would enter no ranking and only waste quota.
- Account-level problems pause quietly; repeated network failures wait a few minutes before retrying. The last 100 records are kept on this tab.
- **Strict no-guess is configured separately**: in 设置 → 强无猜上传 (Settings → strict no-guess upload), choose off / only if it ranks / upload all. "Only if it ranks" compares against the six cells of the site's strict no-guess rankings (Beginner / Intermediate / Expert × time / 3BV/s) and uploads only when a cell would be improved or filled; NF games are compared against the NF rankings.

## Where data lives

All runtime data sits in `YuanshenToolbox-data\` next to the exe: settings, the encrypted account, the upload ledger, the scan cache and logs. Deleting this folder returns the tool to a fresh state. If the exe is in a non-writable location (such as `C:\Program Files`), data goes to `%APPDATA%\YuanshenToolbox\` instead.

The password and session cookie are stored encrypted with Windows DPAPI, bound to the current Windows user and machine — another machine cannot decrypt them. Logs contain no passwords, captchas or cookies.

## FAQ

| Situation | What to do |
| --- | --- |
| Stats look wrong | Click 重新扫描 (Rescan); if still wrong, clear the scan cache in 设置 → 诊断 (Settings → Diagnostics) and rescan |
| The site shows `d` (identifier mismatch) after upload | Make the replay identifier match your account registration per [Player Identifiers](../identifier.md), then upload again |
| An upload stopped midway | Successes are unaffected; click 重试失败 (Retry failed) to upload only the rest |
| The program crashed | The data folder's `logs\crash-<time>.txt` holds the full error; attach it when reporting |
| You want to report a problem | 设置 → 诊断 → 导出诊断包 (Settings → Diagnostics → Export diagnostics): the zip holds system info, settings and logs, never credential ciphertext |

The source is released under the MIT license; the repository [README](https://github.com/Corday-nkusky/yuanshen-toolbox) documents the full counting rules and known limitations.