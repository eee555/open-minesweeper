import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { assignHistoryUploadTimes, gscScoreFields, historyCsvHeaders, parseHistoryCsv, splitHistoryBatches } from './history';
import type { HistoryKind } from './history';

function csv(kind: HistoryKind, identities: (string | number)[], order = 19) {
    return [historyCsvHeaders(kind).join(','), ...identities.map((identity) => [order, identity, ...gscScoreFields.map(() => 1000)].join(','))].join('\n');
}

describe('GSC history CSV', () => {
    it.each(['users', 'anonymous'] as const)('reads all ten %s fixture rows with headers', (kind) => {
        const fixture = kind === 'users' ? 'type2.csv' : 'type3.csv';
        const text = readFileSync(new URL(`../../../cypress/fixtures/gsc/${fixture}`, import.meta.url), 'utf8');
        const records = parseHistoryCsv(text, kind);
        expect(records).toHaveLength(10);
        expect(records[0]).toMatchObject({ order: 19, sourceRow: 2 });
        expect(records[0].data).toMatchObject(kind === 'users' ? { user_id: 101, bt1st: 1480 } : { arbiter_identifier: 'kiraa96G09511', bt1st: 1470 });
    });

    it('maps reordered headers and preserves quoted identifiers and source lines', () => {
        const header = [...historyCsvHeaders('anonymous')].reverse();
        const values = header.map((key) => (key === 'order' ? '19' : key === 'arbiter_identifier' ? '" 中文,Name\n G09511 "' : '1234'));
        const records = parseHistoryCsv(`\uFEFF${header.join(',')}\r\n${values.join(',')}\r\n\r\n${values.join(',').replace('中文', 'Other')}`, 'anonymous');
        expect(records[0].data).toMatchObject({ arbiter_identifier: ' 中文,Name\n G09511 ', bt1st: 1234 });
        expect(records[1].sourceRow).toBe(5);
    });

    it('rejects headerless, missing/duplicate columns, malformed values and duplicate identities before submitting', () => {
        const valid = csv('users', [101]);
        for (const text of [valid.split('\n')[1], valid.replace('bt1st,', ''), valid.replace('bt1st', 'user_id'), valid.replace('1000', '1.5'), valid.replace('19,101', '19,0'), valid.replace('1000', '-1'), csv('users', [101, 101]), `${valid},extra`]) {
            expect(() => parseHistoryCsv(text, 'users')).toThrow();
        }
        expect(() => parseHistoryCsv(csv('anonymous', ['']), 'anonymous')).toThrow();
    });

    it('preserves a stable CSV error code, message and source location', () => {
        expect(() => parseHistoryCsv(csv('users', [0]), 'users')).toThrow(expect.objectContaining({
            code: 'invalidField', message: 'Row 2: invalid user_id', params: { row: 2, field: 'user_id' },
        }));
    });

    it('groups by order, preserves source rows and splits into sequential batches of at most ten', () => {
        const rows = csv('users', Array.from({ length: 21 }, (_, i) => 101 + i));
        const [, otherOrder] = csv('users', [101], 20).split('\n');
        const batches = splitHistoryBatches(parseHistoryCsv(`${rows}\n${otherOrder}`, 'users'));
        expect(batches.map((batch) => [batch.order, batch.records.length])).toEqual([[19, 10], [19, 10], [19, 1], [20, 1]]);
        expect(batches[2].records[0].sourceRow).toBe(22);
    });
});

describe('GSC history replay timestamps', () => {
    const anchor = new Date('2026-01-01T00:00:00.000Z');
    const replay = (id: number, seconds: number, end = id) => ({ id, endTime: new Date(end * 1000), timems: seconds * 1000 });

    it('sorts all levels by end time and works backwards using the following replay duration', () => {
        const files = [replay(3, 30), replay(1, 10), replay(2, 20)];
        const sorted = assignHistoryUploadTimes(files, anchor);
        expect(sorted.map((file) => file.id)).toEqual([1, 2, 3]);
        expect(sorted.map((file) => anchor.getTime() - file.uploadTime.getTime())).toEqual([50000, 30000, 0]);
        expect(files.map((file) => file.id)).toEqual([3, 1, 2]);
    });

    it('preserves equal-time file order and supports single files and filtered selections', () => {
        const sorted = assignHistoryUploadTimes([replay(2, 20, 1), replay(1, 10, 1)], anchor);
        expect(sorted.map((file) => file.id)).toEqual([2, 1]);
        expect(sorted[0].uploadTime.getTime()).toBe(anchor.getTime() - 10000);
        expect(assignHistoryUploadTimes([replay(1, 10)], anchor)[0].uploadTime).toEqual(anchor);
        expect(assignHistoryUploadTimes([replay(1, 10), replay(3, 30)], anchor)[0].uploadTime.getTime()).toBe(anchor.getTime() - 30000);
    });

    it('rejects invalid anchors, missing/invalid end times and nonpositive duration', () => {
        expect(() => assignHistoryUploadTimes([replay(1, 10)], new Date(NaN))).toThrow(expect.objectContaining({
            code: 'uploadTime', message: 'Invalid upload time',
        }));
        for (const file of [replay(1, 0), replay(1, -1), { ...replay(1, 1), endTime: new Date(NaN) }, { ...replay(1, 1), timems: 1.5 }]) {
            expect(() => assignHistoryUploadTimes([file], anchor)).toThrow();
        }
    });
});
