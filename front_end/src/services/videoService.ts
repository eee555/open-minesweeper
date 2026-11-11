import { fetchVideoInfos, videoDisplayFields } from './videoInfoService';
import type { VideoMetadata } from './videoInfoService';

import $axios from '@/http';
import { VideoAbstract } from '@/utils/videoabstract';

export interface VideoQueryFilter {
    field: string;
    eq?: string | number;
    in?: (string | number)[];
    gte?: string | number;
    gt?: string | number;
    lte?: string | number;
    lt?: string | number;
}

export interface VideoQuerySort {
    field: string;
    direction: 'asc' | 'desc';
}

export async function fetchVideoList(url: string, params: Record<string, unknown> = {}): Promise<VideoAbstract[]> {
    const { data } = await $axios.get<VideoMetadata[]>(url, { params });
    return (await fetchVideoInfos(data)).map((row) => new VideoAbstract({ ...videoDisplayFields(row), ...row, bv: row.bv ?? NaN }));
}

export async function fetchVideoQuery(filters: VideoQueryFilter[], sorts: VideoQuerySort[], signal?: AbortSignal): Promise<VideoAbstract[]> {
    const { data } = await $axios.get<{ videos: VideoMetadata[] }>('/api/video/query', {
        params: { filters: JSON.stringify(filters), sorts: JSON.stringify(sorts) },
        signal,
    });
    return (await fetchVideoInfos(data.videos)).map((row) => new VideoAbstract({ ...videoDisplayFields(row), ...row, bv: row.bv ?? NaN }));
}

export async function fetchNewestQueue(): Promise<VideoAbstract[]> {
    return fetchVideoList('/api/video/newest_queue');
}
