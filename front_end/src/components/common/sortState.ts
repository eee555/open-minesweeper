export type SortState = 'none' | 'ascending' | 'descending';

export function sortState(order: number | undefined, active = true): SortState {
    if (!active || order === undefined || order === 0) return 'none';
    return order < 0 ? 'descending' : 'ascending';
}

export function nextSortOrder(order: number | undefined, active = true, clearedOrder: number | undefined = 0): number | undefined {
    if (!active || order === undefined || order === clearedOrder) return 1;
    if (order === 1) return -1;
    if (order === -1) return clearedOrder;
    return 1;
}
