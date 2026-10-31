---
title: Tournaments - Open Minesweeper
description: Points, identifiers, replay visibility rules and automatic uploading for Golden Sheep Cups and Weekly Tournaments.
---

# Minesweeper Tournaments

The website supports Golden Sheep Cups and Weekly Tournaments. Contact the developers to host other tournament formats.

## Tournament Points

Ranking points are awarded after tournament results are finalized. Converting prize money into points is not yet supported.

Personal bests are tracked separately for Golden Sheep Cups and Weekly Tournaments, counting only awarded tournaments.

### Ranking Points

Ranking points = tournament coefficient / rank. For example, 5th place in a Weekly Tournament earns 50 / 5 = 10 points.

| Tournament | Coefficient |
| --- | --- |
| Golden Sheep Cup | 1000 |
| Weekly Tournament | 50 |

### Point Decay

Current points decay over time, halving every 2 years. Historical totals are unaffected.

## Tournament Identifiers

A tournament identifier identifies your tournament replays and must be set before playing. It is revealed only when your participation window starts, even if you register early.

Replays must be uploaded within your participation window. Late uploads do not count, even if the tournament itself has not ended.

A replay can contain multiple tournament identifiers, separated by commas.

## Setting a Tournament Identifier

<details>
    <summary>MetaSweeper</summary>
    <span>Open Settings - Game Settings from the menu bar, or press S to open the settings window.</span>
    <img src="/tournament/metasweeper-token-zh.png" />
</details>
<details>
    <summary>Minesweeper Arbiter</summary>
    <span>Minesweeper Arbiter itself does not support tournament identifiers. Please follow the identifier rules set by the tournament organizer.</span>
</details>

## Tournament Replays

Tournament replays are hidden by default: they are excluded from public replay lists and leaderboards, but you can still view your own. They become public after awards, unless they also belong to another unawarded tournament. Cancelled tournaments do not prevent disclosure.

### Visibility Across Multiple Tournaments

If a replay belongs to multiple tournaments, once one is awarded, other users can see its results through that tournament's complete data export and individual participant pages, even if another tournament keeps it hidden.

Other users still cannot play or download the replay. The exception for viewing results applies only after awards, not simply when the tournament ends.

### Manual Reveal

On your profile's replay list, open a replay row's three-dot menu and choose "Reveal video".

**Revealed replays cannot be hidden again, and disclosure applies to every tournament they belong to.** They still count toward tournament results and do not use your replay quota.

## Automatically Uploading Tournament Replays {#auto-upload}

Automatic uploading requires a browser that supports folder access. During your participation window, select a replay folder, check interval and filter level to upload matching new replays. Each filter level includes all preceding conditions. Level 2 is the default.

When first selecting a folder, choose whether to upload only new replays or also process existing ones. Keep the tournament page open; automatic uploading stops when you leave it.

### Weekly Tournaments

1. All tournament videos: includes your tournament identifier. AVF is not supported.
2. Supported tournament videos: classic tournaments accept Intermediate and Expert replays in Standard mode.
3. Score-improving videos: the replay improves your total time for the best 5 Intermediate or 2 Expert games.

### Golden Sheep Cup

1. All tournament videos: AVF replays must have a nonempty player identifier that exactly matches your registered Arbiter identifier. Other software must include this tournament's identifier.
2. Supported levels and modes: Beginner, Intermediate, or Expert in Standard mode.
3. 3BV minimum met: at least 10 for Beginner, 30 for Intermediate, and 100 for Expert.

Personal replays cannot be refreshed while automatic uploading is running, and must finish loading before it can start. If you have installed the website as an app and your browser supports it, the app icon shows a badge while replays are being processed.

## Frequently Asked Questions

### Why is my uploaded replay missing from my live results?

- Only replays marked "Valid" count toward your score. Pending, frozen and identifier-mismatched replays do not count.
- Tournament identifiers must match exactly, including capitalization, spaces and invisible characters.
- In MetaSweeper, use the separate tournament identifier field. Do not append it to your regular identifier.
- Some tournaments start your participation window as soon as you register. Upload before your own window ends.
