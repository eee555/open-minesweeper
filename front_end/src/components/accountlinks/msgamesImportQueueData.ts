import type { MSGamesVideo } from '@/utils/accountlinks';

export const msgamesImportStatuses = ['pending', 'importing', 'imported', 'failed', 'unsupported'] as const;
export type MSGamesImportStatus = typeof msgamesImportStatuses[number];
export type MSGamesTableVideo = MSGamesVideo & { import_status: MSGamesImportStatus };

export interface MSGamesImportQueueFilters {
    category: string;
    import_status: MSGamesImportStatus | null;
}

export function createMSGamesImportQueueFilters(): MSGamesImportQueueFilters {
    return { category: '', import_status: null };
}

export function msgamesImportStatusOf(video: MSGamesVideo, canImport: boolean, importingId: number | undefined, failures: Readonly<Record<number, string>>): MSGamesImportStatus {
    if (video.import_video !== null) return 'imported';
    if (!canImport) return 'unsupported';
    if (importingId === video.id) return 'importing';
    if ((failures[video.id] ?? '') !== '') return 'failed';
    return 'pending';
}

export function filterMSGamesImportQueue(rows: readonly MSGamesTableVideo[], filters: MSGamesImportQueueFilters): MSGamesTableVideo[] {
    const category = filters.category.toLowerCase();
    return rows.filter((row) => (category === '' || row.category.toLowerCase().includes(category))
        && (filters.import_status === null || row.import_status === filters.import_status));
}

export function msgamesSortValue(row: MSGamesTableVideo): number | null {
    if (row.upload_date === null) return null;
    const parsed = Date.parse(row.upload_date);
    return Number.isFinite(parsed) ? parsed : null;
}

export function compareMSGamesSortValues(a: number | null, b: number | null, order: number): number {
    if (a === null || b === null) {
        if (a === null && b === null) return 0;
        return a === null ? 1 : -1;
    }
    return Math.sign(a - b) * (order < 0 ? -1 : 1);
}

export function sortMSGamesImportQueue(rows: readonly MSGamesTableVideo[], order: number | undefined): MSGamesTableVideo[] {
    const result = [...rows];
    if (order === undefined || order === 0) return result;
    const decorated = result.map((row, index) => ({ row, index, value: msgamesSortValue(row) }));
    decorated.sort((a, b) => compareMSGamesSortValues(a.value, b.value, order) || a.index - b.index);
    return decorated.map((entry) => entry.row);
}

export function sliceMSGamesImportQueue(rows: readonly MSGamesTableVideo[], first: number, size: number): MSGamesTableVideo[] {
    if (!Number.isFinite(size) || size <= 0) return [];
    const start = Number.isFinite(first) ? Math.max(0, Math.floor(first)) : 0;
    return rows.slice(start, start + Math.floor(size));
}
