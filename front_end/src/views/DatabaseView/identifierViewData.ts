export interface IdentifierResult {
    identifier: string;
    user_id: number | null;
    safe?: boolean;
}

export type IdentifierTableRow = IdentifierResult & { ownerKey: number };

export const identifierSortFields = ['identifier', 'safe'] as const;
export type IdentifierSortField = typeof identifierSortFields[number];

export type IdentifierSortValue = string | number | null;

export function toIdentifierTableRow(result: IdentifierResult): IdentifierTableRow {
    return { ...result, ownerKey: result.user_id ?? 0 };
}

export function filterIdentifiersByOwner(rows: readonly IdentifierTableRow[], selected: readonly number[] | null): IdentifierTableRow[] {
    if (selected === null) return [...rows];
    const keys = new Set(selected);
    return rows.filter((row) => keys.has(row.ownerKey));
}

export function identifierSortValue(row: IdentifierTableRow, field: IdentifierSortField): IdentifierSortValue {
    if (field === 'identifier') return row.identifier ?? null;
    return row.safe === undefined ? null : Number(row.safe);
}

export function compareIdentifierSortValues(a: IdentifierSortValue, b: IdentifierSortValue, order: number): number {
    const aMissing = a === null;
    const bMissing = b === null;
    if (aMissing !== bMissing) return aMissing ? 1 : -1;
    if (aMissing) return 0;
    const base = typeof a === 'number' && typeof b === 'number' ? Math.sign(a - b) : String(a).localeCompare(String(b));
    return base * (order < 0 ? -1 : 1);
}

export function sortIdentifiers(rows: readonly IdentifierTableRow[], field: IdentifierSortField, order: number | undefined): IdentifierTableRow[] {
    const result = [...rows];
    if (order === undefined || order === 0) return result;
    const decorated = result.map((row, index) => ({ row, index, value: identifierSortValue(row, field) }));
    decorated.sort((a, b) => compareIdentifierSortValues(a.value, b.value, order) || a.index - b.index);
    return decorated.map((entry) => entry.row);
}

export function sliceIdentifiers(rows: readonly IdentifierTableRow[], first: number, size: number): IdentifierTableRow[] {
    if (!Number.isFinite(size) || size <= 0) return [];
    const start = Number.isFinite(first) ? Math.max(0, Math.floor(first)) : 0;
    return rows.slice(start, start + Math.floor(size));
}
