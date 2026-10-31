---
title: Medals - Open Minesweeper
description: How to earn, view and pin medals, understand ability titles, and resolve questions about replay approval, historical awards and changing tiers.
---

# Medals

Medals record goals you have reached on this site. A title is the name attached to a medal. **Eligible medals are awarded automatically. You can then choose up to six to pin on your profile.**

## Getting Started

1. Open a player profile and select **Medals**.
2. Switch between **All medals** and **Earned medals**. Each row shows the current tier, next target and all thresholds. Browse the tier track horizontally and select a tier or **Details** to read its requirements.
3. Sign in, open your own Medals tab and choose **Manage pins**. Add medals and click **Save pins**.

All medals includes public unearned goals; Earned medals includes only current valid awards. Locked hidden medals are excluded. To get started, fill in your real name, upload your own replays and check that they pass review.

## Earning Medals

### Novice Titles

- **Registered**: your account has a real name and is no longer anonymous.
- **Reviewed**: at least one replay belonging to you has passed review.
- **First Glimpse**: you have approved replays on Beginner, Intermediate and Expert.
- **Another Path**: you have approved flagless replays on all three levels.
- **Grand Tour**: you have an approved replay in each open mode required by the medal. Modes and difficulty levels are different; covering three levels alone does not meet this requirement.
- **Old Traces**: your saolei.wang account link has been verified. See [Account Links](./account-links.md). The current requirement is verified linking; importing another replay is not required. Profile refresh and replay synchronization are disabled during the saolei.wang migration.

Novice replay requirements follow their individual rules; they do not all require Standard mode.

### Ability Titles

Ability titles track Beginner, Intermediate and Expert separately:

- **Breakthrough** uses your fastest time. Sub10 means strictly below 10 seconds; 10.000 seconds does not qualify.
- **Speed** uses your highest 3BV/s, the amount of board work completed per second. A tier of 3 requires at least 3 3BV/s.
- **Mastery** uses your highest STNB, a measure of single-game performance rather than game count or ranking.
- **Flagless Breakthrough, Flagless Speed and Flagless Mastery** use the corresponding metrics from flagless replays.
- **Flagless Precision and Flagged Precision** use the highest thrp for that play style. thrp is `3BV / effective clicks`; it differs from IOE, which uses total clicks.
- **Three-Tier Flagless Precision and Three-Tier Flagged Precision** require all three difficulty levels to meet the threshold in the same play style. Three-Tier refers to difficulty levels, not three games, three awards or a sum. For example, Three-Tier Flagless Precision · 0.9 requires flagless thrp of at least 0.9 on each level, which can come from separate replays.

These titles compare your own eligible results with fixed thresholds. One qualifying result per required metric and level is enough; you do not need five results, a leaderboard position or a better result than another player. See [Data](./minesweeper/stat.md) for more about the metrics.

For single-level ability medals, one, two and three stars indicate Beginner, Intermediate and Expert. Three stars form a triangle with one above and two below. Colors indicate score tiers within each difficulty; numbers show the exact threshold. Matching colors across difficulties do not imply equal times or leaderboard positions. Three-Level Precision is a cross-difficulty achievement and does not receive Expert stars.

Open **Customize medal colors** on a medal page, or **Medal colors** in Settings, to change the five score colors or override an individual threshold. Changes affect your view only and are saved in this browser. Reset and JSON import/export are available.

::: tip Ordinary, NF and FL
NF means flagless and FL means flagged play. The site determines the style from effective right-click actions in the replay. Ordinary Breakthrough, Speed and Mastery accept either style, so one flagless replay can qualify for both an ordinary title and its flagless counterpart.

Precision keeps the two styles separate. A replay cannot count toward both Flagless Precision and Flagged Precision.
:::

### Other Titles

**Original Shareholder** checks whether the lowest replay ID still belonging to you on this site is below a threshold. It recognizes early replay records. It does not use account registration date, game recording date or donations, and the replay does not need to have passed review.

Other titles depend on what is currently enabled and their annotations. A missing category may simply mean you have not earned any medals in it.

## Which Replays Count for Ability Titles?

An ability replay must:

1. **Belong to your account.** Uploading a file is not enough if its player identifier has not matched. See [Player Identifiers](./identifier.md).
2. **Have passed review.** Upload success does not mean approval. Pending or frozen replays do not count as valid ability results.
3. **Use Standard mode on Beginner, Intermediate or Expert.** Other modes, including no-guess modes, do not count for these titles.
4. **No longer be hidden as an ongoing tournament replay.** Such results are checked again after publication.
5. **Contain valid data for the metric.** Precision needs valid 3BV and click data; Flagless Precision excludes records with fewer effective clicks than 3BV.

These ability titles currently have no additional minimum 3BV requirement. Different replays may supply your time, speed and efficiency achievements.

Older replays can qualify once uploaded and eligible. Files stored only on your computer, results held only on another platform, and local records imported into the page from a CSV cannot directly award medals.

## Pinning, Replacing and Ordering Medals

1. Sign in and open **your own profile → Medals**. Other players' pages are view-only.
2. Open **Manage pins**, then use **Add to pins / Unpin** on each row. Tier previews do not change pins.
3. Select up to **six**. At the limit, deselect one before adding another.
4. Click **Save pins**, then check the display in your profile information area.

Use the earlier/later arrows in the pin editor to reorder medals, then save. **Cancel changes** restores the saved selection.

Your pins appear in the profile information area, usually on the left on wide screens and above the content on narrow screens. They remain visible when switching between Top, PB, Record and other tabs. Where player-name medal tooltips are available, such as in rankings, hover over a name to see their pins and then over a medal to read its explanation.

::: tip Earning and Pinning Are Separate
Select and save an earned medal to show it among your pins. Unpinning does not remove ownership. Deselecting everything and saving clears your pins, while earned medals remain visible to others in your Medals tab.

Selections are pending changes until saved. If saving fails, check your sign-in status and connection, save again and verify the display.
:::

## Upgrades and Other Changes

Each series, difficulty and play style keeps its highest currently achieved tier. If Beginner Breakthrough improves from Sub20 to Sub10, it becomes Sub10 rather than adding another Sub20 medal. An already pinned medal updates with its tier. Different levels and ordinary versus flagless titles remain separate medals.

Automatic awards depend on currently valid results and profile information. Deleting, freezing, rejecting or reassigning a replay, or changing relevant profile details or account links, triggers another check. Other eligible results may preserve the award or support a lower tier. If the requirements are no longer met, the medal can be downgraded or withdrawn and disappear from the pinned display.

Administrator decisions take precedence for manually granted or blocked medals. A manually fixed tier does not change automatically with later results; contact an administrator if automatic evaluation should be restored. Globally disabled medals are also hidden from public display.

## Common Questions

### I Uploaded a Qualifying Result. Where Is My Medal?

Check the replay's ownership, approval status, mode, level and relevant metric in your profile's Videos tab. Upload success and review approval are separate. No-guess results and still-hidden tournament replays do not qualify for ability titles.

Awards update through background tasks, so uploads, approvals and identifier changes may take time to appear. Wait and reload the page; do not upload the same replay again just to obtain a medal. If the problem persists, give an administrator your site user ID, replay ID or link, and the expected title.

### Historical Medals Are Being Awarded. What Should I Do?

The first visit schedules a check of existing profile information and historical replays. The page tries to update automatically. If the notice remains, wait and click **Reload**. This does not mean your previous results were cleared, and you do not need to upload old replays again.

### Why Is an Earned Medal Missing from My Pins or Name Tooltip?

Make sure you selected it and clicked **Save pins**. The Medals tab shows earned medals; the pinned area and name tooltips show only your chosen display. Other open pages may temporarily show older results; reload them after a short wait.

### Why Is There No Next Tier?

One-time titles have no upgrade path. Tiered titles stop showing a next tier once they reach the current maximum. The number on a medal is its achieved threshold, which may differ from your exact best result.
