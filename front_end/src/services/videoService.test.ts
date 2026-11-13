import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchVideoQuery } from './videoService';

const { get, fetchVideoInfos } = vi.hoisted(() => ({
    get: vi.fn(),
    fetchVideoInfos: vi.fn(),
}));

vi.mock('@/http', () => ({ default: { get } }));
vi.mock('./videoInfoService', () => ({
    fetchVideoInfos,
    videoDisplayFields: (row: Record<string, unknown>) => ({ ...row, stnb: 8 }),
}));

const queryRow = {
    id: 12,
    upload_time: '2026-11-11T00:00:00Z',
    state: 'c',
    ongoing_tournament: false,
    player_id: 101,
    player__realname: 'hidden',
};

const parsedFields = {
    software: 'e',
    level: 'b',
    mode: '00',
    end_time: null,
    file_size: 123,
    timems: 1000,
    bv: 4,
    cl: 1,
    ce: 1,
};

describe('fetchVideoQuery', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        get.mockResolvedValue({ data: { videos: [queryRow] } });
        fetchVideoInfos.mockImplementation((rows: Record<string, unknown>[]) => Promise.resolve(rows.map((row) => ({ ...parsedFields, ...row }))));
    });

    it('keeps player_id from the query response in VideoAbstract', async () => {
        const videos = await fetchVideoQuery([], []);
        expect(videos).toHaveLength(1);
        expect(videos[0].id).toBe(12);
        expect(videos[0].player_id).toBe(101);
    });

    it('sends filters and sorts as JSON params', async () => {
        const filters = [{ field: 'state', eq: 'c' }];
        const sorts = [{ field: 'timems', direction: 'desc' as const }];
        await fetchVideoQuery(filters, sorts);
        expect(get).toHaveBeenCalledWith('/api/video/query', {
            params: { filters: JSON.stringify(filters), sorts: JSON.stringify(sorts) },
            signal: undefined,
        });
    });
});
