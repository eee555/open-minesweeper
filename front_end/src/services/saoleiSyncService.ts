import { isAxiosError } from 'axios';

import $axios from '@/http';
import type { AccountSaoleiResponse, SaoleiImportSummary, SaoleiVideo } from '@/utils/accountlinks';

const root = '/api/accountlink/saolei';
const requestOptions = { timeout: 120000, headers: { 'Content-Type': 'application/json' } };
export const supportedSaoleiSoftware = new Set(['Clone', 'Vienna', 'Arbiter', '元扫雷']);
export const canImportSaoleiVideo = (video: SaoleiVideo): boolean => video.import_video === null && !video.import_rejected && supportedSaoleiSoftware.has(video.software);

export async function fetchSaoleiSummary(id: number): Promise<SaoleiImportSummary> {
    return (await $axios.get<SaoleiImportSummary>(`${root}/${id}/summary`)).data;
}

export async function fetchSaoleiVideoPage(id: number, after = 0, pending = false): Promise<{ items: SaoleiVideo[]; next_after: number | null }> {
    return (await $axios.get<{ items: SaoleiVideo[]; next_after: number | null }>(`${root}/${id}/videos`, { params: { after, pending } })).data;
}

export async function setSaoleiAutoSync(id: number, enabled: boolean): Promise<AccountSaoleiResponse> {
    return (await $axios.post<AccountSaoleiResponse>(`${root}/${id}/settings`, { auto_sync: enabled }, requestOptions)).data;
}

export async function refreshSaoleiProfile(id: number): Promise<AccountSaoleiResponse> {
    return (await $axios.post<AccountSaoleiResponse>(`${root}/${id}/profile`, undefined, requestOptions)).data;
}

export async function importSaoleiVideo(id: number): Promise<{ status: 'imported' | 'existing' | 'skipped'; import_video: number | null }> {
    return (await $axios.post<{ status: 'imported' | 'existing' | 'skipped'; import_video: number | null }>(`${root}/videos/${id}/import`, undefined, requestOptions)).data;
}

export interface SaoleiSyncProgress {
    stage: 'catalogue' | 'videos';
    pages: number;
    completed: number;
    failed: number;
}

export async function synchronizeSaolei(id: number, full: boolean, cancelled: () => boolean, progress: (value: SaoleiSyncProgress) => void, failure: (id: number, error: unknown) => void): Promise<void> {
    const report: SaoleiSyncProgress = { stage: 'catalogue', pages: 0, completed: 0, failed: 0 };
    progress({ ...report });
    const { data: start } = await $axios.post<{ cursor: number; upper_bound: number }>(`${root}/${id}/sync/start`, { full }, requestOptions);
    let { cursor } = start;
    // Even an empty catalogue needs one page call to record successful completion.
    while (!cancelled()) {
        const { data } = await $axios.post<{ cursor: number; has_more: boolean }>(`${root}/${id}/sync/page`, { cursor, upper_bound: start.upper_bound }, requestOptions);
        if (cancelled()) return;
        report.pages++;
        progress({ ...report });
        if (!data.has_more) break;
        if (data.cursor <= cursor) throw new Error('Saolei catalogue cursor did not advance');
        ({ cursor } = data);
    }
    report.stage = 'videos';
    let after = 0;
    while (!cancelled()) {
        const page = await fetchSaoleiVideoPage(id, after, true);
        if (cancelled()) return;
        for (const video of page.items) {
            if (cancelled()) return;
            if (!canImportSaoleiVideo(video)) continue;
            try {
                await importSaoleiVideo(video.id);
            } catch (error) {
                if (cancelled()) return;
                if (!isAxiosError(error) || ![400, 409].includes(error.response?.status ?? 0)) throw error;
                report.failed++;
                failure(video.id, error);
            }
            if (cancelled()) return;
            report.completed++;
            progress({ ...report });
        }
        if (page.next_after === null) break;
        if (page.next_after <= after) throw new Error('Saolei local catalogue cursor did not advance');
        after = page.next_after;
    }
}
