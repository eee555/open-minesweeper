import type { SaoleiVideo } from '@/utils/accountlinks';
import type { MS_Level } from '@/utils/ms_const';

export const importStatuses = ['imported', 'pending', 'rejected', 'unsupported'] as const;
export type ImportStatus = typeof importStatuses[number];
export type SaoleiTableVideo = SaoleiVideo & { import_status: ImportStatus };

export const sortFields = ['remote_id', 'upload_time', 'timems', 'bv', 'software'] as const;
export type SortField = typeof sortFields[number];

export interface ImportQueueFilters {
    level: MS_Level | null;
    import_status: ImportStatus | null;
}

export function createImportQueueFilters(): ImportQueueFilters {
    return { level: null, import_status: null };
}

export function importStatusOf(video: SaoleiVideo, canImport: boolean): ImportStatus {
    if (video.import_video !== null) return 'imported';
    if (video.import_rejected) return 'rejected';
    return canImport ? 'pending' : 'unsupported';
}

export function filterImportQueue(rows: readonly SaoleiTableVideo[], filters: ImportQueueFilters): SaoleiTableVideo[] {
    return rows.filter((row) => (filters.level === null || row.level === filters.level)
        && (filters.import_status === null || row.import_status === filters.import_status));
}

export type SortValue = number | string | null | undefined;

const sortValueGetters: Record<SortField, (row: SaoleiTableVideo) => SortValue> = {
    remote_id: (row) => row.remote_id,
    upload_time: (row) => Date.parse(row.upload_time),
    timems: (row) => row.timems,
    bv: (row) => row.bv,
    software: (row) => row.software,
};

export function sortValue(row: SaoleiTableVideo, field: SortField): SortValue {
    return sortValueGetters[field](row);
}

export function isMissingSortValue(value: SortValue): boolean {
    if (value === undefined || value === null) return true;
    return typeof value === 'number' && !Number.isFinite(value);
}

function compareDefinedValues(a: SortValue, b: SortValue): number {
    if (typeof a === 'number' && typeof b === 'number') return Math.sign(a - b);
    return String(a).localeCompare(String(b));
}

export function compareSortValues(a: SortValue, b: SortValue, order: number): number {
    const aMissing = isMissingSortValue(a);
    const bMissing = isMissingSortValue(b);
    if (aMissing !== bMissing) return aMissing ? 1 : -1;
    if (aMissing) return 0;
    return compareDefinedValues(a, b) * (order < 0 ? -1 : 1);
}

export function sortImportQueue(rows: readonly SaoleiTableVideo[], field: SortField, order: number | undefined): SaoleiTableVideo[] {
    const result = [...rows];
    if (order === undefined || order === 0) return result;
    const decorated = result.map((row, index) => ({ row, index, value: sortValue(row, field) }));
    decorated.sort((a, b) => compareSortValues(a.value, b.value, order) || a.index - b.index);
    return decorated.map((entry) => entry.row);
}

export function sliceImportQueue(rows: readonly SaoleiTableVideo[], first: number, size: number): SaoleiTableVideo[] {
    if (!Number.isFinite(size) || size <= 0) return [];
    const start = Number.isFinite(first) ? Math.max(0, Math.floor(first)) : 0;
    return rows.slice(start, start + Math.floor(size));
}
