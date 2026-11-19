import { promiseTimeout } from '@vueuse/core';

import $axios from '@/http';
import { AccountLinks } from '@/utils/accountlinks';
import type { AccountLinkPlatform, AccountLinkQueueResponse, AccountLinksResponse, MSGamesImportResult, MSGamesImportSummary, MSGamesSyncResult, MSGamesVideo } from '@/utils/accountlinks';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';

type AccountLinkUpdateErrorMessageCategory = 'cooldown' | 'empty' | 'indexerror' | 'pageempty' | 'requestexception' | 'timeout' | 'unknown';

const accountLinkUpdateErrorCategories = new Set<string>([
    'cooldown',
    'empty',
    'indexerror',
    'pageempty',
    'requestexception',
    'timeout',
]);

interface AccountLinkUpdateSuccessResponse {
    type: 'success';
}

interface AccountLinkUpdateErrorResponse {
    type: 'error';
    object?: string;
    category?: string;
}

export type AccountLinkUpdateResponse = AccountLinkUpdateSuccessResponse | AccountLinkUpdateErrorResponse;

export async function fetchAccountLinks(userId: number): Promise<AccountLinks> {
    const { data } = await $axios.get<AccountLinksResponse>(`/api/accountlink/${userId}`);
    return new AccountLinks(data);
}

export async function addAccountLink(platform: AccountLinkPlatform, identifier: string): Promise<AccountLinkQueueResponse> {
    const { data } = await $axios.post<AccountLinkQueueResponse>('/api/accountlink/create/', {
        platform,
        identifier,
    });
    return data;
}

// 管理员代纪念账号刷新资料时指定目标用户；不指定则由后端按登录用户处理。
export async function updateAccountLink(platform: AccountLinkPlatform, targetUserId?: number): Promise<AccountLinkUpdateResponse> {
    const body: Record<string, string | number> = { platform };
    if (targetUserId !== undefined) body.user_id = targetUserId;
    const { data } = await $axios.post<AccountLinkUpdateResponse>('/api/accountlink/update/', body);
    return data;
}

export function getAccountLinkUpdateErrorMessageKey(category?: string): string {
    return `accountlink.updateError.${getAccountLinkUpdateErrorMessageCategory(category)}`;
}

function getAccountLinkUpdateErrorMessageCategory(category?: string): AccountLinkUpdateErrorMessageCategory {
    if (category !== undefined && accountLinkUpdateErrorCategories.has(category)) {
        return category as AccountLinkUpdateErrorMessageCategory;
    }
    return 'unknown';
}

export async function fetchMSGamesVideos(msgamesId: number): Promise<MSGamesVideo[]> {
    const { data } = await $axios.get<MSGamesVideo[]>('/api/accountlink/msgames/videos', {
        params: { msgames_id: msgamesId },
    });
    return data;
}

export async function fetchMSGamesImportSummary(msgamesId: number): Promise<MSGamesImportSummary> {
    const { data } = await $axios.get<MSGamesImportSummary>('/api/accountlink/msgames/summary', {
        params: { msgames_id: msgamesId },
    });
    return data;
}

interface MSGamesTask {
    id: string;
    status: DjangoTaskResultStatus;
    return_value: MSGamesSyncResult | { type: 'error'; object: string; category: string } | null;
}

export class MSGamesTaskError extends Error {
    public constructor(object: string, category: string) {
        super(`${object}/${category}`);
    }
}

async function waitMSGamesTask(task: MSGamesTask, signal?: AbortSignal): Promise<MSGamesSyncResult> {
    while (task.status === 'READY' || task.status === 'RUNNING') {
        await promiseTimeout(2000);
        signal?.throwIfAborted();
        const { data } = await $axios.get<MSGamesTask>(`/api/accountlink/msgames/tasks/${task.id}`, { signal });
        task = data;
    }
    if (task.status === 'FAILED') throw new MSGamesTaskError('import', 'task_failed');
    if (task.status !== 'SUCCESSFUL' || task.return_value === null) throw new Error('Invalid MSGames task result');
    if ('type' in task.return_value) throw new MSGamesTaskError(task.return_value.object, task.return_value.category);
    return task.return_value;
}

export async function syncMSGamesVideos(msgamesId: number, signal?: AbortSignal): Promise<MSGamesSyncResult> {
    const { data } = await $axios.post<MSGamesTask>(`/api/accountlink/msgames/${msgamesId}/sync`, undefined, { signal });
    return waitMSGamesTask(data, signal);
}

export async function importMSGamesVideo(videoId: number, signal?: AbortSignal): Promise<MSGamesImportResult> {
    const { data } = await $axios.post<MSGamesImportResult>(`/api/accountlink/msgames/videos/${videoId}/import`, undefined, { signal, timeout: 5000 });
    return data;
}
