import { reactive } from 'vue';

import type { CacheRowSchema } from './database';
import { getDatabase, getTransaction, registerStoreRowSchema, USER_INFO_STORE_NAME } from './database';
import { serviceConfig } from './store';
import { fetchVideoList } from './videoService';

import $axios from '@/http';
import type { GetUserInfoResponse } from '@/utils/common/structInterface';
import { UserProfile } from '@/utils/userprofile';
import type { VideoAbstract } from '@/utils/videoabstract';

type RequestStatus = 'pending' | 'inFlight';
interface UserInfoRequest {
    promise: Promise<GetUserInfoResponse>;
    resolve: (value: GetUserInfoResponse) => void;
    reject: (reason?: unknown) => void;
    status: RequestStatus;
    revision: number;
}

const userInfoRequests = new Map<number, UserInfoRequest>();
const userInfoRevisions = reactive(new Map<number, number>());
const userInfoInvalidations = new Map<number, Promise<void>>();
const invalidatedUsers = new Set<number>();

export function userInfoRevision(userId: number): number {
    return userInfoRevisions.get(userId) ?? 0;
}

export function invalidateUserInfo(userId: number): Promise<void> {
    if (userId <= 0) return Promise.resolve();
    invalidatedUsers.add(userId);
    const previous = userInfoInvalidations.get(userId);
    const invalidation = (async () => {
        await previous;
        try {
            const tx = await getTransaction(USER_INFO_STORE_NAME, 'readwrite');
            await tx.store.delete(userId);
            await tx.done;
        } catch {
            // A saved profile must not appear to fail because its local cache is unavailable.
            serviceConfig.value.userInfoLastUpdate = 0;
        }
    })().finally(() => {
        if (userInfoInvalidations.get(userId) === invalidation) userInfoInvalidations.delete(userId);
    });
    userInfoInvalidations.set(userId, invalidation);
    const revision = userInfoRevision(userId) + 1;
    const pending = userInfoRequests.get(userId);
    // Unsent requests can use the new revision without abandoning their callers.
    if (pending?.status === 'pending') pending.revision = revision;
    userInfoRevisions.set(userId, revision);
    return invalidation;
}

registerStoreRowSchema(USER_INFO_STORE_NAME, {
    id: { type: 'number' },
    username: { type: 'string', default: '' },
    firstname: { type: 'string', default: '' },
    lastname: { type: 'string', default: '' },
    realname: { type: 'string', default: '' },
    is_banned: { type: 'boolean', default: false },
    is_staff: { type: 'boolean', default: false },
    country: { type: 'string', default: '' },
    signature: { type: 'string', default: '' },
    last_change_avatar: { type: 'string', default: '' },
    last_change_signature: { type: 'string', default: '' },
    left_avatar_n: { type: 'number', default: 0 },
    left_signature_n: { type: 'number', default: 0 },
} satisfies CacheRowSchema);

let batchTimer: ReturnType<typeof setTimeout> | null = null;
let updateCachePromise: Promise<void> | null = null;

function scheduleBatchIfNeeded() {
    if (batchTimer) return;

    batchTimer = setTimeout(() => {
        batchTimer = null;
        void processUserInfoBatch();
    }, serviceConfig.value.userInfoBatchDelay);
}

/**
 * 将用户信息请求加入队列，如果同一用户已有请求则返回现有请求的Promise
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为GetUserInfoResponse类型的结果
 */
function enqueueRequest(userId: number): Promise<GetUserInfoResponse> {
    // 检查是否已有该用户的请求。如果存在，直接返回现有请求的Promise
    const existing = userInfoRequests.get(userId);
    if (existing?.revision === userInfoRevision(userId)) return existing.promise;

    // 定义Promise的resolve和reject函数，创建一个新的Promise
    const { promise, resolve, reject } = Promise.withResolvers<GetUserInfoResponse>();

    const request = { promise, resolve, reject, status: 'pending' as const, revision: userInfoRevision(userId) };
    userInfoRequests.set(userId, request);
    scheduleBatchIfNeeded();

    return promise;
}

function shouldRefreshUpdatedUsers() {
    return Date.now() - serviceConfig.value.userInfoLastUpdate >= serviceConfig.value.userInfoUpdateInterval;
}

async function writeUserInfoCache(userInfos: GetUserInfoResponse[], revisions: Map<number, number>) {
    const tx = await getTransaction(USER_INFO_STORE_NAME, 'readwrite');
    const { store } = tx;

    const currentInfos = userInfos.filter((info) => revisions.get(info.id) === userInfoRevision(info.id));
    await Promise.all(currentInfos.map((userInfo) => store.put(userInfo)));
    await tx.done;
    for (const info of currentInfos) {
        if (revisions.get(info.id) === userInfoRevision(info.id)) invalidatedUsers.delete(info.id);
    }
}

async function fetchUserInfoImmediately(userId: number) {
    const revision = userInfoRevision(userId);
    const { data } = await $axios.get(`/api/userprofile/info/${userId}`);
    const userInfo = data as GetUserInfoResponse;

    try {
        await writeUserInfoCache([userInfo], new Map([[userInfo.id, revision]]));
    } catch {
        // 忽略 IndexedDB 错误（如隐私模式）
    }

    return userInfo;
}

/**
 * 刷新已更新用户信息的异步函数
 * 该函数会检查是否需要刷新用户信息，并更新本地缓存
 * 使用IndexedDB存储用户信息，并通过API获取更新后的用户数据
 */
async function refreshUpdatedUsers() {
    if (!shouldRefreshUpdatedUsers()) return;
    if (updateCachePromise) return updateCachePromise;

    // 创建并执行刷新缓存的操作
    updateCachePromise = (async () => {
        // 初始化
        const requestTime = Date.now();
        const lastUpdate = serviceConfig.value.userInfoLastUpdate;

        // 如果是首次更新（lastUpdate为0），则清空整个存储
        if (lastUpdate === 0) {
            const tx = await getTransaction(USER_INFO_STORE_NAME, 'readwrite');
            await tx.store.clear();
            await tx.done;

            serviceConfig.value.userInfoLastUpdate = requestTime;
            return;
        }

        // 获取自上次更新以来有更新的用户ID列表，删除所有已更新的用户记录
        const { data } = await $axios.get('/api/userprofile/infoupdated', {
            params: { since: lastUpdate },
        });
        const updatedUserIds = data as number[];
        // 网络响应后再创建事务，避免等待期间事务自动提交。
        const tx = await getTransaction(USER_INFO_STORE_NAME, 'readwrite');
        const { store } = tx;
        await Promise.all(updatedUserIds.map((userId) => store.delete(userId)));
        await tx.done;

        serviceConfig.value.userInfoLastUpdate = requestTime;
    })().finally(() => {
        // 操作完成后清除Promise引用
        updateCachePromise = null;
    });

    return updateCachePromise;
}

/**
 * 批量处理待处理的用户信息请求
 * 该函数会从请求队列中获取指定数量的待处理请求，并发送批量请求获取用户信息
 * 然后将结果存储到数据库并解决相应的Promise
 */
async function processUserInfoBatch() {
    // 获取所有状态为'pending'的请求，并转换为数组
    const pendingEntries = [...userInfoRequests.entries()].filter(([, request]) => request.status === 'pending');
    // 根据配置的批量大小获取要处理的请求数量，至少为1
    const entries = pendingEntries.slice(0, Math.max(1, serviceConfig.value.userInfoBatchSize));

    // 如果没有待处理条目
    if (entries.length === 0) {
        // 如果没有待处理的请求且存在批处理定时器，则清除定时器
        if (userInfoRequests.size === 0 && batchTimer) {
            clearTimeout(batchTimer);
            batchTimer = null;
        }
        return; // 直接返回，不执行任何操作
    }

    // 将所有选中的请求状态设置为'inFlight'（正在处理）
    entries.forEach(([, request]) => {
        request.status = 'inFlight';
    });

    // 提取用户ID数组，用于批量请求
    const userIds = entries.map(([id]) => id);
    try {
        // 发送批量请求获取用户信息
        const { data } = await $axios.get('/api/userprofile/infobulk', { params: { ids: userIds.join(',') } });
        const userInfos = data as GetUserInfoResponse[];

        // 将所有用户信息存储到数据库
        const infoMap = new Map(userInfos.map((u) => [u.id, u]));
        await writeUserInfoCache(userInfos, new Map(entries.map(([id, request]) => [id, request.revision])));

        // 遍历所有请求，解决或拒绝相应的Promise
        for (const [userId, { resolve, reject }] of entries) {
            const info = infoMap.get(userId);
            // 如果找到用户信息，则解决Promise；否则拒绝
            if (info) resolve(info);
            else reject(new Error(`User ${userId} not returned by batch API`));
        }
    } catch (err) {
        // 如果发生错误，拒绝所有请求
        entries.forEach(([, { reject }]) => {
            reject(err);
        });
    } finally {
        // 清理已处理的请求
        entries.forEach(([userId, request]) => {
            if (userInfoRequests.get(userId) === request) userInfoRequests.delete(userId);
        });

        // 如果还有待处理的请求，检查是否需要安排刷新缓冲区
        if ([...userInfoRequests.values()].some((request) => request.status === 'pending')) {
            scheduleBatchIfNeeded();
        }
    }
}

export async function fetchUserInfo(userId: number, immediate = false): Promise<UserProfile> {
    const revision = userInfoRevision(userId);
    await userInfoInvalidations.get(userId);
    if (immediate) {
        const info = await fetchUserInfoImmediately(userId);
        return revision === userInfoRevision(userId) ? new UserProfile(info) : fetchUserInfo(userId, immediate);
    }

    try {
        await refreshUpdatedUsers().catch(() => undefined);
        const db = await getDatabase();
        const cached = await db.get(USER_INFO_STORE_NAME, userId) as GetUserInfoResponse | undefined;
        if (cached && !invalidatedUsers.has(userId) && revision === userInfoRevision(userId)) return new UserProfile(cached);
    } catch {
        // 忽略 IndexedDB 错误（如隐私模式）
    }
    const info = await enqueueRequest(userId);
    return revision === userInfoRevision(userId) ? new UserProfile(info) : fetchUserInfo(userId);
}

export async function fetchUserIdentifiers(userId: number): Promise<string[]> {
    const response = await $axios.get('/api/userprofile/identifier', {
        params: { user_id: userId },
    });
    return response.data as string[];
}

const userVideosPendingRequests = new Map<string, Promise<VideoAbstract[]>>();
export async function revealUserVideo(videoId: number): Promise<void> {
    await $axios.post(`/api/tournament/video/${videoId}/reveal`);
}

export function fetchUserVideos(userId: number, viewerKey = 'public', revision = 0): Promise<VideoAbstract[]> {
    const key = `${userId}:${viewerKey}:${revision}`;
    const pendingRequest = userVideosPendingRequests.get(key);

    if (pendingRequest) return pendingRequest;

    const promise = fetchVideoList('/api/userprofile/videolist', { user_id: userId }).finally(() => {
        userVideosPendingRequests.delete(key);
    });

    userVideosPendingRequests.set(key, promise);
    return promise;
}
