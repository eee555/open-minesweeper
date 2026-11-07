import $axios from '@/http';
import { ms_to_s } from '@/utils';

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

export interface EffNewsRecord {
    value: number;
    video_id: number | null;
    rank: number | null;
    count: number | null;
    timems: number | null;
}

export interface EffNewsPayload {
    field: string;
    old: EffNewsRecord | null;
    new: EffNewsRecord;
}

interface NewsEventBase {
    id: string;
    occurred_at: number;
    player_id: number;
}

type PBNewsEvent = NewsEventBase & { category: 'pb'; payload: PBNewsPayload };
type LSFNewsEvent = NewsEventBase & { category: 'lsf'; payload: LSFNewsPayload };
type EffNewsEvent = NewsEventBase & { category: 'eff'; payload: EffNewsPayload };
export type NewsEvent = PBNewsEvent | LSFNewsEvent | EffNewsEvent;

export type NewsCategory = 'all' | 'pb' | 'lsf' | 'eff';

export function formatEffValue(record: EffNewsRecord, field: string): string {
    const [ranking, stat] = field.split(':');
    const formatted = record.value.toFixed(3);
    if (ranking === 'thrp' && stat === 'e_nf' && (record.count ?? 0) > 1) return `1 x ${record.count}`;
    if (ranking === 'nf_ioe' && record.timems !== null && record.value === (stat === 'sum' ? 3 : 1)) {
        return `${formatted} (${ms_to_s(record.timems)})`;
    }
    return formatted;
}

export async function fetchNews(category: NewsCategory = 'all', limit = 50): Promise<NewsEvent[]> {
    const { data } = await $axios.get<NewsEvent[]>('/api/news/events', { params: { category, limit } });
    return data;
}
