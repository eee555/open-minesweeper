import { parse } from 'papaparse';

export const gscScoreFields = ['bt1st', 'bt20th', 'bt20sum', 'it1st', 'it12th', 'it12sum', 'et1st', 'et5th', 'et5sum'] as const;
export type HistoryKind = 'users' | 'anonymous';
export type HistoryScores = Record<typeof gscScoreFields[number], number>;
export type HistoryScoreRow = HistoryScores & ({ user_id: number } | { arbiter_identifier: string });
export interface HistoryCsvRecord {
    order: number;
    sourceRow: number;
    data: HistoryScoreRow;
}
export interface HistoryBatch {
    order: number;
    records: HistoryCsvRecord[];
}

export function historyCsvHeaders(kind: HistoryKind): string[] {
    return ['order', kind === 'users' ? 'user_id' : 'arbiter_identifier', ...gscScoreFields];
}

function integer(value: string, row: number, field: string, minimum = 0): number {
    const result = Number(value);
    if (!(/^\d+$/).test(value) || !Number.isSafeInteger(result) || result < minimum || result > 4294967295) throw new Error(`Row ${row}: invalid ${field}`);
    return result;
}

export function parseHistoryCsv(text: string, kind: HistoryKind): HistoryCsvRecord[] {
    if (new TextEncoder().encode(text).byteLength > 10 * 1024 * 1024) throw new Error('CSV exceeds 10 MiB');
    const parsed = parse<string[]>(text.replace(/^\uFEFF/, ''), { delimiter: ',', dynamicTyping: false });
    if (parsed.errors.length) throw new Error(parsed.errors[0].message);
    const headers = parsed.data[0]?.map((cell) => cell.trim()) ?? [];
    if (headers.length !== new Set(headers).size || historyCsvHeaders(kind).some((field) => !headers.includes(field))) throw new Error('Missing or duplicate CSV headers');
    const records: HistoryCsvRecord[] = [];
    const seen = new Set<string>();
    let sourceRow = 1;
    for (const cells of parsed.data) {
        const row = sourceRow;
        sourceRow += 1 + cells.reduce((count, cell) => count + (cell.match(/\r\n|\r|\n/g)?.length ?? 0), 0);
        if (row === 1 || cells.every((cell) => cell.trim() === '')) continue;
        if (cells.length !== headers.length) throw new Error(`Row ${row}: invalid column count`);
        const values = Object.fromEntries(headers.map((header, index) => [header, cells[index]]));
        const order = integer(values.order.trim(), row, 'order', 1);
        const scores = Object.fromEntries(gscScoreFields.map((field) => [field, integer(values[field].trim(), row, field)])) as HistoryScores;
        let identity: string | number;
        let data: HistoryScoreRow;
        if (kind === 'users') {
            identity = integer(values.user_id.trim(), row, 'user_id', 1);
            data = { ...scores, user_id: identity };
        } else {
            identity = values.arbiter_identifier;
            if (!identity.trim() || Array.from(identity).length > 80) throw new Error(`Row ${row}: invalid arbiter_identifier`);
            data = { ...scores, arbiter_identifier: identity };
        }
        const key = JSON.stringify([order, identity]);
        if (seen.has(key)) throw new Error(`Row ${row}: duplicate participant`);
        seen.add(key);
        records.push({ order, sourceRow: row, data });
    }
    if (!records.length) throw new Error('CSV has no records');
    return records;
}

export function splitHistoryBatches(records: HistoryCsvRecord[]): HistoryBatch[] {
    const groups = new Map<number, HistoryCsvRecord[]>();
    for (const record of records) {
        const group = groups.get(record.order) ?? [];
        group.push(record);
        groups.set(record.order, group);
    }
    return [...groups].flatMap(([order, group]) => {
        const batches: HistoryBatch[] = [];
        for (let i = 0; i < group.length; i += 10) batches.push({ order, records: group.slice(i, i + 10) });
        return batches;
    });
}

export { assignHistoryUploadTimes } from '@/utils/historyUploadTimes';
export type { HistoryReplayTime } from '@/utils/historyUploadTimes';
