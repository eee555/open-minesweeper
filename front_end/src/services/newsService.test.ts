import { describe, expect, it } from 'vitest';

import { formatEffValue } from './newsService';
import type { EffNewsRecord } from './newsService';

function record(overrides: Partial<EffNewsRecord> = {}): EffNewsRecord {
    return { value: 1, video_id: 1, rank: 1, count: null, timems: null, ...overrides };
}

describe('formatEffValue', () => {
    it('formats ordinary efficiency values to three decimals', () => {
        expect(formatEffValue(record({ value: 0.9 }), 'thrp:b')).toBe('0.900');
        expect(formatEffValue(record({ value: 1.5 }), 'nf_ioe:sum')).toBe('1.500');
    });

    it('uses 1 x N when expert NF has more than one perfect game', () => {
        expect(formatEffValue(record({ count: 1 }), 'thrp:e_nf')).toBe('1.000');
        expect(formatEffValue(record({ count: 2 }), 'thrp:e_nf')).toBe('1 x 2');
    });

    it('appends the comparison time for perfect NF IOE records', () => {
        expect(formatEffValue(record({ value: 1, timems: 10000 }), 'nf_ioe:e')).toBe('1.000 (10.000)');
        expect(formatEffValue(record({ value: 3, timems: 9000 }), 'nf_ioe:sum')).toBe('3.000 (9.000)');
    });

    it('omits the comparison time below the maximum', () => {
        expect(formatEffValue(record({ value: 0.9, timems: 10000 }), 'nf_ioe:e')).toBe('0.900');
        expect(formatEffValue(record({ value: 2.9, timems: 10000 }), 'nf_ioe:sum')).toBe('2.900');
    });

    it('does not apply one ranking\'s format to the other', () => {
        expect(formatEffValue(record({ count: 2 }), 'nf_ioe:e')).toBe('1.000');
        expect(formatEffValue(record({ timems: 10000 }), 'thrp:e')).toBe('1.000');
    });
});
