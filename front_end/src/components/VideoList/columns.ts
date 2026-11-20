import { toDisplayString } from 'vue';

import i18n from '@/i18n';
import { toDate, toISODateTimeString } from '@/utils/datetime';
import { formatBytes } from '@/utils/strings';
import { utc_to_local_format } from '@/utils/system/tools';
import type { CompiledVideoExpression, VideoExpressionResult } from '@/utils/videoExpression';
import { compileVideoExpression, evaluateVideoExpression } from '@/utils/videoExpression';

export const fixedColumnTypes = ['state', 'software', 'level', 'mode', 'player'] as const;
export type FixedColumnType = typeof fixedColumnTypes[number];
export type DataColumnType = 'data' | `data.${number}f`;
export type ExpressionColumnType = DataColumnType | 'date' | 'bool' | 'bytes';
export type VideoColumn = { type: FixedColumnType } | { type: ExpressionColumnType; key: string; expr: string };
export type VideoDescriptionItem = VideoColumn & { width: 1 | 2 | 3 };
export type VideoColumnScope = 'fixed-player' | 'mixed-players';

export function isFixedColumn(column: VideoColumn): column is { type: FixedColumnType } {
    return isFixedColumnType(column.type);
}

export function isFixedColumnType(type: string): type is FixedColumnType {
    return (fixedColumnTypes as readonly string[]).includes(type);
}

export function dataPrecision(type: string): number | undefined {
    const match = (/^data\.(0|[1-9]\d*)f$/u).exec(type);
    const digits = match === null ? NaN : Number(match[1]);
    return Number.isInteger(digits) && digits <= 100 ? digits : undefined;
}

export function isExpressionColumnType(type: string): type is ExpressionColumnType {
    return type === 'data' || type === 'date' || type === 'bool' || type === 'bytes' || dataPrecision(type) !== undefined;
}

export function columnKey(column: VideoColumn): string {
    if (isFixedColumn(column)) return column.type;
    return `${column.type.startsWith('data') ? 'data' : column.type}:${column.key}`;
}

export function videoColumnLabel(column: VideoColumn): string {
    return isFixedColumn(column) ? videoFieldLabel(column.type) : column.key;
}

export function videoFieldLabel(field: string): string {
    const key = `prop.${field}`;
    const translated = i18n.global.t(key);
    return translated === key ? field : translated;
}

export function defaultVideoSortField(columns: readonly VideoColumn[]): string {
    const column = columns.find((item) => item.type === 'date' && item.expr === 'upload_time');
    return column === undefined ? '' : columnKey(column);
}

export function isVideoColumns(value: unknown, description = false): value is VideoColumn[] {
    if (!Array.isArray(value)) return false;
    const keys = new Set<string>();
    for (const item of value as unknown[]) {
        if (typeof item !== 'object' || item === null || !('type' in item) || typeof item.type !== 'string') return false;
        let identity: string;
        if (isFixedColumnType(item.type)) identity = `fixed:${item.type}`;
        else {
            if (!isExpressionColumnType(item.type) || !('key' in item) || typeof item.key !== 'string' || item.key.trim() === '' || !('expr' in item) || typeof item.expr !== 'string') return false;
            identity = `expression:${item.key}`;
        }
        if (keys.has(identity)) return false;
        keys.add(identity);
        if (description && (!('width' in item) || typeof item.width !== 'number' || ![1, 2, 3].includes(item.width))) return false;
    }
    return true;
}

export interface PreparedVideoColumn {
    column: VideoColumn;
    id: string;
    compiled?: CompiledVideoExpression;
}

export function prepareVideoColumn(column: VideoColumn): PreparedVideoColumn {
    return { column, id: columnKey(column), compiled: isFixedColumn(column) ? undefined : compileVideoExpression(column.expr) };
}

export interface VideoColumnResult {
    text: string;
    sortValue: number;
    bool?: boolean;
    error: string;
}

export function formatVideoColumnResult(column: VideoColumn, result: VideoExpressionResult, description = false): VideoColumnResult {
    const invalid = { text: 'NaN', sortValue: NaN, error: result.error };
    if (description && result.missing) return { text: '—', sortValue: NaN, error: '' };
    if (result.error !== '') return invalid;
    const { value } = result;
    if (column.type === 'bool') return typeof value === 'boolean' ? { text: String(value), sortValue: NaN, bool: value, error: '' } : invalid;
    if (column.type === 'date') {
        if (!(typeof value === 'number' || typeof value === 'string' || value instanceof Date)) return invalid;
        const date = toDate(value);
        if (date === undefined || !Number.isFinite(date.getTime())) return invalid;
        return { text: description ? toISODateTimeString(date) : utc_to_local_format(date), sortValue: date.getTime(), error: '' };
    }
    const digits = dataPrecision(column.type);
    if (description && column.type === 'data' && typeof value !== 'function') return { text: toDisplayString(value), sortValue: typeof value === 'number' ? value : NaN, error: '' };
    if (typeof value !== 'number') return invalid;
    if (column.type === 'bytes') {
        if (!Number.isFinite(value) || value < 0) return invalid;
        return { text: formatBytes(value), sortValue: value, error: '' };
    }
    return { text: digits === undefined ? String(value) : value.toFixed(digits), sortValue: value, error: '' };
}

export function evaluateVideoColumn(prepared: PreparedVideoColumn, context: Parameters<typeof evaluateVideoExpression>[1], description = false): VideoColumnResult {
    if (prepared.compiled === undefined) return { text: '', sortValue: NaN, error: '' };
    return formatVideoColumnResult(prepared.column, evaluateVideoExpression(prepared.compiled, context), description);
}
