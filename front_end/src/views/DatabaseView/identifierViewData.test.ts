import { describe, expect, it } from 'vitest';

import type { IdentifierResult, IdentifierTableRow } from './identifierViewData';
import {
    compareIdentifierSortValues, filterIdentifiersByOwner, identifierSortFields, identifierSortValue,
    sliceIdentifiers, sortIdentifiers, toIdentifierTableRow,
} from './identifierViewData';

function makeRow(overrides: Partial<IdentifierResult> = {}): IdentifierTableRow {
    return toIdentifierTableRow({
        identifier: 'Alpha01',
        user_id: 42,
        safe: true,
        ...overrides,
    });
}

function identifiers(rows: readonly IdentifierTableRow[]): string[] {
    return rows.map((row) => row.identifier);
}

describe('Identifier view data', () => {
    it('derives owner keys and exposes both sortable fields', () => {
        expect(identifierSortFields).toEqual(['identifier', 'safe']);
        expect(toIdentifierTableRow({ identifier: 'a', user_id: 7, safe: false })).toEqual({ identifier: 'a', user_id: 7, safe: false, ownerKey: 7 });
        expect(toIdentifierTableRow({ identifier: 'b', user_id: null }).ownerKey).toBe(0);
    });

    it('keeps null (no filter) distinct from an empty selection while matching owner keys exactly', () => {
        const rows = [
            makeRow({ identifier: 'owned', user_id: 42 }),
            makeRow({ identifier: 'other', user_id: 43 }),
            makeRow({ identifier: 'unbound', user_id: null }),
        ];
        expect(identifiers(filterIdentifiersByOwner(rows, null))).toEqual(['owned', 'other', 'unbound']);
        expect(filterIdentifiersByOwner(rows, [])).toEqual([]);
        expect(identifiers(filterIdentifiersByOwner(rows, [42]))).toEqual(['owned']);
        expect(identifiers(filterIdentifiersByOwner(rows, [0, 43]))).toEqual(['other', 'unbound']);
        expect(identifiers(filterIdentifiersByOwner(rows, [999]))).toEqual([]);
        expect(identifiers(rows)).toEqual(['owned', 'other', 'unbound']);
    });

    it('sorts identifiers in both directions and keeps equal values stable', () => {
        const rows = [
            makeRow({ identifier: 'Alpha10' }),
            makeRow({ identifier: 'Alpha02' }),
            makeRow({ identifier: 'Alpha01', safe: undefined }),
            makeRow({ identifier: 'Alpha01', user_id: 43 }),
        ];
        expect(identifiers(sortIdentifiers(rows, 'identifier', 1))).toEqual(['Alpha01', 'Alpha01', 'Alpha02', 'Alpha10']);
        expect(identifiers(sortIdentifiers(rows, 'identifier', -1))).toEqual(['Alpha10', 'Alpha02', 'Alpha01', 'Alpha01']);
        expect(identifiers(sortIdentifiers(rows, 'identifier', 0))).toEqual(['Alpha10', 'Alpha02', 'Alpha01', 'Alpha01']);
        expect(identifiers(sortIdentifiers(rows, 'identifier', undefined))).toEqual(['Alpha10', 'Alpha02', 'Alpha01', 'Alpha01']);
        expect(identifiers(rows)).toEqual(['Alpha10', 'Alpha02', 'Alpha01', 'Alpha01']);
    });

    it('sorts safe with missing values last in both directions', () => {
        const rows = [
            makeRow({ identifier: 'missing', safe: undefined }),
            makeRow({ identifier: 'yes', safe: true }),
            makeRow({ identifier: 'no', safe: false }),
        ];
        expect(identifiers(sortIdentifiers(rows, 'safe', 1))).toEqual(['no', 'yes', 'missing']);
        expect(identifiers(sortIdentifiers(rows, 'safe', -1))).toEqual(['yes', 'no', 'missing']);
        expect(identifierSortValue(rows[0], 'safe')).toBeNull();
        expect(identifierSortValue(rows[1], 'safe')).toBe(1);
        expect(compareIdentifierSortValues(null, null, -1)).toBe(0);
        expect(compareIdentifierSortValues(null, 1, -1)).toBe(1);
        expect(compareIdentifierSortValues(1, null, -1)).toBe(-1);
    });

    it('slices from an arbitrary start, truncates the tail and rejects non-positive sizes', () => {
        const rows = Array.from({ length: 53 }, (_, index) => makeRow({ identifier: `Alpha${index}` }));
        expect(identifiers(sliceIdentifiers(rows, 25, 25))).toEqual(Array.from({ length: 25 }, (_, index) => `Alpha${index + 25}`));
        expect(identifiers(sliceIdentifiers(rows, 50, 25))).toEqual(['Alpha50', 'Alpha51', 'Alpha52']);
        expect(sliceIdentifiers(rows, 3, 0)).toEqual([]);
        expect(identifiers(sliceIdentifiers(rows, -5, 2))).toEqual(['Alpha0', 'Alpha1']);
    });
});
