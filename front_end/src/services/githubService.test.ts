import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchGitHubProfile, startGitHubLink } from './githubService';

import $axios from '@/http';

vi.mock('@/http', () => ({ default: { post: vi.fn() } }));
afterEach(() => {
    vi.unstubAllGlobals(); vi.clearAllMocks();
});

describe('GitHub public profile', () => {
    it('fetches by numeric ID without website cookies and builds a canonical profile URL', async () => {
        const remote = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 42, login: 'Renamed-user', html_url: 'https://untrusted.test/' })));
        vi.stubGlobal('fetch', remote);
        const { signal } = new AbortController();
        expect(await fetchGitHubProfile('42', signal)).toEqual({ id: '42', login: 'Renamed-user', url: 'https://github.com/Renamed-user' });
        expect(remote).toHaveBeenCalledWith('https://api.github.com/user/42', { credentials: 'omit', signal });
        expect($axios.post).not.toHaveBeenCalled();
    });

    it('rejects rate limits and responses for a different identity', async () => {
        const remote = vi.fn().mockResolvedValueOnce(new Response('{}', { status: 403 })).
            mockResolvedValueOnce(new Response(JSON.stringify({ id: 43, login: 'SomeoneElse' })));
        vi.stubGlobal('fetch', remote);
        await expect(fetchGitHubProfile('42')).rejects.toThrow('HTTP 403');
        await expect(fetchGitHubProfile('42')).rejects.toThrow('Invalid GitHub profile');
    });

    it('does not send malformed IDs and rejects invalid usernames or imprecise IDs', async () => {
        const remote = vi.fn();
        vi.stubGlobal('fetch', remote);
        await expect(fetchGitHubProfile('42/../user')).rejects.toThrow('Invalid GitHub ID');
        expect(remote).not.toHaveBeenCalled();
        for (const profile of [{ id: 42, login: '../login' }, { id: 9007199254740992, login: 'user' }]) {
            remote.mockResolvedValueOnce(new Response(JSON.stringify(profile)));
            await expect(fetchGitHubProfile(String(profile.id))).rejects.toThrow('Invalid GitHub profile');
        }
    });
});

describe('GitHub authorization URL', () => {
    it('accepts only the GitHub authorization endpoint', async () => {
        vi.mocked($axios.post).mockResolvedValueOnce({ data: { authorization_url: 'https://github.com/login/oauth/authorize?state=test' } });
        expect(await startGitHubLink()).toBe('https://github.com/login/oauth/authorize?state=test');
        for (const url of ['https://attacker.test/login/oauth/authorize', 'https://github.com.evil.test/login/oauth/authorize', 'https://github.com/login']) {
            vi.mocked($axios.post).mockResolvedValueOnce({ data: { authorization_url: url } });
            await expect(startGitHubLink()).rejects.toThrow('Invalid authorization URL');
        }
    });
});
