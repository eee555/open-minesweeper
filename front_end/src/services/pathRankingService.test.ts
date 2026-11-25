import { describe, expect, it } from 'vitest';

import { formatPathValue, pathStats, pathValue, pathVideoId } from './pathRankingService';
import type { PathRecord } from './pathRankingService';

describe('Path records', () => {
    it('converts raw distances to cells, preserving zero, missing metrics and complete sums', () => {
        const record: PathRecord = {
            player_id: 42,
            b_path: { value: 0, video_id: 1 },
            b_cpath: null,
            b_epath: { value: 9, video_id: 2 },
            i_path: { value: 10, video_id: 3 },
            i_cpath: { value: 2, video_id: 4 },
            i_epath: null,
            e_path: { value: 12.3456789, video_id: 5 },
            e_cpath: { value: 3, video_id: 6 },
            e_epath: null,
        };
        expect(pathStats).toEqual(['b_path', 'b_cpath', 'b_epath', 'i_path', 'i_cpath', 'i_epath', 'e_path', 'e_cpath', 'e_epath', 'sum_path', 'sum_cpath', 'sum_epath']);
        expect(formatPathValue(record, 'b_path')).toBe('0.000');
        expect(pathValue(record, 'e_path')).toBe(12.3456789 / 16);
        expect(pathValue(record, 'sum_path')).toBe(22.3456789 / 16);
        expect(formatPathValue(record, 'sum_path')).toBe('1.397');
        expect(pathValue(record, 'b_epath')).toBe(9 / 16);
        expect(record.e_path?.value).toBe(12.3456789);
        expect(pathValue(record, 'sum_cpath')).toBeNull();
        expect(pathValue(record, 'sum_epath')).toBeNull();
        expect(pathVideoId(record, 'e_path')).toBe(5);
        expect(pathVideoId(record, 'sum_path')).toBeUndefined();
        expect(formatPathValue(undefined, 'sum_epath')).toBe('--');
        record.b_cpath = { value: 0, video_id: 7 };
        expect(pathValue(record, 'sum_cpath')).toBe(5 / 16);
    });
});
