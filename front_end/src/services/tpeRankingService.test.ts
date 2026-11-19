import { describe, expect, it } from 'vitest';

import { formatTPEValue, tpeStats, tpeValue, tpeVideoId } from './tpeRankingService';
import type { TPERecord } from './tpeRankingService';

describe('TPE records', () => {
    it('preserves zero and raw precision, requires both levels for sum and only links individual replays', () => {
        const record: TPERecord = { player_id: 42, i: { value: 0, video_id: 1 }, i2: { value: 0, video_id: 1 }, i3: { value: 0, video_id: 1 }, e: null, e2: null, e3: null };
        expect(tpeStats).toEqual(['i', 'i2', 'i3', 'e', 'e2', 'e3', 'sum', 'sum2', 'sum3']);
        expect(tpeValue(record, 'i')).toBe(0);
        expect(formatTPEValue(record, 'i')).toBe('0.000');
        expect(tpeValue(record, 'sum')).toBeNull();
        expect(formatTPEValue(record, 'sum')).toBe('--');
        record.e = { value: 123.456789, video_id: 2 };
        record.e2 = { value: 200, video_id: 3 };
        record.e3 = { value: 300, video_id: 4 };
        expect(tpeValue(record, 'sum')).toBe(123.456789);
        expect(formatTPEValue(record, 'sum')).toBe('123.457');
        expect(tpeVideoId(record, 'e')).toBe(2);
        expect(tpeVideoId(record, 'sum')).toBeUndefined();
        expect(tpeValue(record, 'sum2')).toBe(200);
        expect(tpeValue(record, 'sum3')).toBe(300);
        expect(tpeVideoId(record, 'e3')).toBe(4);
        expect(tpeVideoId(record, 'sum3')).toBeUndefined();
        expect(formatTPEValue(undefined, 'sum')).toBe('--');
    });
});
