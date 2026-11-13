import axios from 'axios';
import type { AxiosInstance } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { applyLoginSession as applyLoginSessionFunction, refreshSelfAccess as refreshSelfAccessFunction } from './loginSession';

import type { UserProfileData } from '@/utils/userprofile';

const { store, moduleLoads, install } = vi.hoisted(() => ({
    store: { sessionRevision: 0, user: { id: 0, is_staff: false, is_superuser: false, verified: false, can_submit_replays: false }, login: vi.fn<(user: UserProfileData) => void>() },
    moduleLoads: vi.fn(),
    install: vi.fn<(client: AxiosInstance, isAdmin: () => boolean) => number>(),
}));
vi.mock('@/store', () => ({ store }));

let applyLoginSession: typeof applyLoginSessionFunction;
let refreshSelfAccess: typeof refreshSelfAccessFunction;
let loadGate: Promise<void> | undefined;

function deferred() {
    let resolve!: () => void;
    let reject!: (error: Error) => void;
    const promise = new Promise<void>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

function client() {
    return axios.create({ adapter: (config) => Promise.resolve({ config, data: config.headers.get('X-CSRFToken') ?? null, status: 200, statusText: 'OK', headers: {} }) });
}

function loginAutoClient(user: unknown) {
    return axios.create({ adapter: (config) => Promise.resolve({ config, data: { user }, status: 200, statusText: 'OK', headers: {} }) });
}

describe('lazy administrator session setup', () => {
    beforeEach(async () => {
        vi.resetModules();
        moduleLoads.mockClear();
        store.sessionRevision = 0;
        store.user = { id: 0, is_staff: false, is_superuser: false, verified: false, can_submit_replays: false };
        store.login.mockReset().mockImplementation((user) => {
            store.user = { id: user.id ?? 0, is_staff: user.is_staff ?? false, is_superuser: user.is_superuser ?? false, verified: false, can_submit_replays: false };
            store.sessionRevision++;
        });
        install.mockReset().mockImplementation((http, isAdmin) => http.interceptors.request.use((config) => {
            if (isAdmin()) config.headers.set('X-CSRFToken', 'ready-token');
            return config;
        }));
        loadGate = undefined;
        vi.doMock('./adminCsrf', async () => {
            moduleLoads();
            if (loadGate) await loadGate;
            return { installAdminCsrfInterceptor: install };
        });
        ({ applyLoginSession, refreshSelfAccess } = await import('./loginSession'));
    });

    afterEach(() => {
        vi.doUnmock('./adminCsrf');
    });

    it('publishes ordinary user sessions without importing CSRF code', async () => {
        const user = { id: 1 };
        expect(await applyLoginSession(user, client())).toBe(true);
        expect(moduleLoads).not.toHaveBeenCalled();
        expect(install).not.toHaveBeenCalled();
        expect(store.login).toHaveBeenCalledWith(user);
    });

    it.each([{ is_staff: true }, { is_superuser: true }])('prepares CSRF before publishing management role %j', async (role) => {
        const gate = deferred();
        loadGate = gate.promise;
        const http = client();
        const pending = applyLoginSession({ id: 2, ...role }, http);
        await vi.waitFor(() => {
            expect(moduleLoads).toHaveBeenCalledOnce();
        });
        expect(store.login).not.toHaveBeenCalled();
        gate.resolve();
        expect(await pending).toBe(true);
        const firstWrite = await http.post('/management');
        expect(firstWrite.data).toBe('ready-token');
        expect(install).toHaveBeenCalledOnce();
    });

    it('installs only once for repeated management logins on the same client', async () => {
        const http = client();
        await applyLoginSession({ id: 2, is_staff: true }, http);
        await applyLoginSession({ id: 3, is_superuser: true }, http);
        expect(install).toHaveBeenCalledOnce();
        expect(moduleLoads).toHaveBeenCalledOnce();
    });

    it('shares concurrent setup and publishes only the latest login', async () => {
        const gate = deferred();
        loadGate = gate.promise;
        const http = client();
        const first = applyLoginSession({ id: 2, is_staff: true }, http);
        const second = applyLoginSession({ id: 3, is_staff: true }, http);
        await vi.waitFor(() => {
            expect(moduleLoads).toHaveBeenCalledOnce();
        });
        gate.resolve();
        expect(await Promise.all([first, second])).toEqual([false, true]);
        expect(install).toHaveBeenCalledOnce();
        expect(store.login).toHaveBeenCalledExactlyOnceWith({ id: 3, is_staff: true });
    });

    it('does not overwrite a newer ordinary login when the management module finishes loading', async () => {
        const gate = deferred();
        loadGate = gate.promise;
        const http = client();
        const pending = applyLoginSession({ id: 2, is_staff: true }, http);
        await vi.waitFor(() => {
            expect(moduleLoads).toHaveBeenCalledOnce();
        });
        expect(await applyLoginSession({ id: 3 }, http)).toBe(true);
        gate.resolve();
        expect(await pending).toBe(false);
        expect(store.login).toHaveBeenCalledExactlyOnceWith({ id: 3 });
        expect((await http.post('/ordinary')).data).toBe(null);
    });

    it('does not restore a management login after logout during module loading', async () => {
        const gate = deferred();
        loadGate = gate.promise;
        const pending = applyLoginSession({ id: 2, is_staff: true }, client());
        await vi.waitFor(() => {
            expect(moduleLoads).toHaveBeenCalledOnce();
        });
        store.sessionRevision++;
        gate.resolve();
        expect(await pending).toBe(false);
        expect(store.login).not.toHaveBeenCalled();
    });

    it('does not publish a management session when module loading fails', async () => {
        const gate = deferred();
        loadGate = gate.promise;
        const pending = applyLoginSession({ id: 2, is_staff: true }, client());
        const rejection = expect(pending).rejects.toThrow();
        await vi.waitFor(() => {
            expect(moduleLoads).toHaveBeenCalledOnce();
        });
        gate.reject(new Error('module unavailable'));
        await rejection;
        expect(store.login).not.toHaveBeenCalled();
        expect(install).not.toHaveBeenCalled();
    });

    it('allows a later attempt after installation fails', async () => {
        install.mockImplementationOnce(() => {
            throw new Error('installation failed');
        });
        const http = client();
        await expect(applyLoginSession({ id: 2, is_staff: true }, http)).rejects.toThrow('installation failed');
        expect(store.login).not.toHaveBeenCalled();
        expect(await applyLoginSession({ id: 2, is_staff: true }, http)).toBe(true);
        expect(install).toHaveBeenCalledTimes(2);
    });

    describe('refreshSelfAccess', () => {
        it('updates the backend-derived access fields without replacing the session object', async () => {
            store.user.id = 42;
            const before = store.user;
            expect(await refreshSelfAccess(42, loginAutoClient({ id: 42, verified: true, can_submit_replays: true }))).toBe(true);
            expect(store.user).toBe(before);
            expect(store.user.verified).toBe(true);
            expect(store.user.can_submit_replays).toBe(true);
            expect(store.login).not.toHaveBeenCalled();
        });

        it('does not overwrite a later login with a different account', async () => {
            store.user.id = 42;
            expect(await refreshSelfAccess(42, loginAutoClient({ id: 99, can_submit_replays: true }))).toBe(false);
            expect(store.user.can_submit_replays).toBe(false);
            expect(store.login).not.toHaveBeenCalled();
        });

        it('skips a stale page whose account has already changed', async () => {
            store.user.id = 99;
            expect(await refreshSelfAccess(42, loginAutoClient({ id: 42, can_submit_replays: true }))).toBe(false);
            expect(store.login).not.toHaveBeenCalled();
        });

        it('skips guests and logged-out sessions', async () => {
            expect(await refreshSelfAccess(0, loginAutoClient({ id: 0 }))).toBe(false);
            expect(await refreshSelfAccess(42, loginAutoClient(null))).toBe(false);
            expect(store.login).not.toHaveBeenCalled();
        });

        it('ignores a response when another login happened while the request was pending', async () => {
            store.user.id = 42;
            const before = store.user;
            const http = axios.create({ adapter: (config) => {
                store.login({ id: 42 });
                return Promise.resolve({ config, data: { user: { id: 42, verified: true, can_submit_replays: true } }, status: 200, statusText: 'OK', headers: {} });
            } });
            expect(await refreshSelfAccess(42, http)).toBe(false);
            expect(before.verified).toBe(false);
            expect(before.can_submit_replays).toBe(false);
        });
    });
});
