import { describe, expect, it } from 'vitest';

import { AccountLinks } from './collection';
import type { AccountLinksResponse } from './collection';
import { AccountDiscord } from './discord';

describe('Discord account links', () => {
    const base = { id: '803511102246789123', parent: 1, username: 'player', global_name: '', update_time: '2026-10-31T12:00:00Z' };

    it('uses official CDN paths for static and animated images', () => {
        const account = new AccountDiscord({ ...base, avatar: 'a_' + 'a'.repeat(32), banner: 'b'.repeat(32) });
        expect(account.avatarUrl).toBe(`https://cdn.discordapp.com/avatars/${base.id}/a_${'a'.repeat(32)}.gif?size=128`);
        expect(account.bannerUrl).toBe(`https://cdn.discordapp.com/banners/${base.id}/${'b'.repeat(32)}.png?size=512`);
        expect(new AccountDiscord({ ...base, avatar: '../image' }).avatarUrl).toBeUndefined();
    });

    it('handles omitted and cleared optional fields without inventing a color or badge', () => {
        const account = new AccountDiscord(base);
        expect(account.avatarUrl).toBeUndefined();
        expect(account.bannerUrl).toBeUndefined();
        expect(account.accentColor).toBeUndefined();
        expect(account.badgeNames).toEqual([]);
        const cleared = new AccountDiscord({ ...base, avatar: null, banner: null, accent_color: null, public_flags: null });
        expect(cleared.avatarUrl).toBeUndefined();
        expect(cleared.bannerUrl).toBeUndefined();
    });

    it('preserves zero colors and flags while keeping unknown bits', () => {
        const black = new AccountDiscord({ ...base, accent_color: 0, public_flags: 0 });
        expect(black.accentColor).toBe('#000000');
        expect(black.badgeNames).toEqual([]);
        const account = new AccountDiscord({ ...base, accent_color: 0x5865F2, public_flags: 2 ** 40 + 64 + 512 });
        expect(account.accentColor).toBe('#5865f2');
        expect(account.badgeNames).toEqual(['bravery', 'earlySupporter']);
        expect(account.public_flags).toBe(2 ** 40 + 64 + 512);
    });

    it('preserves snowflake precision throughout the aggregate response', () => {
        const response: AccountLinksResponse = {
            summary: [{ id: 1, platform: 'd', identifier: '18446744073709551615', userprofile: 1, verified: true }],
            B: null,
            m: null,
            c: null,
            a: null,
            w: null,
            q: null,
            d: { id: '18446744073709551615', parent: 1, username: 'player', global_name: '', update_time: '2026-10-31T12:00:00Z' },
        };
        const links = new AccountLinks(response);
        expect(links.d?.id).toBe('18446744073709551615');
        expect(links.getSummary('d')?.identifier).toBe(links.d?.id);
        expect(links.d?.update_time.toISOString()).toBe('2026-10-31T12:00:00.000Z');
    });
});
