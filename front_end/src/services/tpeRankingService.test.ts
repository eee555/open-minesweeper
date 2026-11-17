import { describe, expect, it } from 'vitest';

import { formatTPEValue, tpeValue, tpeVideoId } from './tpeRankingService';
import type { TPERecord } from './tpeRankingService';

describe('TPE records', () => {
    it('preserves zero and raw precision, requires both levels for sum and only links individual replays', () => {
        const record: TPERecord = { player_id: 42, i: { value: 0, video_id: 1 }, e: null };
        expect(tpeValue(record, 'i')).toBe(0);
        expect(formatTPEValue(record, 'i')).toBe('0.000');
        expect(tpeValue(record, 'sum')).toBeNull();
        expect(formatTPEValue(record, 'sum')).toBe('--');
        record.e = { value: 123.456789, video_id: 2 };
        expect(tpeValue(record, 'sum')).toBe(123.456789);
        expect(formatTPEValue(record, 'sum')).toBe('123.457');
        expect(tpeVideoId(record, 'e')).toBe(2);
        expect(tpeVideoId(record, 'sum')).toBeUndefined();
        expect(formatTPEValue(undefined, 'sum')).toBe('--');
    });
});
