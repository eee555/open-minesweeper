import $axios from '@/http';

export interface NewsRankRecord {
    timems: number;
    video_id: number;
    rank: number | null;
}

export interface NewsValue {
    lsf: number;
    rank: number | null;
}

export interface PBNewsPayload {
    field: string;
    old: NewsRankRecord | null;
    new: NewsRankRecord;
}

export interface LSFNewsPayload {
    video_id: number | null;
    video_ids: number[];
    old: NewsValue | null;
    new: NewsValue;
}

interface NewsEventBase {
    id: string;
    occurred_at: number;
    player_id: number;
}

type PBNewsEvent = NewsEventBase & { category: 'pb'; payload: PBNewsPayload };
type LSFNewsEvent = NewsEventBase & { category: 'lsf'; payload: LSFNewsPayload };
export type NewsEvent = PBNewsEvent | LSFNewsEvent;

export type NewsCategory = 'all' | 'pb' | 'lsf';

export async function fetchNews(category: NewsCategory = 'all', limit = 50): Promise<NewsEvent[]> {
    const { data } = await $axios.get<NewsEvent[]>('/api/news/events', { params: { category, limit } });
    return data;
}
