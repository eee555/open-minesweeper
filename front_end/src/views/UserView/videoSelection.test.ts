import { describe, expect, it } from 'vitest';

import { selectProfileVideos } from './videoSelection';

import { createVideoListFilters, filterVideos } from '@/components/VideoList/videoListData';
import { toISODateString } from '@/utils/datetime';
import { VideoAbstract } from '@/utils/videoabstract';

const upload = new Date(2026, 9, 14, 0, 30);
const end = new Date(2026, 9, 13, 23, 59);
const videos = [
    new VideoAbstract({ id: 1, level: 'e', bv: 100, timems: 40000, software: 'a', state: 'c', mode: '00', upload_time: upload, end_time: end }),
    new VideoAbstract({ id: 2, level: 'e', bv: 100, timems: 40000, software: 'r', state: 'd', mode: '05', upload_time: upload }),
    new VideoAbstract({ id: 3, level: 'i', bv: 100, timems: 40000, software: 'e', state: 'a', mode: '00', upload_time: upload }),
    new VideoAbstract({ id: 4, level: 'c10_10_10', bv: 50, timems: 40000, software: 'e', state: 'b', mode: '11', upload_time: upload }),
];
const ids = (items: VideoAbstract[]) => items.map((video) => video.id);

describe('profile video selection', () => {
    it('selects every BV bucket member across software, mode and state, with level isolation', () => {
        expect(ids(selectProfileVideos(videos, { kind: 'bv', level: 'e', bv: 100 }))).toEqual([1, 2]);
        expect(ids(selectProfileVideos(videos, { kind: 'bv', level: 'i', bv: 100 }))).toEqual([3]);
        expect(selectProfileVideos(videos, { kind: 'bv', level: 'b', bv: 100 })).toEqual([]);
        expect(selectProfileVideos(videos, { kind: 'all' })).toBe(videos);
    });

    it('uses local calendar days and falls back from missing end time to upload time', () => {
        expect(ids(selectProfileVideos(videos, { kind: 'date', dateKey: toISODateString(upload) }))).toEqual([1, 2, 3, 4]);
        expect(ids(selectProfileVideos(videos, { kind: 'date', dateKey: toISODateString(end) }, true))).toEqual([1]);
        expect(ids(selectProfileVideos(videos, { kind: 'date', dateKey: toISODateString(upload) }, true))).toEqual([2, 3, 4]);
        expect(selectProfileVideos(videos, { kind: 'date', dateKey: '2000-01-01' })).toEqual([]);
    });

    it('applies shared filters after the selection without modifying the complete distribution', () => {
        const bucket = selectProfileVideos(videos, { kind: 'bv', level: 'e', bv: 100 });
        const filters = createVideoListFilters();
        expect(ids(filterVideos(videos, filters))).toEqual([1, 2, 3, 4]);
        filters.software = ['r'];
        filters.mode = ['05'];
        filters.state = ['d'];
        expect(ids(filterVideos(bucket, filters))).toEqual([2]);
        expect(ids(bucket)).toEqual([1, 2]);
        expect(videos).toHaveLength(4);
        filters.state = [];
        expect(filterVideos(bucket, filters)).toEqual([]);
        filters.state = ['b'];
        filters.software = ['e'];
        filters.mode = ['11'];
        filters.level = 'custom';
        expect(ids(filterVideos(videos, filters))).toEqual([4]);
    });
});
