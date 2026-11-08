import $axios from '@/http';
import { AccountLinks, AccountLinkPlatform } from '@/utils/accountlinks';
import type { AccountLinkPlatform, AccountLinkQueueResponse, AccountLinksResponse, MSGamesImportResult, MSGamesImportSummary, MSGamesSyncResult, MSGamesVideo } from '@/utils/accountlinks';

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

export interface SaoleiSyncPreferences {
    /** 扫雷网上传录像自动同步本站 */
    syncFromSaolei: boolean;
    /** 本站上传录像自动同步扫雷网 */
    syncToSaolei: boolean;
}

export async function addAccountLink(platform: AccountLinkPlatform, identifier: string, syncPreferences?: SaoleiSyncPreferences): Promise<AccountLinkQueueResponse> {
    const { data } = await $axios.post<AccountLinkQueueResponse>('/api/accountlink/create/', {
        platform,
        identifier,
        // 仅扫雷网绑定申请携带同步偏好勾选（key 与后端 AccountLinkCreateIn 字段一致）；其余平台后端默认 True
        ...(platform === AccountLinkPlatform.Saolei && syncPreferences
            ? { sync_from_saolei: syncPreferences.syncFromSaolei, sync_to_saolei: syncPreferences.syncToSaolei }
            : {}),
    });
    return data;
}

export async function updateAccountLink(platform: AccountLinkPlatform): Promise<AccountLinkUpdateResponse> {
    const { data } = await $axios.post<AccountLinkUpdateResponse>('accountlink/update/', {
        platform,
    });
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

export async function syncMSGamesVideos(msgamesId: number): Promise<MSGamesSyncResult> {
    const { data } = await $axios.post<MSGamesSyncResult>(`/api/accountlink/msgames/${msgamesId}/sync`, undefined, { timeout: 120000 });
    return data;
}

export async function importMSGamesVideo(videoId: number): Promise<MSGamesImportResult> {
    const { data } = await $axios.post<MSGamesImportResult>(`/api/accountlink/msgames/videos/${videoId}/import`, undefined, { timeout: 120000 });
    return data;
}
