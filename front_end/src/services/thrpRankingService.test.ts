import { describe, expect, it } from 'vitest';

import { formatThrpValue, thrpValue } from './thrpRankingService';
import type { ThrpRecord } from './thrpRankingService';

describe('Thrp ranking', () => {
    it('keeps raw values and sums missing levels as zero', () => {
        const record: ThrpRecord = { player_id: 42, b: { value: 1.2345678, video_id: 8001, upload_time: '2026-10-19T12:00:00Z' }, i: null, e: null, e_nf: null };
        expect(thrpValue(record, 'b')).toBe(1.2345678);
        expect(thrpValue(record, 'i')).toBeNull();
        expect(thrpValue(record, 'sum')).toBe(1.2345678);
        record.e = { value: 2, video_id: 8002, upload_time: '2026-10-19T12:00:00Z' };
        record.e_nf = { value: 1, video_ids: [8003, 8004, 8005] };
        expect(thrpValue(record, 'sum')).toBeCloseTo(3.2345678, 12);
        expect(formatThrpValue(record, 'e_nf')).toBe('1 x 3');
        record.e_nf.video_ids = [8003];
        expect(formatThrpValue(record, 'e_nf')).toBe('1.000');
        record.e_nf.value = 0.9;
        expect(formatThrpValue(record, 'e_nf')).toBe('0.900');
    });
});
