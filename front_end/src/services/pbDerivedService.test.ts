import { afterEach, describe, expect, it, vi } from 'vitest';

import {
    defaultDerivedSort, derivedCollectionKeys, derivedField, derivedOverviewKeys, derivedPages, derivedSegments, derivedSkillTTSortKeys, derivedSort, derivedTitle,
    fetchDerivedRanking, fetchDerivedSummary, formatDerivedCount, formatDerivedNumber, formatDerivedPercent,
    formatDerivedValue, formatRank, formatWithRank, modeKey, parseDerivedSort, rebuildDerivedPlayer,
} from './pbDerivedService';

import $axios from '@/http';

describe('PB derived ranking service', () => {
    afterEach(() => vi.restoreAllMocks());

    it('keeps three significant digits on the nearer side and restores the original probability', () => {
        expect(formatDerivedPercent(0)).toBe('0%');
        expect(formatDerivedPercent(1)).toBe('100%');
        expect(formatDerivedPercent(0.999876)).toBe('99.9876%');
        expect(formatDerivedPercent(0.9999)).toBe('99.99%');
        expect(formatDerivedPercent(0.99999999)).toBe('99.999999%');
        expect(formatDerivedPercent(0.98765)).toBe('98.76%');
        expect(formatDerivedPercent(0.5)).toBe('50%');
        expect(formatDerivedPercent(0.123)).toBe('12.3%');
        expect(formatDerivedPercent(0.1234)).toBe('12.3%');
        expect(formatDerivedPercent(0.012345)).toBe('1.23%');
        expect(formatDerivedPercent(0.00012345)).toBe('0.0123%');
        expect(formatDerivedPercent(2.999876)).toBe('299.9876%');
        expect(formatDerivedPercent(1.234)).toBe('123%');
        expect(formatDerivedPercent(2.345)).toBe('234.5%');
        expect(formatDerivedPercent(3)).toBe('300%');
        expect(formatDerivedPercent(undefined)).toBe('--');
    });

    it('formats counts, three-decimal values and raw-value titles separately', () => {
        expect(formatDerivedCount(3)).toBe('3');
        expect(formatDerivedNumber(1.23456)).toBe('1.235');
        expect(formatDerivedValue('probability', 0.012345)).toBe('1.23%');
        expect(formatDerivedValue('tt', 999.999)).toBe('999.999');
        expect(derivedTitle('tt', 1.23456)).toBe('1.23456');
        expect(derivedTitle('count', 3)).toBe('3');
        expect(formatRank(null)).toBe('--');
        expect(formatWithRank(1.23456, 'skill', 7)).toBe('1.235(7)');
    });

    it('builds field names, sort keys and per-view defaults', () => {
        expect(modeKey(true)).toBe('nf');
        expect(derivedField('nf', 'e:s3')).toBe('nf:e:s3');
        expect(derivedSort('typical_time', 'e:s3')).toBe('typical_time:e:s3');
        expect(parseDerivedSort('typical_time:e:s3', true)).toEqual({ ranking: 'typical_time', field: 'nf:e:s3' });
        expect(derivedCollectionKeys).toHaveLength(12);
        expect(derivedOverviewKeys).toHaveLength(8);
        expect(derivedPages).toHaveLength(7);
        expect(defaultDerivedSort('overview')).toBe('skill:sum:total');
        expect(defaultDerivedSort('skill_b')).toBe('skill:b:total');
        expect(defaultDerivedSort('tt_e')).toBe('typical_time:e:total');
    });

    it('keeps static segment boundaries contiguous and builds every sort key from them', () => {
        const lastBV = { b: 54, i: 216, e: 381 };
        expect(Object.values(derivedSegments).flat()).toHaveLength(23);
        for (const [level, bounds] of Object.entries(derivedSegments)) {
            let expected = 1;
            bounds.forEach((segment, index) => {
                expect(segment.field).toBe(`s${index + 1}`);
                expect(segment.start).toBe(expected);
                expect(segment.end).toBeGreaterThanOrEqual(segment.start);
                expected = segment.end + 1;
            });
            expect(bounds.at(-1)?.end).toBe(lastBV[level as keyof typeof lastBV]);
        }
        expect(derivedSkillTTSortKeys).toHaveLength(54);
        expect(derivedSkillTTSortKeys).toContain('typical_time:e:s11');
        expect(derivedSkillTTSortKeys).not.toContain('typical_time:e:s12');
        for (const page of derivedPages) expect(derivedSkillTTSortKeys).toContain(defaultDerivedSort(page));
    });

    it('requests one ranking page and a full player summary', async () => {
        const ranking = { count: 1, rows: [{ player_id: 48, records: { collection: { 'std:sum:count': 2 } } }] };
        const get = vi.spyOn($axios, 'get').mockResolvedValue({ data: ranking });
        expect(await fetchDerivedRanking('collection', 'std:sum:count', 20, 40)).toEqual(ranking);
        expect(get).toHaveBeenCalledExactlyOnceWith('/api/speedranking/pb_derived/rank', { params: { ranking: 'collection', field: 'std:sum:count', start: 20, end: 40 }, signal: undefined });
        get.mockClear().mockResolvedValue({ data: { pb: [], records: {}, ranks: {} } });
        expect(await fetchDerivedSummary(48)).toEqual({ pb: [], records: {}, ranks: {} });
        expect(get).toHaveBeenCalledExactlyOnceWith('/api/speedranking/pb_derived/summary', { params: { player_id: 48 }, signal: undefined });
    });

    it('posts a form body when an admin rebuilds one player', async () => {
        const post = vi.spyOn($axios, 'post').mockResolvedValue({ data: { player_id: 48, fields: 54 } });
        expect(await rebuildDerivedPlayer(48)).toEqual({ player_id: 48, fields: 54 });
        expect(post).toHaveBeenCalledExactlyOnceWith('/api/speedranking/pb_derived/admin/rebuild_player', { player_id: 48 });
    });
});
