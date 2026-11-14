import { clamp } from '@/utils/math';

export const DEFAULT_MAX_SEGMENTS = 5;
export const PAGINATION_WIDE_MAX_SEGMENTS = 17;
export const PAGINATION_FIXED_WIDTH = 180;
export const PAGINATION_SEGMENT_WIDTH = 100;

export function maxSegmentsForWidth(width: number): number {
    if (!Number.isFinite(width) || width <= 0) return DEFAULT_MAX_SEGMENTS;
    const budget = Math.floor((width - PAGINATION_FIXED_WIDTH) / PAGINATION_SEGMENT_WIDTH);
    return clamp(budget, 1, PAGINATION_WIDE_MAX_SEGMENTS);
}

export interface PaginationRange {
    start: number;
    end: number;
}

export interface PaginationSegmentItem extends PaginationRange {
    type: 'segment';
    current: boolean;
}

export type PaginationItem = PaginationSegmentItem | { type: 'ellipsis' };

export interface PaginationItemsOptions {
    total: number;
    pageSize: number;
    currentStart: number;
    maxSegments?: number;
}

export function normalizeTotal(total: number): number {
    return Number.isFinite(total) && total > 0 ? Math.floor(total) : 0;
}

export function normalizePageSize(pageSize: number): number {
    return Number.isFinite(pageSize) && pageSize >= 1 ? Math.floor(pageSize) : 1;
}

export function clampStart(start: number, total: number): number {
    if (total <= 0) return 1;
    const value = Number.isFinite(start) ? Math.floor(start) : 1;
    return clamp(value, 1, total);
}

export function rangeFor(total: number, pageSize: number, start: number): PaginationRange {
    if (total <= 0) return { start: 0, end: 0 };
    const current = clampStart(start, total);
    return { start: current, end: Math.min(current + pageSize - 1, total) };
}

export function segmentCount(total: number, pageSize: number): number {
    return total <= 0 ? 0 : Math.ceil(total / pageSize);
}

export function segmentRange(index: number, total: number, pageSize: number): PaginationRange {
    const start = 1 + index * pageSize;
    return { start, end: Math.min(start + pageSize - 1, total) };
}

export function lastSegmentStart(total: number, pageSize: number): number {
    const count = segmentCount(total, pageSize);
    return count === 0 ? 1 : 1 + (count - 1) * pageSize;
}

export function previousStart(start: number, total: number, pageSize: number): number {
    return clampStart(Math.max(1, start - pageSize), total);
}

export function nextStart(start: number, total: number, pageSize: number): number {
    return clampStart(start + pageSize, total);
}

export function canGoNext(range: PaginationRange, total: number): boolean {
    return total > 0 && range.end < total;
}

export function buildPaginationItems(options: PaginationItemsOptions): PaginationItem[] {
    const total = normalizeTotal(options.total);
    const pageSize = normalizePageSize(options.pageSize);
    if (total === 0) return [];

    const count = segmentCount(total, pageSize);
    const start = clampStart(options.currentStart, total);
    const currentIndex = Math.floor((start - 1) / pageSize);
    const aligned = (start - 1) % pageSize === 0;
    const range = rangeFor(total, pageSize, start);
    const maxSegments = Math.max(1, Math.floor(options.maxSegments ?? DEFAULT_MAX_SEGMENTS));

    const indices = new Set<number>([0, count - 1, currentIndex]);
    const offset = Math.floor(maxSegments / 2);
    const windowStart = Math.max(0, Math.min(currentIndex - offset, count - maxSegments));
    const windowEnd = Math.min(count, windowStart + maxSegments);
    for (let index = windowStart; index < windowEnd; index += 1) indices.add(index);

    const sorted = [...indices].sort((a, b) => a - b);
    const filled: number[] = [];
    let previous = -1;
    for (const index of sorted) {
        if (previous >= 0 && index - previous === 2) filled.push(previous + 1);
        filled.push(index);
        previous = index;
    }

    const items: PaginationItem[] = [];
    let last = -1;
    for (const index of filled) {
        if (last >= 0 && index - last > 1) items.push({ type: 'ellipsis' });
        items.push({ type: 'segment', ...segmentRange(index, total, pageSize), current: aligned && index === currentIndex });
        if (!aligned && index === currentIndex) {
            items.push({ type: 'segment', start: range.start, end: range.end, current: true });
        }
        last = index;
    }
    return items;
}
