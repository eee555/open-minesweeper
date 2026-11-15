export type SortState = 'none' | 'ascending' | 'descending';

export function sortState(order: number | undefined, active = true): SortState {
    if (!active || order === undefined || order === 0) return 'none';
    return order < 0 ? 'descending' : 'ascending';
}
