import { describe, expect, it } from 'vitest';

import {
    columnConfig, createVideoListFilters, CUSTOM_LEVEL_FILTER, filterVideos,
    isColumnFilterActive, sliceVideos, sortValue, sortVideos,
} from './videoListData';

import { MS_Mode, MS_State } from '@/utils/ms_const';
import type { VideoAbstractData } from '@/utils/videoabstract';
import { VideoAbstract } from '@/utils/videoabstract';

function makeVideo(overrides: Partial<VideoAbstractData> = {}): VideoAbstract {
    return new VideoAbstract({
        id: 1,
        level: 'e',
        mode: MS_Mode.Standard,
        timems: 40000,
        bv: 100,
        software: 'e',
        upload_time: new Date('2026-01-01T00:00:00Z'),
        end_time: new Date('2026-01-02T00:00:00Z'),
        ...overrides,
    });
}

function ids(videos: readonly VideoAbstract[]): number[] {
    return videos.map((video) => video.id);
}

describe('video list filters', () => {
    it('starts from all states, softwares and modes with no level restriction', () => {
        const filters = createVideoListFilters();
        expect(filters.state).toContain(MS_State.Local);
        expect(filters.software).toHaveLength(5);
        expect(filters.level).toBeNull();
        expect(filters.mode).toHaveLength(5);
    });

    it('keeps local CSV videos and custom levels visible by default', () => {
        const videos = [
            makeVideo({ id: 1 }),
            makeVideo({ id: 2, level: 'c9_9_10' }),
            VideoAbstract.fromArbiterCsv({ level: 'c9_9_10', mode: MS_Mode.Standard, timems: 35000, bv: 90, software: 'a', end_time: new Date('2026-02-01T00:00:00Z') }),
        ];
        expect(ids(filterVideos(videos, createVideoListFilters()))).toEqual([1, 2, 0]);
        expect(videos[2]?.isLocal).toBe(true);
    });

    it('combines state, software, mode and level without mutating the input', () => {
        const videos = [
            makeVideo({ id: 1, state: MS_State.Plain, software: 'e', mode: MS_Mode.Standard, level: 'e' }),
            makeVideo({ id: 2, state: MS_State.Frozen, software: 'a', mode: MS_Mode.Lucky, level: 'i' }),
            makeVideo({ id: 3, state: MS_State.Official, software: 'e', mode: MS_Mode.Recursive, level: 'c9_9_10' }),
        ];
        const snapshot = [...videos];
        const filters = createVideoListFilters();
        filters.state = [MS_State.Plain, MS_State.Official];
        filters.software = ['e'];
        filters.mode = [MS_Mode.Standard, MS_Mode.Recursive];
        expect(ids(filterVideos(videos, filters))).toEqual([1, 3]);
        filters.level = 'e';
        expect(ids(filterVideos(videos, filters))).toEqual([1]);
        filters.level = CUSTOM_LEVEL_FILTER;
        expect(ids(filterVideos(videos, filters))).toEqual([3]);
        filters.level = null;
        filters.state = [];
        expect(filterVideos(videos, filters)).toEqual([]);
        expect(videos).toEqual(snapshot);
    });

    it('treats an empty multi-select as no matches and a null level as all levels', () => {
        const videos = [makeVideo({ id: 1 }), makeVideo({ id: 2 })];
        const filters = createVideoListFilters();
        filters.software = [];
        expect(filterVideos(videos, filters)).toEqual([]);
        filters.software = ['e'];
        filters.level = null;
        expect(ids(filterVideos(videos, filters))).toEqual([1, 2]);
    });
});

describe('video list sorting', () => {
    it('sorts raw numbers and derived getters by value instead of display text', () => {
        const slower = makeVideo({ id: 1, timems: 40000, bv: 100 });
        const faster = makeVideo({ id: 2, timems: 20000, bv: 100 });
        expect(ids(sortVideos([slower, faster], 'bv', 1))).toEqual([1, 2]);
        expect(ids(sortVideos([faster, slower], 'bvs', 1))).toEqual([1, 2]);
        expect(ids(sortVideos([faster, slower], 'bvs', -1))).toEqual([2, 1]);
        expect(sortValue(slower, 'bvs')).toBeCloseTo(2.5);
    });

    it('sorts dates and keeps an undefined order as the original order', () => {
        const early = makeVideo({ id: 1, upload_time: new Date('2026-01-01T00:00:00Z') });
        const late = makeVideo({ id: 2, upload_time: new Date('2026-03-01T00:00:00Z') });
        expect(ids(sortVideos([early, late], 'upload_time', -1))).toEqual([2, 1]);
        expect(ids(sortVideos([early, late], 'upload_time', 1))).toEqual([1, 2]);
        expect(ids(sortVideos([early, late], 'upload_time', undefined))).toEqual([1, 2]);
        expect(ids(sortVideos([early, late], 'upload_time', 0))).toEqual([1, 2]);
    });

    it('always places NaN, missing and invalid dates last in both directions', () => {
        const normal = makeVideo({ id: 1, bv: 100 });
        const nan = makeVideo({ id: 2, bv: Number.NaN });
        const invalidDate = makeVideo({ id: 3, end_time: new Date('invalid') });
        const noDate = makeVideo({ id: 4, end_time: undefined });
        expect(ids(sortVideos([normal, nan], 'bv', 1))).toEqual([1, 2]);
        expect(ids(sortVideos([nan, normal], 'bv', -1))).toEqual([1, 2]);
        expect(ids(sortVideos([noDate, invalidDate, normal], 'end_time', 1))).toEqual([1, 4, 3]);
        expect(ids(sortVideos([noDate, invalidDate, normal], 'end_time', -1))).toEqual([1, 4, 3]);
    });

    it('keeps equal values in input order and does not mutate the input', () => {
        const videos = [makeVideo({ id: 1 }), makeVideo({ id: 2 }), makeVideo({ id: 3 })];
        const snapshot = [...videos];
        expect(ids(sortVideos(videos, 'bv', -1))).toEqual([1, 2, 3]);
        expect(ids(sortVideos(videos, 'bv', 1))).toEqual([1, 2, 3]);
        expect(videos).toEqual(snapshot);
    });

    it('uses custom level codes for the level sort value', () => {
        const custom = makeVideo({ id: 1, level: 'c9_9_10' });
        const standard = makeVideo({ id: 2, level: 'e' });
        expect(sortValue(custom, 'level')).toBe('c9_9_10');
        expect(sortValue(custom, 'stnb')).toBeNaN();
        expect(ids(sortVideos([custom, standard], 'level', 1))).toEqual([1, 2]);
    });
});

describe('video list slicing', () => {
    it('connects filtered results with an arbitrary start index', () => {
        const videos = Array.from({ length: 40 }, (_, index) => makeVideo({ id: index + 1 }));
        const filtered = filterVideos(videos, createVideoListFilters());
        expect(ids(sliceVideos(filtered, 13, 25))).toEqual(Array.from({ length: 25 }, (_, index) => index + 14));
        expect(ids(sliceVideos(filtered, 37, 25))).toEqual([38, 39, 40]);
        expect(sliceVideos(filtered, 0, 0)).toEqual([]);
        expect(videos).toHaveLength(40);
    });
});

describe('video list columns', () => {
    it('keeps fixed sort and filter capabilities for each column family', () => {
        expect(columnConfig('state')).toMatchObject({ sortable: false, filterable: true });
        expect(columnConfig('player')).toMatchObject({ sortable: false, filterable: false });
        expect(columnConfig('upload_time')).toMatchObject({ sortable: true, sortField: 'upload_time' });
        expect(columnConfig('bv')).toMatchObject({ sortable: true, sortField: 'bv', filterable: false });
        expect(columnConfig('file_size')).toMatchObject({ sortable: true, sortField: 'file_size' });
    });

    it('omits header labels only for the four filtered icon columns', () => {
        expect(columnConfig('state').headLabel).toBe(false);
        expect(columnConfig('software').headLabel).toBe(false);
        expect(columnConfig('mode').headLabel).toBe(false);
        expect(columnConfig('level').headLabel).toBe(false);
        expect(columnConfig('player').headLabel).toBe(true);
        expect(columnConfig('upload_time').headLabel).toBe(true);
        expect(columnConfig('bv').headLabel).toBe(true);
    });

    it('marks a column filter active only when its selection is not full', () => {
        const filters = createVideoListFilters();
        const choices = ['state', 'software', 'mode', 'level'] as const;
        for (const choice of choices) {
            expect(isColumnFilterActive(choice, filters)).toBe(false);
        }
        filters.state = ['a'];
        filters.software = ['e'];
        filters.mode = ['00'];
        filters.level = 'e';
        for (const choice of choices) {
            expect(isColumnFilterActive(choice, filters)).toBe(true);
        }
        expect(isColumnFilterActive('state', { ...filters, state: ['a', 'b', 'c', 'd'] }, false)).toBe(false);
        expect(isColumnFilterActive('state', { ...filters, state: ['a', 'b', 'c', 'd'] }, true)).toBe(true);
        expect(isColumnFilterActive('bv', filters)).toBe(false);
    });
});
