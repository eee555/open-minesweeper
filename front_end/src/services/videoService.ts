import { fetchVideoInfos, videoDisplayFields } from './videoInfoService';
import type { ParsedVideoInfo, VideoMetadata } from './videoInfoService';

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

function toVideoAbstract(row: ParsedVideoInfo & VideoMetadata): VideoAbstract {
    return new VideoAbstract({ ...videoDisplayFields(row), ...row, bv: row.bv ?? NaN });
}

export async function fetchVideoList(url: string, params: Record<string, unknown> = {}, onBatch?: (rows: VideoAbstract[]) => void): Promise<VideoAbstract[]> {
    const { data } = await $axios.get<VideoMetadata[]>(url, { params });
    return (await fetchVideoInfos(data, (batch) => {
        if (onBatch !== undefined) onBatch(batch.map(toVideoAbstract));
    })).map(toVideoAbstract);
}

export async function fetchVideoQuery(filters: VideoQueryFilter[], sorts: VideoQuerySort[], signal?: AbortSignal, onBatch?: (rows: VideoAbstract[]) => void): Promise<VideoAbstract[]> {
    const { data } = await $axios.get<{ videos: VideoMetadata[] }>('/api/video/query', {
        params: { filters: JSON.stringify(filters), sorts: JSON.stringify(sorts) },
        signal,
    });
    return (await fetchVideoInfos(data.videos, (batch) => {
        if (onBatch !== undefined) onBatch(batch.map(toVideoAbstract));
    })).map(toVideoAbstract);
}

export async function fetchNewestQueue(): Promise<VideoAbstract[]> {
    return fetchVideoList('/api/video/newest_queue');
}
