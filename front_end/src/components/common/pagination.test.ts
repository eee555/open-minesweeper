import { describe, expect, it } from 'vitest';

import {
    buildPaginationItems, canGoNext, clampStart, DEFAULT_MAX_SEGMENTS, lastSegmentStart,
    maxSegmentsForWidth, nextStart, normalizePageSize, normalizeTotal, PAGINATION_WIDE_MAX_SEGMENTS,
    previousStart, rangeFor, segmentCount,
} from './pagination';

describe('pagination calculations', () => {
    it('normalizes invalid totals and page sizes', () => {
        expect(normalizeTotal(0)).toBe(0);
        expect(normalizeTotal(-3)).toBe(0);
        expect(normalizeTotal(Number.NaN)).toBe(0);
        expect(normalizeTotal(12.9)).toBe(12);
        expect(normalizePageSize(0)).toBe(1);
        expect(normalizePageSize(Number.POSITIVE_INFINITY)).toBe(1);
        expect(normalizePageSize(7.9)).toBe(7);
    });

    it('keeps arbitrary valid starts and clamps out-of-range starts', () => {
        expect(clampStart(13, 37)).toBe(13);
        expect(clampStart(0, 37)).toBe(1);
        expect(clampStart(99, 37)).toBe(37);
        expect(clampStart(50, 0)).toBe(1);
        expect(clampStart(Number.NaN, 37)).toBe(1);
    });

    it('computes inclusive 1-based ranges and truncates the last interval', () => {
        expect(rangeFor(0, 25, 1)).toEqual({ start: 0, end: 0 });
        expect(rangeFor(10, 25, 1)).toEqual({ start: 1, end: 10 });
        expect(rangeFor(100, 25, 26)).toEqual({ start: 26, end: 50 });
        expect(rangeFor(37, 25, 13)).toEqual({ start: 13, end: 37 });
        expect(rangeFor(37, 25, 26)).toEqual({ start: 26, end: 37 });
        expect(rangeFor(100, 25, 90)).toEqual({ start: 90, end: 100 });
    });

    it('moves by page size without rounding to regular segments', () => {
        expect(segmentCount(0, 25)).toBe(0);
        expect(segmentCount(37, 25)).toBe(2);
        expect(lastSegmentStart(37, 25)).toBe(26);
        expect(lastSegmentStart(0, 25)).toBe(1);
        expect(previousStart(13, 37, 25)).toBe(1);
        expect(previousStart(51, 100, 25)).toBe(26);
        expect(nextStart(13, 37, 25)).toBe(37);
        expect(canGoNext({ start: 13, end: 37 }, 37)).toBe(false);
        expect(canGoNext({ start: 1, end: 25 }, 37)).toBe(true);
    });

    it('builds regular segments with a truncated last interval', () => {
        expect(buildPaginationItems({ total: 37, pageSize: 25, currentStart: 1 })).toEqual([
            { type: 'segment', start: 1, end: 25, current: true },
            { type: 'segment', start: 26, end: 37, current: false },
        ]);
    });

    it('shows a non-aligned start as its own current interval', () => {
        const items = buildPaginationItems({ total: 37, pageSize: 25, currentStart: 13 });
        expect(items).toEqual([
            { type: 'segment', start: 1, end: 25, current: false },
            { type: 'segment', start: 13, end: 37, current: true },
            { type: 'segment', start: 26, end: 37, current: false },
        ]);
        expect(items.filter((item) => item.type === 'segment' && item.current)).toHaveLength(1);
    });

    it('limits segment buttons and inserts ellipses for large totals', () => {
        const items = buildPaginationItems({ total: 1000, pageSize: 25, currentStart: 501, maxSegments: 5 });
        expect(items.filter((item) => item.type === 'segment')).toHaveLength(7);
        expect(items.filter((item) => item.type === 'ellipsis')).toHaveLength(2);
        expect(items.at(0)).toEqual({ type: 'segment', start: 1, end: 25, current: false });
        expect(items.at(-1)).toEqual({ type: 'segment', start: 976, end: 1000, current: false });
    });

    it('returns no segment buttons for an empty result', () => {
        expect(buildPaginationItems({ total: 0, pageSize: 25, currentStart: 1 })).toEqual([]);
    });

    it('grades the segment budget linearly by container width', () => {
        expect(maxSegmentsForWidth(0)).toBe(DEFAULT_MAX_SEGMENTS);
        expect(maxSegmentsForWidth(Number.NaN)).toBe(DEFAULT_MAX_SEGMENTS);
        expect(maxSegmentsForWidth(200)).toBe(1);
        expect(maxSegmentsForWidth(480)).toBe(3);
        expect(maxSegmentsForWidth(640)).toBe(4);
        expect(maxSegmentsForWidth(700)).toBe(5);
        expect(maxSegmentsForWidth(950)).toBe(7);
        expect(maxSegmentsForWidth(1280)).toBe(11);
        expect(maxSegmentsForWidth(1920)).toBe(PAGINATION_WIDE_MAX_SEGMENTS);
        expect(maxSegmentsForWidth(2560)).toBe(PAGINATION_WIDE_MAX_SEGMENTS);
        expect(maxSegmentsForWidth(3840)).toBe(PAGINATION_WIDE_MAX_SEGMENTS);
        expect(maxSegmentsForWidth(1200)).toBeLessThan(maxSegmentsForWidth(1600));
    });

    it('keeps the first, current and last intervals when the width budget shrinks', () => {
        const options = { total: 1000, pageSize: 25, currentStart: 501 };
        const wide = buildPaginationItems({ ...options, maxSegments: maxSegmentsForWidth(700) });
        expect(wide.filter((item) => item.type === 'segment')).toHaveLength(7);
        expect(buildPaginationItems({ ...options, maxSegments: maxSegmentsForWidth(300) })).toEqual([
            { type: 'segment', start: 1, end: 25, current: false },
            { type: 'ellipsis' },
            { type: 'segment', start: 501, end: 525, current: true },
            { type: 'ellipsis' },
            { type: 'segment', start: 976, end: 1000, current: false },
        ]);
    });

    it('shows more intervals on a wide screen', () => {
        const options = { total: 1000, pageSize: 25, currentStart: 501 };
        const medium = buildPaginationItems({ ...options, maxSegments: maxSegmentsForWidth(950) });
        const wide = buildPaginationItems({ ...options, maxSegments: maxSegmentsForWidth(1920) });
        expect(wide.filter((item) => item.type === 'segment').length).toBeGreaterThan(medium.filter((item) => item.type === 'segment').length);
    });
});
