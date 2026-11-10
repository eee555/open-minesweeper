---
title: Works - Open Minesweeper
description: Submission, review, rubies and heat rules for promoting Bilibili videos, articles and Saolei.wang posts on Open Minesweeper.
---

# Works

[Open the Works page](https://openms.top/#/works)

Works lists the minesweeper content collected on this site: Bilibili videos, Bilibili articles and Saolei.wang posts. **Only approved works appear here.** The table is sorted by **Current heat** by default; click a column heading to switch between **Published at**, **Current heat** and **Total likes**. Changing the sort returns to page one, with 20 works per page. Clicking a Bilibili video title opens an in-site preview; other titles open the original link. The icon before each title shows the source platform.

If you create content and want to promote it here, these are the rules most likely to catch you out:

- You must [link and verify](./account-links.md) your account on the source platform before submitting.
- A link can only be submitted once, even if the submission was rejected.
- There is no delete button: you cannot take down an approved work yourself.
- Pending and rejected works are hidden from Works, but visible to everyone on your profile and in the database pages.

## Submitting a work

Click **Submit** at the top right of the Works page, choose the platform and type, enter the **Work ID**, and optionally fill in the language. You can paste a full link or just the ID: a BV id for Bilibili videos, a numeric id for Bilibili articles and Saolei.wang posts (leading zeros do not matter, so `cv01646742` and `cv1646742` are the same article). The title and publish time are fetched from the source site; you do not fill them in.

::: tip When the source site is temporarily unavailable
The submission is kept and shown as **Title to be filled**. A moderator fills in the title and verifies the external account during review. An invalid link, a wrong type or a malformed ID is rejected outright and leaves no record.
:::

### Link your account first

The site checks that the author of the source work matches one of your **verified** account links. You cannot submit without a link, while a link is awaiting verification, or when the author does not match. External author IDs are used only to verify ownership; they are not stored on this site or shown on the Works page.

Bilibili videos and articles need a verified Bilibili link; Saolei.wang posts need a verified Saolei.wang link. See [Account Links](./account-links.md) for how to link an account. **Creator-platform links are public**: once you promote a work, that external account is publicly connected to your identity on this site. If you do not plan to promote works, there is no need to link one, and we do not recommend it.

::: warning One link, one submission
The same external URL cannot be submitted twice, **even if the earlier submission was rejected**. Only a moderator permanently deleting the record frees the link. Check the link and type before submitting.
:::

## Review and where works appear

| Place | What you see |
| --- | --- |
| Works | Approved works only |
| **Works** on a profile and in the database pages | Every status, including Pending review and Rejected; rejected works also show the reason and the moderator who rejected them, to all visitors |
| **Works** on the rankings page | Approved works only, totalled per author; it is not a per-work ranking |

Works has no **Pending review** section. After submitting, check the **Works** tab on your own profile. A pending work does not enter the Works page or the rankings; when it is approved, any likes it already received are counted at once.

::: warning You cannot delete your own work
Before approval, the only way to withdraw a work is to ask a moderator to reject it. Once approved, a work is final: its title and other details cannot be changed either. Only a moderator can permanently delete an approved work, which is also the only case where the link becomes reusable.
:::

## Feeding and heat

Once logged in, click **Feed** in the **Total likes** column to spend one ruby. Rubies accumulate with the age of your account: one for every full 24 hours since registration, whether or not you log in, and unused rubies never expire. Hover over the button to see your balance.

- **Current heat**: each feed adds about 1, then keeps 99% per day. Decay is continuous, so older works slide down naturally.
- **Total likes**: the number of feeds, which never decays. It is reset to zero if the work is rejected.

Each account can make at most 10 successful feeds per day, counted in UTC days (so the limit resets at 00:00 UTC, not at your local midnight); failed feeds do not count. Feeding your own work is allowed.

::: warning Rejection refunds rubies, not your daily allowance
When a work is rejected, the rubies spent on it are refunded, but the feeds already used that day are not returned.
:::

## Frequently Asked Questions

### Why can't I find my work after submitting?
A work appears on the Works page only after a moderator approves it. Check the **Works** tab on your profile; a **Rejected** work shows its rejection reason there.

### Why do I see "this work has already been submitted"?
That external URL already has a submission record, including rejected ones. It cannot be resubmitted, and rewriting the link format is not a workaround.

### Why is the title "Title to be filled"?
The title could not be fetched from the source site when you submitted. A moderator fills it in during review and also verifies ownership of the external account.

### Why didn't the ranking change after I fed a work?
**Current heat** decays by 1% per day and works were fed at different times; sorting by **Total likes** shows the raw, non-decaying count. The Works page order updates on the next reload, so you can use the refresh button at the top right.

### I linked my account, so why can't I submit?
Check that the link has been verified by a moderator and that the work's author is the same external account. See [Account Links](./account-links.md).
