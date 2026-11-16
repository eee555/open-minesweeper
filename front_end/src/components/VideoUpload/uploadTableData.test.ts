import { describe, expect, it } from 'vitest';

import type { UploadTableRow, UploadTableStat } from './uploadTableData';
import {
    compareUploadSortValues, createUploadFilters, filterUploadTable, sliceUploadTable,
    sortUploadTable, uploadFilterFields, uploadSortFields, uploadSortValue,
} from './uploadTableData';

function stat(overrides: Partial<UploadTableStat> = {}): UploadTableStat {
    return {
        end_time: new Date('2024-01-01T00:00:00Z'),
        level: 'b',
        mode: '00',
        timems: 1000,
        bv: 10,
        bvs: 10,
        ...overrides,
    };
}

function row(hash: string, overrides: Partial<UploadTableRow> = {}): UploadTableRow {
    return { hash, status: 'pass', stat: stat(), ...overrides };
}

function hashes(rows: readonly UploadTableRow[]): string[] {
    return rows.map((entry) => entry.hash);
}

describe('VideoUpload table data', () => {
    it('exposes all filter and sort fields and starts with no active filter', () => {
        expect(uploadFilterFields).toEqual(['status', 'stat.level', 'stat.mode']);
        expect(uploadSortFields).toEqual(['stat.end_time', 'stat.timems', 'stat.bv', 'stat.bvs']);
        expect(createUploadFilters()).toEqual({ status: null, 'stat.level': null, 'stat.mode': null });
    });

    it('applies equality on each field and combines active filters', () => {
        const rows = [
            row('a', { status: 'pass', stat: stat({ level: 'b', mode: '00' }) }),
            row('b', { status: 'quota', stat: stat({ level: 'e', mode: '10' }) }),
            row('c', { status: 'pass', stat: stat({ level: 'e', mode: '00' }) }),
            row('d', { status: 'pass', stat: undefined }),
        ];
        const filters = createUploadFilters();
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['a', 'b', 'c', 'd']);
        filters.status = 'pass';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['a', 'c', 'd']);
        filters['stat.level'] = 'e';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['c']);
        filters['stat.mode'] = '00';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['c']);
        filters.status = null;
        filters['stat.level'] = null;
        filters['stat.mode'] = '10';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['b']);
        expect(hashes(rows)).toEqual(['a', 'b', 'c', 'd']);
    });

    it('treats custom levels and rows without stats as non-matching', () => {
        const rows = [
            row('custom', { stat: stat({ level: { column: 30, row: 24, mine: 226 } }) }),
            row('plain'),
        ];
        const filters = createUploadFilters();
        filters['stat.level'] = 'b';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['plain']);
        filters['stat.level'] = null;
        filters['stat.mode'] = '00';
        expect(hashes(filterUploadTable(rows, filters))).toEqual(['custom', 'plain']);
    });

    it('sorts every sortable field, keeps ties stable and pushes missing values last', () => {
        const rows = [
            row('slow', { stat: stat({ timems: 3000, bv: 30, bvs: 10, end_time: new Date('2024-03-01T00:00:00Z') }) }),
            row('missing'),
            row('fast', { stat: stat({ timems: 1000, bv: 10, bvs: 10, end_time: new Date('2024-01-01T00:00:00Z') }) }),
            row('tie', { stat: stat({ timems: 2000, bv: 20, bvs: 10, end_time: new Date('2024-02-01T00:00:00Z') }) }),
        ];
        rows[1].stat = undefined;
        expect(hashes(sortUploadTable(rows, null, 1))).toEqual(['slow', 'missing', 'fast', 'tie']);
        expect(hashes(sortUploadTable(rows, 'stat.timems', 1))).toEqual(['fast', 'tie', 'slow', 'missing']);
        expect(hashes(sortUploadTable(rows, 'stat.timems', -1))).toEqual(['slow', 'tie', 'fast', 'missing']);
        expect(hashes(sortUploadTable(rows, 'stat.bv', 1))).toEqual(['fast', 'tie', 'slow', 'missing']);
        expect(hashes(sortUploadTable(rows, 'stat.bvs', 1))).toEqual(['slow', 'fast', 'tie', 'missing']);
        expect(hashes(sortUploadTable(rows, 'stat.end_time', -1))).toEqual(['slow', 'tie', 'fast', 'missing']);
        expect(hashes(sortUploadTable(rows, 'stat.timems', 0))).toEqual(['slow', 'missing', 'fast', 'tie']);
        expect(hashes(sortUploadTable(rows, 'stat.timems', undefined))).toEqual(['slow', 'missing', 'fast', 'tie']);
        expect(hashes(rows)).toEqual(['slow', 'missing', 'fast', 'tie']);
    });

    it('treats NaN, Infinity and missing end times as missing sort values', () => {
        expect(uploadSortValue(row('nan', { stat: stat({ timems: NaN }) }), 'stat.timems')).toBeNull();
        expect(uploadSortValue(row('infinite', { stat: stat({ bvs: Infinity }) }), 'stat.bvs')).toBeNull();
        expect(uploadSortValue(row('no-date', { stat: stat({ end_time: undefined }) }), 'stat.end_time')).toBeNull();
        expect(uploadSortValue(row('no-stat', { stat: undefined }), 'stat.bv')).toBeNull();
        expect(compareUploadSortValues(null, null, -1)).toBe(0);
        expect(compareUploadSortValues(null, 1, -1)).toBe(1);
        expect(compareUploadSortValues(1, null, -1)).toBe(-1);
    });

    it('slices from an arbitrary start, truncates the tail and rejects non-positive sizes', () => {
        const rows = Array.from({ length: 27 }, (_, index) => row(String(index)));
        expect(hashes(sliceUploadTable(rows, 25, 25))).toEqual(['25', '26']);
        expect(hashes(sliceUploadTable(rows, 5, 5))).toEqual(['5', '6', '7', '8', '9']);
        expect(sliceUploadTable(rows, 3, 0)).toEqual([]);
        expect(hashes(sliceUploadTable(rows, -5, 2))).toEqual(['0', '1']);
    });
});
