export interface UploadTableStat {
    end_time?: Date;
    level: string | object;
    mode: string;
    timems: number;
    bv: number;
    bvs: number;
}

export interface UploadTableRow {
    hash: string;
    status: string;
    stat?: UploadTableStat;
}

export const uploadFilterFields = ['status', 'stat.level', 'stat.mode'] as const;
export type UploadFilterField = typeof uploadFilterFields[number];
export type UploadFilters = Record<UploadFilterField, string | null>;

export function createUploadFilters(): UploadFilters {
    return { status: null, 'stat.level': null, 'stat.mode': null };
}

function fieldValue(row: UploadTableRow, field: UploadFilterField): string | null {
    if (field === 'status') return row.status;
    const { stat } = row;
    if (stat === undefined) return null;
    if (field === 'stat.level') return typeof stat.level === 'string' ? stat.level : null;
    return stat.mode;
}

export function filterUploadTable<T extends UploadTableRow>(rows: readonly T[], filters: UploadFilters): T[] {
    const active = uploadFilterFields.filter((field) => filters[field] !== null);
    if (active.length === 0) return [...rows];
    return rows.filter((row) => active.every((field) => fieldValue(row, field) === filters[field]));
}

export const uploadSortFields = ['stat.end_time', 'stat.timems', 'stat.bv', 'stat.bvs'] as const;
export type UploadSortField = typeof uploadSortFields[number];

export function uploadSortValue(row: UploadTableRow, field: UploadSortField): number | null {
    const { stat } = row;
    if (stat === undefined) return null;
    let value: number;
    switch (field) {
        case 'stat.end_time': value = stat.end_time?.getTime() ?? NaN; break;
        case 'stat.timems': value = stat.timems; break;
        case 'stat.bv': value = stat.bv; break;
        case 'stat.bvs': value = stat.bvs; break;
    }
    return Number.isFinite(value) ? value : null;
}

export function compareUploadSortValues(a: number | null, b: number | null, order: number): number {
    if (a === null || b === null) {
        if (a === b) return 0;
        return a === null ? 1 : -1;
    }
    return Math.sign(a - b) * (order < 0 ? -1 : 1);
}

export function sortUploadTable<T extends UploadTableRow>(rows: readonly T[], field: UploadSortField | null, order: number | undefined): T[] {
    const result = [...rows];
    if (field === null || order === undefined || order === 0) return result;
    const decorated = result.map((row, index) => ({ row, index, value: uploadSortValue(row, field) }));
    decorated.sort((a, b) => compareUploadSortValues(a.value, b.value, order) || a.index - b.index);
    return decorated.map((entry) => entry.row);
}

export function sliceUploadTable<T extends UploadTableRow>(rows: readonly T[], first: number, size: number): T[] {
    if (!Number.isFinite(size) || size <= 0) return [];
    const start = Number.isFinite(first) ? Math.max(0, Math.floor(first)) : 0;
    return rows.slice(start, start + Math.floor(size));
}
