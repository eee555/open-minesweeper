import { describe, expect, it } from 'vitest';

import { AccountLinks } from './collection';
import type { AccountLinksResponse } from './collection';
import { AccountDiscord, isDiscordUserId } from './discord';
import { AccountLinkPlatform, manualAccountLinkPlatforms, privateAccountLinkPlatforms } from './platforms';

describe('manual Discord account links', () => {
    it('preserves numeric IDs beyond JavaScript integer precision', () => {
        const id = '18446744073709551615';
        expect(isDiscordUserId(id)).toBe(true);
        const response: AccountLinksResponse = {
            summary: [{ id: 1, platform: 'd', identifier: id, userprofile: 1, verified: true }],
            B: null,
            m: null,
            c: null,
            a: null,
            w: null,
            q: null,
            d: { id, parent: 1 },
        };
        const links = new AccountLinks(response);
        expect(links.d?.id).toBe(id);
        expect(links.d?.parent).toBe(1);
        expect(links.getSummary('d')?.identifier).toBe(id);
    });

    it('rejects names, noncanonical numbers and identifiers that exceed storage', () => {
        for (const id of ['', '0', '01', '-1', '1.5', '1e18', 'player', '１２３', '123 ', ' 123', '1'.repeat(21)]) {
            expect(isDiscordUserId(id), id).toBe(false);
        }
    });

    it('uses the same manual and private platform categories as QQ', () => {
        for (const platform of [AccountLinkPlatform.Discord, AccountLinkPlatform.QQ]) {
            expect(manualAccountLinkPlatforms).toContain(platform);
            expect(privateAccountLinkPlatforms).toContain(platform);
        }
        expect(manualAccountLinkPlatforms).not.toContain(AccountLinkPlatform.Mineracer);
    });

    it('handles absent account details and ignores obsolete OAuth profile fields', () => {
        expect(new AccountDiscord().id).toBe('');
        const oldResponse = { id: '123', parent: 1, username: 'obsolete', avatar: 'old-avatar' };
        expect(new AccountDiscord(oldResponse)).toEqual({ id: '123', parent: 1 });
    });
});
