import { describe, expect, it } from 'vitest';

import { formatNFIOEValue, nfIOEValue } from './nfIOERankingService';
import type { NFIOERecord } from './nfIOERankingService';

describe('NF IOE records', () => {
    it('adds raw IOE, fills missing levels with zero and only shows comparison times at perfection', () => {
        const record: NFIOERecord = { player_id: 42, b: { value: 0.5, video_id: 1, timems: 10 }, i: null, e: null };
        expect(nfIOEValue(record, 'sum')).toBe(0.5);
        expect(formatNFIOEValue(record, 'b')).toBe('0.500');
        expect(formatNFIOEValue(record, 'i')).toBe('--');
        record.b = { value: 1, video_id: 1, timems: 8000 };
        record.i = { value: 1, video_id: 2, timems: 20000 };
        record.e = { value: 1, video_id: 3, timems: 45000 };
        expect(formatNFIOEValue(record, 'b')).toBe('1.000 (8.000)');
        expect(formatNFIOEValue(record, 'sum')).toBe('3.000 (45.000)');
    });
});
