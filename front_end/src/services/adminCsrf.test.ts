import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { installAdminCsrfInterceptor } from './adminCsrf';

const { cookieGet } = vi.hoisted(() => ({ cookieGet: vi.fn<(name: string) => string | undefined>() }));
vi.mock('js-cookie', () => ({ default: { get: cookieGet } }));

function response(config: InternalAxiosRequestConfig, data: unknown = {}) {
    return { config, data, status: 200, statusText: 'OK', headers: {} };
}

function setup(admin = true, baseURL = 'https://site.test/') {
    const sent: InternalAxiosRequestConfig[] = [];
    const adapter = vi.fn((config: InternalAxiosRequestConfig) => {
        sent.push(config);
        return Promise.resolve(response(config, config.url === '/api/userprofile/admin/csrf' ? { csrf_token: 'server-token' } : {}));
    });
    const client = axios.create({ baseURL, adapter, withCredentials: true });
    const role = { admin };
    installAdminCsrfInterceptor(client, () => role.admin);
    return { client, sent, adapter, role };
}

describe('administrator CSRF transport', () => {
    beforeEach(() => {
        vi.stubGlobal('location', { href: 'https://site.test/page' });
        cookieGet.mockReset();
    });
    afterEach(() => vi.unstubAllGlobals());

    it('does not fetch or send a token for ordinary users', async () => {
        const { client, sent } = setup(false);
        for (const method of ['post', 'put', 'patch', 'delete']) await client.request({ method, url: '/api/user/action' });
        expect(sent).toHaveLength(4);
        expect(sent.every((config) => !config.headers.has('X-CSRFToken'))).toBe(true);
        expect(cookieGet).not.toHaveBeenCalled();
    });

    it('leaves safe requests, external destinations and explicit tokens alone', async () => {
        const { client, sent } = setup();
        for (const method of ['get', 'head', 'options']) await client.request({ method, url: '/api/staff/query' });
        await client.post('https://external.test/action');
        await client.post('/action', undefined, { baseURL: 'https://external.test/' });
        await client.post('/api/staff/action', undefined, { headers: { 'X-CSRFToken': 'explicit-token' } });
        expect(sent).toHaveLength(6);
        expect(sent.slice(0, 5).every((config) => !config.headers.has('X-CSRFToken'))).toBe(true);
        expect(sent.at(-1)?.headers.get('X-CSRFToken')).toBe('explicit-token');
        expect(cookieGet).not.toHaveBeenCalled();
    });

    it('reads the current cookie for each write, including a rotated token', async () => {
        cookieGet.mockReturnValue('first-cookie');
        const { client, sent } = setup(true, 'https://site.test:8443/');
        await client.post('/api/staff/action');
        cookieGet.mockReturnValue('rotated-cookie');
        await client.patch('/api/staff/action');
        expect(sent).toHaveLength(2);
        expect(sent.map((config) => config.headers.get('X-CSRFToken'))).toEqual(['first-cookie', 'rotated-cookie']);
    });

    it('gets a masked token from the backend when cookies are unavailable or on a different host', async () => {
        cookieGet.mockReturnValue('unrelated-frontend-cookie');
        const { client, sent } = setup(true, 'https://api.test/');
        await client.post('/api/staff/action');
        expect(sent.map((config) => config.url)).toEqual(['/api/userprofile/admin/csrf', '/api/staff/action']);
        expect(sent[0]?.headers.has('X-CSRFToken')).toBe(false);
        expect(sent[1]?.headers.get('X-CSRFToken')).toBe('server-token');
    });

    it('shares an in-flight token fetch but fetches again for the next batch', async () => {
        const { client, sent, adapter } = setup();
        let release: (() => void) | undefined;
        adapter.mockImplementationOnce((config) => new Promise((resolve) => {
            sent.push(config);
            release = () => {
                resolve(response(config, { csrf_token: 'batch-token' }));
            };
        }));
        const first = client.post('/first');
        const second = client.delete('/second');
        await vi.waitFor(() => {
            expect(release).toBeDefined();
        });
        expect(sent).toHaveLength(1);
        release?.();
        await Promise.all([first, second]);
        expect(sent.slice(1).map((config) => config.headers.get('X-CSRFToken'))).toEqual(['batch-token', 'batch-token']);
        await client.post('/third');
        expect(sent.filter((config) => config.url === '/api/userprofile/admin/csrf')).toHaveLength(2);
        expect(sent.at(-1)?.headers.get('X-CSRFToken')).toBe('server-token');
    });

    it('does not dispatch or retry a write if token retrieval fails', async () => {
        const { client, adapter } = setup();
        adapter.mockRejectedValueOnce(new Error('access denied'));
        await expect(client.post('/api/staff/action')).rejects.toThrow('access denied');
        expect(adapter).toHaveBeenCalledTimes(1);
        expect(adapter.mock.calls[0]?.[0].url).toBe('/api/userprofile/admin/csrf');
    });

    it('does not dispatch a write when the bootstrap response has no valid token', async () => {
        const { client, adapter } = setup();
        adapter.mockImplementationOnce((config) => Promise.resolve(response(config, { csrf_token: null })));
        await expect(client.post('/api/staff/action')).rejects.toThrow('Missing administrator CSRF token');
        expect(adapter).toHaveBeenCalledTimes(1);
    });

    it('stops a pending administrator write if the session changes', async () => {
        const { client, sent, adapter, role } = setup();
        adapter.mockImplementationOnce((config) => {
            role.admin = false;
            sent.push(config);
            return Promise.resolve(response(config, { csrf_token: 'old-session-token' }));
        });
        await expect(client.post('/api/staff/action')).rejects.toThrow('Administrative session changed');
        expect(sent).toHaveLength(1);
    });
});
