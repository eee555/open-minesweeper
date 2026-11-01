import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { authorizeDiscord, discordAvailable, discordHttpError, normalizeDiscordError, unlinkDiscord } from './discordService';

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/http', () => ({ default: http }));

describe('Discord authorization', () => {
    const assign = vi.fn();

    beforeEach(() => {
        vi.resetAllMocks();
        vi.stubGlobal('window', { location: { assign } });
    });

    afterEach(() => vi.unstubAllGlobals());

    it('uses server availability and preserves login expiry in the authorization request', async () => {
        http.get.mockResolvedValue({ data: { enabled: true } });
        expect(await discordAvailable()).toBe(true);
        http.post.mockResolvedValue({ data: { authorization_url: 'https://discord.com/oauth2/authorize?state=browser-state' } });
        await authorizeDiscord('login', 30);
        expect(http.post).toHaveBeenCalledWith('/api/accountlink/discord/start', { mode: 'login', set_expiry: 30 });
        expect(assign).toHaveBeenCalledWith('https://discord.com/oauth2/authorize?state=browser-state');
    });

    it('does not navigate to an unexpected authorization origin or endpoint', async () => {
        for (const url of ['https://evil.example/oauth2/authorize', 'https://discord.com/other', 'javascript:alert(1)']) {
            http.post.mockResolvedValue({ data: { authorization_url: url } });
            await expect(authorizeDiscord('link')).rejects.toThrow();
        }
        expect(assign).not.toHaveBeenCalled();
    });

    it('keeps the browser on the page if starting authorization fails', async () => {
        http.post.mockRejectedValue(new Error('offline'));
        await expect(authorizeDiscord('link')).rejects.toThrow('offline');
        expect(assign).not.toHaveBeenCalled();
    });

    it('unlinks only the identity belonging to the authenticated server session', async () => {
        http.post.mockResolvedValue({ data: { type: 'success' } });
        await unlinkDiscord();
        expect(http.post).toHaveBeenCalledWith('/api/accountlink/discord/unlink');
    });

    it('maps only known errors and never exposes arbitrary upstream text', () => {
        expect(discordHttpError({ isAxiosError: true, response: { data: { object: 'discord', category: 'identifier_conflict' } } })).toBe('identifier_conflict');
        expect(discordHttpError({ isAxiosError: true, response: { data: null } })).toBe('unknown');
        expect(normalizeDiscordError('<private upstream error>')).toBe('unknown');
        expect(normalizeDiscordError(['not_linked'])).toBe('unknown');
    });
});
