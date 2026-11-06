import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchStrictNgRanking, fetchStrictNgRecords, formatStrictNgValue, isStrictNgTimeStat, strictNgVideoId } from './strictNgRankingService';
import type { StrictNgRecord } from './strictNgRankingService';

import $axios from '@/http';

const record: StrictNgRecord = {
    player_id: 42,
    bt: 1234,
    bb: 0,
    it: null,
    ib: null,
    et: null,
    eb: null,
    sumt: 2001232,
    sumb: 0,
    bt_id: 1,
    bb_id: 2,
    it_id: null,
    ib_id: null,
    et_id: null,
    eb_id: null,
};

describe('strictNgRanking', () => {
    afterEach(() => vi.restoreAllMocks());

    it('formats milliseconds, zero values and absent records', () => {
        expect(formatStrictNgValue(record, 'bt')).toBe('1.234');
        expect(formatStrictNgValue(record, 'bb')).toBe('0.000');
        expect(formatStrictNgValue(record, 'et')).toBe('--');
        expect(formatStrictNgValue(record, 'sumt')).toBe('2001.232');
        expect(formatStrictNgValue(record, 'sumb')).toBe('0.000');
        expect(formatStrictNgValue(undefined, 'sumt')).toBe('--');
        expect(strictNgVideoId(record, 'bt')).toBe(1);
        expect(strictNgVideoId(record, 'sumt')).toBeUndefined();
        expect(strictNgVideoId(record, 'sumb')).toBeUndefined();
        expect(strictNgVideoId(record, 'et')).toBeUndefined();
        expect(isStrictNgTimeStat('sumt')).toBe(true);
        expect(isStrictNgTimeStat('eb')).toBe(false);
    });

    it('passes the selected ranking and exclusive range to the API', async () => {
        const get = vi.spyOn($axios, 'get').mockResolvedValue({ data: { count: 1, players: [record] } });
        expect(await fetchStrictNgRanking('strict_ng_nf', 'bb', 20, 40)).toEqual({ count: 1, players: [record] });
        expect(get).toHaveBeenCalledWith('/api/speedranking/strict_ng/rank', { params: { ranking_name: 'strict_ng_nf', stat: 'bb', start: 20, end: 40 } });
        const playerRecord = { ...record, ranks: { bt: 2, bb: 3, it: null, ib: null, et: null, eb: null, sumt: 4, sumb: 5 } };
        const records = { strict_ng: playerRecord, strict_ng_nf: playerRecord };
        get.mockClear().mockResolvedValue({ data: records });
        expect(await fetchStrictNgRecords(42)).toEqual(records);
        expect(get).toHaveBeenCalledExactlyOnceWith('/api/speedranking/strict_ng/player/42');
    });
});
