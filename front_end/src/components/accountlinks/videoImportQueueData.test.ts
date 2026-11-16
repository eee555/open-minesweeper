import { describe, expect, it } from 'vitest';

import type { ImportQueueFilters, SaoleiTableVideo } from './videoImportQueueData';
import {
    compareSortValues, createImportQueueFilters, filterImportQueue, importStatusOf,
    isMissingSortValue, sliceImportQueue, sortFields, sortImportQueue, sortValue,
} from './videoImportQueueData';

function makeRow(overrides: Partial<SaoleiTableVideo> = {}): SaoleiTableVideo {
    return {
        id: 1,
        remote_id: 1001,
        level: 'b',
        timems: 1000,
        bv: 10,
        nf: false,
        software: '元扫雷',
        status: 0,
        upload_time: '2026-01-01T00:00:00Z',
        import_video: null,
        import_rejected: false,
        import_status: 'pending',
        ...overrides,
    };
}

function ids(rows: readonly SaoleiTableVideo[]): number[] {
    return rows.map((row) => row.id);
}

describe('import queue filters', () => {
    it('starts with both filters cleared', () => {
        expect(createImportQueueFilters()).toEqual({ level: null, import_status: null });
    });

    it('derives the four import states', () => {
        const pending = makeRow();
        expect(importStatusOf(pending, true)).toBe('pending');
        expect(importStatusOf(pending, false)).toBe('unsupported');
        expect(importStatusOf(makeRow({ import_video: 42 }), false)).toBe('imported');
        expect(importStatusOf(makeRow({ import_rejected: true }), true)).toBe('rejected');
    });

    it('matches level and import status by equality without mutating the input', () => {
        const rows = [
            makeRow({ id: 1, level: 'b' }),
            makeRow({ id: 2, level: 'e' }),
            makeRow({ id: 3, level: 'i', import_status: 'rejected' }),
        ];
        const filters: ImportQueueFilters = { level: 'e', import_status: null };
        expect(ids(filterImportQueue(rows, filters))).toEqual([2]);
        filters.level = null;
        filters.import_status = 'rejected';
        expect(ids(filterImportQueue(rows, filters))).toEqual([3]);
        filters.level = 'e';
        expect(filterImportQueue(rows, filters)).toEqual([]);
        expect(rows).toHaveLength(3);
    });
});

describe('import queue sorting', () => {
    it('exposes exactly the five sortable fields', () => {
        expect(sortFields).toEqual(['remote_id', 'upload_time', 'timems', 'bv', 'software']);
    });

    it('sorts dates and numbers in both directions', () => {
        const early = makeRow({ id: 1, upload_time: '2026-01-01T00:00:00Z', bv: 3 });
        const late = makeRow({ id: 2, upload_time: '2026-03-01T00:00:00Z', bv: 1 });
        expect(ids(sortImportQueue([early, late], 'upload_time', -1))).toEqual([2, 1]);
        expect(ids(sortImportQueue([early, late], 'upload_time', 1))).toEqual([1, 2]);
        expect(ids(sortImportQueue([early, late], 'bv', 1))).toEqual([2, 1]);
        expect(ids(sortImportQueue([early, late], 'bv', -1))).toEqual([1, 2]);
        expect(sortValue(early, 'software')).toBe('元扫雷');
    });

    it('always places missing and invalid values last in both directions', () => {
        const normal = makeRow({ id: 1, upload_time: '2026-01-01T00:00:00Z', timems: 1000 });
        const invalidDate = makeRow({ id: 2, upload_time: 'invalid' });
        const nanTime = makeRow({ id: 3, timems: Number.NaN });
        expect(isMissingSortValue(Date.parse(invalidDate.upload_time))).toBe(true);
        expect(ids(sortImportQueue([normal, invalidDate], 'upload_time', 1))).toEqual([1, 2]);
        expect(ids(sortImportQueue([normal, invalidDate], 'upload_time', -1))).toEqual([1, 2]);
        expect(ids(sortImportQueue([nanTime, normal], 'timems', 1))).toEqual([1, 3]);
        expect(ids(sortImportQueue([nanTime, normal], 'timems', -1))).toEqual([1, 3]);
        expect(compareSortValues(Number.NaN, 5, 1)).toBe(1);
        expect(compareSortValues(5, Number.NaN, -1)).toBe(-1);
    });

    it('keeps equal values in input order and skips sorting for a cleared order', () => {
        const rows = [makeRow({ id: 1 }), makeRow({ id: 2 }), makeRow({ id: 3 })];
        expect(ids(sortImportQueue(rows, 'bv', 1))).toEqual([1, 2, 3]);
        expect(ids(sortImportQueue(rows, 'bv', undefined))).toEqual([1, 2, 3]);
        expect(ids(sortImportQueue(rows, 'bv', 0))).toEqual([1, 2, 3]);
        expect(rows.map((row) => row.id)).toEqual([1, 2, 3]);
    });
});

describe('import queue slicing', () => {
    it('connects the processed rows with an arbitrary start index', () => {
        const rows = Array.from({ length: 40 }, (_, index) => makeRow({ id: index + 1 }));
        expect(ids(sliceImportQueue(rows, 13, 10))).toEqual(Array.from({ length: 10 }, (_, index) => index + 14));
        expect(ids(sliceImportQueue(rows, 37, 10))).toEqual([38, 39, 40]);
        expect(sliceImportQueue(rows, 0, 0)).toEqual([]);
        expect(rows).toHaveLength(40);
    });
});
