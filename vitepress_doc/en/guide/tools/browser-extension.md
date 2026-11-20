---
title: Browser Extension (Yuanshen Helper)
description: Install and use Yuanshen Helper to find players, upload replays automatically, analyze results, and build custom site-wide rankings.
---

# Browser Extension (Yuanshen Helper)

Yuanshen Helper (元神助手) is a third-party browser extension for [Open Minesweeper](https://openms.top) players.

- **Player search** supports real names in Chinese, usernames, English names, pinyin, and numeric IDs.
- **Automatic replay upload** monitors a local folder and uploads new replays at regular intervals.
- **Results analysis** includes PB tables, Top-5 results, detailed player statistics (赛博大表), and local CSV analysis.
- **Custom rankings** use public replays from a range of replay IDs to rank players with your own filters and formulas.

[Project homepage](https://github.com/LockhartANR/yuanshen-helper) · [Download the latest version](https://github.com/LockhartANR/yuanshen-helper/releases/latest)

## Browser support

Use Chrome 120 or later on desktop. Edge and other Chromium browsers can generally load the extension, but have not been specifically tested.

## Install and update

1. Download `yuanshen-helper-<version>.zip` and extract it to a folder you can keep in place.
2. Open `chrome://extensions` in Chrome and turn on **Developer mode** in the upper-right corner.
3. Click **Load unpacked** and select the extracted folder.
4. Click the puzzle-piece icon on the browser toolbar and pin Yuanshen Helper (元神助手).

To update, replace the contents of the existing folder and click **Reload** on the extensions page. Refresh any open analysis pages and openms.top tabs. You can verify the download against the SHA-256 checksum on the release page.

## Get started

The extension uses Chinese interface labels.

1. **Sync the player list.** Click the extension icon, select **同步** or **立即同步**, and wait for the sync to finish.
2. **Find a player.** Enter part of a name or a numeric ID and select a result to open the player profile. You can use `↑` and `↓` to select, `Enter` to open, and `Esc` to close the popup.
3. **Analyze results.** Click the chart icon beside a search result or **我的成绩** (My Results) at the top of the popup. For local files, click **本地 CSV 分析** (Local CSV Analysis).
4. **Upload replays automatically.** Sign in to openms.top, then open **自动上传** (Automatic Upload). Click **选择目录**, select your replays folder, and grant read access. Choose **只上传新录像** for new replays only or **补传已有录像** to include existing replays, then click **开始监视**.
5. **Build a custom ranking.** Click **自定义排行榜 ↗** (Custom Rankings) on the Open Minesweeper rankings page, or open it from the extension popup. In the dataset section (**全站数据集**), enter the start and end replay IDs and click **开始加载** (Start Loading). Once loading finishes, open **筛选与指标设置** (Filters and Metrics) to configure the ranking, then click **计算排行榜** (Calculate Rankings).
6. **Manage settings.** Click the gear icon in the upper-right corner to manage syncing, toggle the on-site shortcut for detailed player statistics (赛博大表), enter your own player ID, or clear local data.

## Usage notes

- Monitoring continues if you close the upload page or minimize the browser. Click **暂停** (Pause) to stop it. Monitoring stops when you close all browser windows, quit the browser, or move or delete the replays folder. After restarting the browser, click **开始监视** again. Follow the prompts if sign-in or permissions need attention.
- Player information, analysis data, and upload history are stored locally. Automatic upload sends replays to openms.top only.
- The extension stores players’ real names locally. Use it on a personal computer and follow the site rules.
