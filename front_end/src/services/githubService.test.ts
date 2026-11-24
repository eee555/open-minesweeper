import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchGitHubProfile, fetchGitHubRepositoryInfo, fetchGitHubRepositoryUrl, resetGitHubRepositoryCache, startGitHubLink } from './githubService';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/http', () => ({ default: { post } }));
afterEach(() => {
    vi.unstubAllGlobals(); vi.clearAllMocks(); resetGitHubRepositoryCache();
});

describe('GitHub public profile', () => {
    it('fetches by numeric ID without website cookies and builds a canonical profile URL', async () => {
        const remote = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 42, login: 'Renamed-user', html_url: 'https://untrusted.test/' })));
        vi.stubGlobal('fetch', remote);
        const { signal } = new AbortController();
        expect(await fetchGitHubProfile('42', signal)).toEqual({ id: '42', login: 'Renamed-user', url: 'https://github.com/Renamed-user' });
        expect(remote).toHaveBeenCalledWith('https://api.github.com/user/42', { credentials: 'omit', signal });
        expect(post).not.toHaveBeenCalled();
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
        post.mockResolvedValueOnce({ data: { authorization_url: 'https://github.com/login/oauth/authorize?state=test' } });
        expect(await startGitHubLink()).toBe('https://github.com/login/oauth/authorize?state=test');
        for (const url of ['https://attacker.test/login/oauth/authorize', 'https://github.com.evil.test/login/oauth/authorize', 'https://github.com/login']) {
            post.mockResolvedValueOnce({ data: { authorization_url: url } });
            await expect(startGitHubLink()).rejects.toThrow('Invalid authorization URL');
        }
    });
});

describe('GitHub repository links', () => {
    it('resolves a repository by ID without cookies and follows the current name from metadata', async () => {
        const remote = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 42, html_url: 'https://github.com/new-owner/new-name' })));
        vi.stubGlobal('fetch', remote);
        const { signal } = new AbortController();
        expect(await fetchGitHubRepositoryUrl('42', signal)).toBe('https://github.com/new-owner/new-name');
        expect(remote).toHaveBeenCalledWith('https://api.github.com/repositories/42', { credentials: 'omit', signal });
        expect(post).not.toHaveBeenCalled();
    });

    it('rejects invalid IDs, identity mismatches, unsafe URLs and imprecise IDs', async () => {
        const remote = vi.fn();
        vi.stubGlobal('fetch', remote);
        await expect(fetchGitHubRepositoryUrl('../repos')).rejects.toThrow('Invalid GitHub repository ID');
        expect(remote).not.toHaveBeenCalled();
        for (const [id, html_url] of [
            [43, 'https://github.com/a/b'], [9007199254740992, 'https://github.com/a/b'],
            [42, 'https://github.com.evil.test/a/b'], [42, 'https://user@github.com/a/b'],
            [42, 'https://github.com:443/a/b'], [42, 'javascript:alert(1)'],
            [42, 'https://github.com/a/b/tree/main'], [42, 'https://github.com/a/../b'],
        ]) {
            remote.mockResolvedValueOnce(new Response(JSON.stringify({ id, html_url })));
            await expect(fetchGitHubRepositoryUrl('42')).rejects.toThrow('Invalid GitHub repository');
        }
    });

    it('keeps rate limits and missing repositories as retryable lookup failures', async () => {
        for (const status of [403, 404, 429]) {
            vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status })));
            await expect(fetchGitHubRepositoryUrl('42')).rejects.toThrow(`HTTP ${status}`);
        }
    });
});

describe('GitHub repository details', () => {
    const payload = { id: 42, full_name: 'owner/project', description: 'A minesweeper client', html_url: 'https://github.com/owner/project' };

    it('reads the repository name and description by numeric ID without website cookies', async () => {
        const remote = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
        vi.stubGlobal('fetch', remote);
        const { signal } = new AbortController();
        expect(await fetchGitHubRepositoryInfo('42', signal)).toEqual({ id: '42', fullName: 'owner/project', description: 'A minesweeper client', htmlUrl: 'https://github.com/owner/project' });
        expect(remote).toHaveBeenCalledWith('https://api.github.com/repositories/42', { credentials: 'omit', signal });
        expect(post).not.toHaveBeenCalled();
    });

    it('caches successful lookups and falls back to the URL path when metadata is absent', async () => {
        const remote = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 42, description: null, html_url: 'https://github.com/owner/project' })));
        vi.stubGlobal('fetch', remote);
        expect(await fetchGitHubRepositoryInfo('42')).toEqual({ id: '42', fullName: 'owner/project', description: '', htmlUrl: 'https://github.com/owner/project' });
        expect(await fetchGitHubRepositoryInfo('42')).toEqual({ id: '42', fullName: 'owner/project', description: '', htmlUrl: 'https://github.com/owner/project' });
        expect(remote).toHaveBeenCalledTimes(1);
        resetGitHubRepositoryCache();
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))));
        expect((await fetchGitHubRepositoryInfo('42')).description).toBe('A minesweeper client');
    });

    it('rejects a full name that does not match the validated repository URL', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...payload, full_name: 'attacker/other' }))));
        await expect(fetchGitHubRepositoryInfo('42')).rejects.toThrow('Invalid GitHub repository');
    });

    it('never sends malformed IDs and keeps lookup failures retryable', async () => {
        const remote = vi.fn();
        vi.stubGlobal('fetch', remote);
        await expect(fetchGitHubRepositoryInfo('42/../repos')).rejects.toThrow('Invalid GitHub repository ID');
        expect(remote).not.toHaveBeenCalled();
        remote.mockResolvedValueOnce(new Response('{}', { status: 403 }));
        await expect(fetchGitHubRepositoryInfo('42')).rejects.toThrow('HTTP 403');
        remote.mockResolvedValueOnce(new Response(JSON.stringify(payload)));
        expect((await fetchGitHubRepositoryInfo('42')).fullName).toBe('owner/project');
    });
});
