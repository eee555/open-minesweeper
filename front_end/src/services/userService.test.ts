import 'fake-indexeddb/auto';

import { openDB } from 'idb';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { SaoleiCacheDB } from './database';
import { CACHE_DB_NAME, CACHE_DB_VERSION, CACHE_STORE_SCHEMA_VERSIONS, META_STORE_NAME, USER_INFO_STORE_NAME, VIDEO_INFO_STORE_NAME } from './database';

import type { GetUserInfoResponse } from '@/utils/common/structInterface';

const STORE_NAME = USER_INFO_STORE_NAME;
const STORE_VERSIONS_KEY = 'storeVersions';
const ROW_SCHEMAS_KEY = 'rowSchemas';

interface ServiceConfigValue {
    userInfoUpdateInterval: number;
    userInfoLastUpdate: number;
    userInfoBatchDelay: number;
    userInfoBatchSize: number;
}

const axiosGet = vi.fn();
const serviceConfig = {
    value: {
        userInfoUpdateInterval: 86400000,
        userInfoLastUpdate: Date.now(),
        userInfoBatchDelay: 1,
        userInfoBatchSize: 100,
    },
};

vi.mock('@/http', () => ({ default: { get: axiosGet } }));
vi.mock('./store', () => ({ serviceConfig }));

function createUser(id: number, realname: string): GetUserInfoResponse {
    return {
        id,
        username: `user${id}`,
        firstname: '',
        lastname: '',
        realname,
        is_banned: false,
        is_staff: false,
        country: '',
        signature: '',
        last_change_avatar: '',
        last_change_signature: '',
        left_avatar_n: 0,
        left_signature_n: 0,
    };
}

async function openUserInfoDB() {
    return openDB<SaoleiCacheDB>(CACHE_DB_NAME, CACHE_DB_VERSION, {
        upgrade(db) {
            if (!db.objectStoreNames.contains(META_STORE_NAME)) {
                db.createObjectStore(META_STORE_NAME);
            }
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            }
            if (!db.objectStoreNames.contains(VIDEO_INFO_STORE_NAME)) {
                db.createObjectStore(VIDEO_INFO_STORE_NAME, { keyPath: ['scope', 'id'] }).createIndex('scope', 'scope');
            }
        },
    });
}

async function putCachedUser(user: GetUserInfoResponse) {
    const db = await openUserInfoDB();
    await db.put(META_STORE_NAME, CACHE_STORE_SCHEMA_VERSIONS, STORE_VERSIONS_KEY);
    await db.put(STORE_NAME, user);
    db.close();
}

async function putRawCachedUser(row: Record<string, unknown>, rowSchema: Record<string, unknown>) {
    const db = await openUserInfoDB();
    await db.put(META_STORE_NAME, CACHE_STORE_SCHEMA_VERSIONS, STORE_VERSIONS_KEY);
    await db.put(META_STORE_NAME, { [STORE_NAME]: rowSchema }, ROW_SCHEMAS_KEY);
    await db.put(STORE_NAME, row);
    db.close();
}

async function getCachedUser(userId: number) {
    const db = await openUserInfoDB();
    const user = await db.get(STORE_NAME, userId);
    db.close();
    return user as GetUserInfoResponse | undefined;
}

async function loadFetchUserInfo(config: Partial<ServiceConfigValue> = {}) {
    vi.resetModules();
    Object.assign(serviceConfig.value, {
        userInfoUpdateInterval: 86400000,
        userInfoLastUpdate: Date.now(),
        userInfoBatchDelay: 1,
        userInfoBatchSize: 100,
        ...config,
    });

    const { fetchUserInfo } = await import('./userService');
    return fetchUserInfo;
}

async function clearUserInfoDB() {
    const db = await openUserInfoDB();
    await db.clear(STORE_NAME);
    db.close();
}

async function waitForBatch() {
    await new Promise((resolve) => {
        setTimeout(resolve, serviceConfig.value.userInfoBatchDelay + 10);
    });
}

describe('fetchUserInfo', () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    beforeEach(async () => {
        axiosGet.mockReset();
        await clearUserInfoDB();
    });

    it('returns cached user info without requesting infobulk', async () => {
        await putCachedUser(createUser(1, 'Cached User'));
        const fetchUserInfo = await loadFetchUserInfo();

        const user = await fetchUserInfo(1);

        expect(user.id).toBe(1);
        expect(user.realname).toBe('Cached User');
        expect(axiosGet).not.toHaveBeenCalled();
    });

    it('immediately requests single user info and updates cache', async () => {
        await putCachedUser(createUser(1, 'Cached User'));
        const fetchUserInfo = await loadFetchUserInfo({
            userInfoLastUpdate: 0,
            userInfoUpdateInterval: 0,
        });
        axiosGet.mockResolvedValueOnce({ data: createUser(1, 'Immediate User') });

        const user = await fetchUserInfo(1, true);

        expect(user.realname).toBe('Immediate User');
        expect((await getCachedUser(1))?.realname).toBe('Immediate User');
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(axiosGet).toHaveBeenCalledWith('/api/userprofile/info/1');
    });

    it('migrates cached user rows when row schema changes', async () => {
        await putRawCachedUser(
            {
                id: '1',
                username: 'user1',
                realname: 'Migrated User',
                is_banned: 'false',
                unused_column: 'removed',
            },
            {
                id: { type: 'string' },
                username: { type: 'string' },
                realname: { type: 'string' },
                is_banned: { type: 'string' },
                unused_column: { type: 'string' },
            },
        );
        const fetchUserInfo = await loadFetchUserInfo();

        const user = await fetchUserInfo(1);
        const cached = await getCachedUser(1);

        expect(user.realname).toBe('Migrated User');
        expect(cached?.id).toBe(1);
        expect(cached?.is_banned).toBe(false);
        expect(cached?.left_avatar_n).toBe(0);
        expect(cached).not.toHaveProperty('unused_column');
        expect(axiosGet).not.toHaveBeenCalled();
    });

    it('clears cached user rows when row migration fails', async () => {
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        await putRawCachedUser(
            {
                id: 1,
                username: 'user1',
                realname: 'Broken User',
                is_banned: 'not-a-boolean',
            },
            {
                id: { type: 'number' },
                username: { type: 'string' },
                realname: { type: 'string' },
                is_banned: { type: 'string' },
            },
        );
        const fetchUserInfo = await loadFetchUserInfo();
        axiosGet.mockResolvedValueOnce({ data: [createUser(1, 'Fresh User')] });

        const promise = fetchUserInfo(1);
        await waitForBatch();
        const user = await promise;

        expect(user.realname).toBe('Fresh User');
        expect((await getCachedUser(1))?.realname).toBe('Fresh User');
        expect(axiosGet).toHaveBeenCalledWith('/api/userprofile/infobulk', { params: { ids: '1' } });
        expect(warnSpy).toHaveBeenCalledOnce();
        warnSpy.mockRestore();
    });

    it('clears local cache instead of requesting infoupdated when lastUpdate is zero', async () => {
        await putCachedUser(createUser(1, 'Stale User'));
        const fetchUserInfo = await loadFetchUserInfo({
            userInfoLastUpdate: 0,
            userInfoUpdateInterval: 0,
        });
        axiosGet.mockResolvedValueOnce({ data: [createUser(1, 'Fresh User')] });
        const now = Date.now();

        const promise = fetchUserInfo(1);
        await waitForBatch();
        const user = await promise;

        expect(user.realname).toBe('Fresh User');
        expect((await getCachedUser(1))?.realname).toBe('Fresh User');
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(axiosGet).toHaveBeenCalledWith('/api/userprofile/infobulk', { params: { ids: '1' } });
        expect(serviceConfig.value.userInfoLastUpdate).toBeGreaterThanOrEqual(now);
    });

    it.each([{ updatedUserIds: [1] }, { updatedUserIds: [] }])('updates the timestamp after a delayed invalidation response containing $updatedUserIds', async ({ updatedUserIds }) => {
        await putCachedUser(createUser(1, 'Stale User'));
        const fetchUserInfo = await loadFetchUserInfo({
            userInfoLastUpdate: 100,
            userInfoUpdateInterval: 1000,
        });
        const now = vi.spyOn(Date, 'now').mockReturnValue(2000);
        const response = Promise.withResolvers<{ data: number[] }>();
        const started = Promise.withResolvers<undefined>();
        axiosGet.mockImplementationOnce(() => {
            started.resolve(undefined);
            return response.promise;
        });
        axiosGet.mockResolvedValueOnce({ data: [{ ...createUser(1, 'hidden'), firstname: 'hidden', lastname: 'hidden' }] });

        const promise = fetchUserInfo(1);
        await started.promise;
        // A separate read waits for any earlier readwrite transaction to finish while HTTP is pending.
        expect((await getCachedUser(1))?.realname).toBe('Stale User');
        expect(serviceConfig.value.userInfoLastUpdate).toBe(100);
        now.mockReturnValue(2500);
        response.resolve({ data: updatedUserIds });
        const user = await promise;

        const expectedName = updatedUserIds.length ? 'hidden' : 'Stale User';
        expect(user.realname).toBe(expectedName);
        expect((await getCachedUser(1))?.realname).toBe(expectedName);
        expect(serviceConfig.value.userInfoLastUpdate).toBe(2000);
        expect(axiosGet).toHaveBeenNthCalledWith(1, '/api/userprofile/infoupdated', { params: { since: 100 } });
        if (updatedUserIds.length) {
            expect(user.isNameHidden).toBe(true);
            expect(user.isAnonymous).toBe(false);
            expect(axiosGet).toHaveBeenNthCalledWith(2, '/api/userprofile/infobulk', { params: { ids: '1' } });
        }
        const requestCount = axiosGet.mock.calls.length;
        expect((await fetchUserInfo(1)).realname).toBe(expectedName);
        expect(axiosGet).toHaveBeenCalledTimes(requestCount);
    });

    it('preserves the timestamp on refresh failure and retries on the next fetch', async () => {
        await putCachedUser(createUser(1, 'Cached User'));
        const fetchUserInfo = await loadFetchUserInfo({ userInfoLastUpdate: 100, userInfoUpdateInterval: 1000 });
        vi.spyOn(Date, 'now').mockReturnValue(2000);
        axiosGet.mockRejectedValueOnce(new Error('Network unavailable'));

        expect((await fetchUserInfo(1)).realname).toBe('Cached User');
        expect(serviceConfig.value.userInfoLastUpdate).toBe(100);

        axiosGet.mockResolvedValueOnce({ data: [] });
        expect((await fetchUserInfo(1)).realname).toBe('Cached User');
        expect(serviceConfig.value.userInfoLastUpdate).toBe(2000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
        expect(axiosGet).toHaveBeenNthCalledWith(2, '/api/userprofile/infoupdated', { params: { since: 100 } });
    });

    it('batches concurrent cache misses into one infobulk request', async () => {
        const fetchUserInfo = await loadFetchUserInfo();
        axiosGet.mockResolvedValueOnce({
            data: [
                createUser(1, 'User One'),
                createUser(2, 'User Two'),
            ],
        });

        const user1Promise = fetchUserInfo(1);
        const user2Promise = fetchUserInfo(2);
        await waitForBatch();
        const [user1, user2] = await Promise.all([user1Promise, user2Promise]);

        expect(user1.realname).toBe('User One');
        expect(user2.realname).toBe('User Two');
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(axiosGet).toHaveBeenCalledWith('/api/userprofile/infobulk', { params: { ids: '1,2' } });
    });

    it('invalidates only the saved user immediately with the normal one-day interval and survives reload', async () => {
        await putCachedUser(createUser(1, 'Old Real Name'));
        await putCachedUser(createUser(2, 'Other User'));
        const fetchUserInfo = await loadFetchUserInfo();
        const { invalidateUserInfo, userInfoRevision } = await import('./userService');
        const lastUpdate = serviceConfig.value.userInfoLastUpdate;
        expect((await fetchUserInfo(1)).realname).toBe('Old Real Name');

        await invalidateUserInfo(1);
        expect(userInfoRevision(1)).toBe(1);
        expect(await getCachedUser(1)).toBeUndefined();
        expect((await getCachedUser(2))?.realname).toBe('Other User');
        expect(serviceConfig.value.userInfoLastUpdate).toBe(lastUpdate);
        axiosGet.mockResolvedValueOnce({ data: [{ ...createUser(1, 'hidden'), firstname: 'hidden', lastname: 'hidden' }] });

        const user = await fetchUserInfo(1);
        expect(user.isNameHidden).toBe(true);
        expect(axiosGet).toHaveBeenCalledExactlyOnceWith('/api/userprofile/infobulk', { params: { ids: '1' } });
        const reloadedFetch = await loadFetchUserInfo();
        expect((await reloadedFetch(1)).isNameHidden).toBe(true);
        expect(axiosGet).toHaveBeenCalledTimes(1);
    });

    it('discards a response started before a privacy save instead of restoring the old name', async () => {
        const fetchUserInfo = await loadFetchUserInfo();
        const { invalidateUserInfo } = await import('./userService');
        const response = Promise.withResolvers<{ data: GetUserInfoResponse[] }>();
        const started = Promise.withResolvers<undefined>();
        axiosGet.mockImplementationOnce(() => {
            started.resolve(undefined);
            return response.promise;
        });
        const oldRequest = fetchUserInfo(1);
        await started.promise;
        await invalidateUserInfo(1);
        axiosGet.mockResolvedValueOnce({ data: [{ ...createUser(1, 'hidden'), firstname: 'hidden', lastname: 'hidden' }] });
        expect((await fetchUserInfo(1)).isNameHidden).toBe(true);

        response.resolve({ data: [createUser(1, 'Old Real Name')] });
        expect((await oldRequest).isNameHidden).toBe(true);
        expect((await getCachedUser(1))?.realname).toBe('hidden');
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('preserves callers waiting for a batch that has not started when the cache is invalidated', async () => {
        const fetchUserInfo = await loadFetchUserInfo({ userInfoBatchDelay: 10000 });
        const { invalidateUserInfo } = await import('./userService');
        const scheduled = Promise.withResolvers<Parameters<typeof setTimeout>[0]>();
        const setTimer = globalThis.setTimeout;
        const timer = vi.spyOn(globalThis, 'setTimeout').mockImplementationOnce((callback) => {
            scheduled.resolve(callback);
            return setTimer(() => { /* The batch is released explicitly below. */ }, 0);
        });
        axiosGet.mockResolvedValue({ data: [createUser(1, 'hidden')] });
        const waiting = fetchUserInfo(1);
        const runBatch = await scheduled.promise;
        timer.mockRestore();
        await invalidateUserInfo(1);
        const fresh = fetchUserInfo(1);
        runBatch();

        const users = await Promise.all([waiting, fresh]);
        expect(users.every((user) => user.isNameHidden)).toBe(true);
        expect(axiosGet).toHaveBeenCalledTimes(1);
    });

    it('does not turn a saved profile into an error when local cache invalidation fails', async () => {
        await putCachedUser(createUser(1, 'Old Real Name'));
        const fetchUserInfo = await loadFetchUserInfo();
        const { invalidateUserInfo } = await import('./userService');
        const database = await import('./database');
        vi.spyOn(database, 'getTransaction').mockRejectedValueOnce(new Error('IndexedDB unavailable'));

        await expect(invalidateUserInfo(1)).resolves.toBeUndefined();
        expect(serviceConfig.value.userInfoLastUpdate).toBe(0);
        axiosGet.mockResolvedValueOnce({ data: [createUser(1, 'hidden')] });
        expect((await fetchUserInfo(1)).isNameHidden).toBe(true);
        expect((await getCachedUser(1))?.realname).toBe('hidden');
    });
});

describe('fetchUserVideos identity isolation', () => {
    beforeEach(() => axiosGet.mockReset());

    it('shares requests only within the same viewer and revision, and clears rejected requests', async () => {
        const { fetchUserVideos } = await import('./userService');
        const pending = Promise.withResolvers<{ data: [] }>();
        axiosGet.mockReturnValue(pending.promise);
        const owner = fetchUserVideos(42, 'owner-session', 0);
        expect(fetchUserVideos(42, 'owner-session', 0)).toBe(owner);
        const guest = fetchUserVideos(42, 'guest-session', 0);
        const updated = fetchUserVideos(42, 'owner-session', 1);
        expect(guest).not.toBe(owner);
        expect(updated).not.toBe(owner);
        expect(axiosGet).toHaveBeenCalledTimes(3);
        expect(axiosGet).toHaveBeenCalledWith('/api/userprofile/videolist', { params: { user_id: 42 } });
        pending.resolve({ data: [] });
        await Promise.all([owner, guest, updated]);
        axiosGet.mockRejectedValueOnce(new Error('network'));
        await expect(fetchUserVideos(42, 'owner-session', 1)).rejects.toThrow('network');
        axiosGet.mockResolvedValueOnce({ data: [] });
        expect(await fetchUserVideos(42, 'owner-session', 1)).toEqual([]);
        expect(axiosGet).toHaveBeenCalledTimes(5);
    });
});
