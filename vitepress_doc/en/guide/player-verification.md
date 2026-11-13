---
title: Player Verification - Open Minesweeper
description: How player verification works on Open Minesweeper — getting verified, verifying other players, and how verification relates to replay uploads, tournament entry, and superuser maintenance.
---

# Player Verification

Player verification is how Open Minesweeper confirms a player's identity and unlocks replay uploads and tournament entry. Once you have a real name on your profile or are verified by a verified player, you can upload replays and enter tournaments. The access state updates immediately when your real name or verification changes — no re-login required.

## Why verification exists

We want everyone using Open Minesweeper to be a real person, and we encourage players to connect with each other — in person, especially offline. If you are confident that a player is a real person, we suggest you verify them from the **Player verification** section of your settings page. Real-name and player verification together shape a community that puts real people first: a real name is you standing behind your own identity, while verifying another player is you passing that trust on to a friend you actually know.

## What verification unlocks

- The manual replay upload entry.
- Tournament entry (including the Weekly Tournament, Golden Sheep Cup, and others).

Access opens as soon as either "has a real name" or "verified by a verified player" is satisfied. Access is computed live from your effective user ID, real name (including a hidden name), and verification status — it is not stored as a separate field.

## How to get verified

Either of the following is enough:

### Option 1: Add your real name

Fill in your real name on your profile. The real name acts as your identity credential, and access opens immediately. If you qualify for name privacy, you can enable hiding later; verified players can still verify you afterwards.

### Option 2: Be verified by a verified player

A verified player can verify you directly from the **Player verification** section of their settings page by entering your site ID:

- You do not need to send a request first, and there is no approval step;
- Verification takes effect immediately and the relation between you and them is created;
- Once created, you cannot remove the relation yourself.

## How to verify other players

When you are yourself **verified**, the **Player verification** section of your settings page shows an input:

1. Enter the target player's site ID (the number in their profile URL) in **Target user ID**;
2. Click **Verify user**.

Note: verification is a directed relation, with the direction "verifier → verified". You can verify multiple players and be verified by multiple players; reverse and mutual relations are both legal and independent, but you cannot verify yourself.

## Checking your own verification status

Open the **Player verification** section of your settings page to see:

- **Status**: Verified / Not verified;
- **Replay & tournament access**: Granted / Blocked.

Both states refresh immediately after your real name or verification changes.

## During maintenance

When a superuser makes bulk adjustments to verification relations, they open an exclusive maintenance session (duration chosen by the superuser, up to 1 hour). While maintenance is active:

- Regular player-to-player verification is paused;
- Read endpoints for status and the graph structure stay available;
- The superuser can still submit bulk adjustments inside the maintenance session.

The maintenance session auto-recovers when it expires, or releases immediately when the superuser ends it.

## FAQ

### I am verified, so why is the upload entry still unavailable?

Access depends on both your real name and verification status. If you revoked your real name or your verification was removed, access closes accordingly. Check that the **Replay & tournament access** line in the **Player verification** section of your settings page shows **Granted**.

### Can I remove my own verified status?

No. Once a verification relation is created it links you and the verifier, and there is no self-service removal. Contact the superuser if an adjustment is needed.

### Is verification the same as a real name?

No. A real name is the name credential you fill in yourself; player verification is the relation other verified players have with you. `verified` is your current effective verification result — it does not mean you have a real name, nor does it imply a staff role.
