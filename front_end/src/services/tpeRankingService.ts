import $axios from '@/http';

export const tpeLevels = ['i', 'e'] as const;
export const tpeStats = [...tpeLevels, 'sum'] as const;
export type TPEStat = typeof tpeStats[number];
export interface TPEVideoRecord {
    value: number;
    video_id: number;
}
export type TPERecord = { player_id: number } & Record<typeof tpeLevels[number], TPEVideoRecord | null>;
export type TPEPlayerRecord = TPERecord & { ranks: Record<TPEStat, number | null> };

export function tpeValue(record: TPERecord | undefined, stat: TPEStat): number | null {
    if (!record) return null;
    if (stat === 'sum') return record.i !== null && record.e !== null ? record.i.value + record.e.value : null;
    return record[stat]?.value ?? null;
}

export function tpeVideoId(record: TPERecord | undefined, stat: TPEStat): number | undefined {
    return stat === 'sum' ? undefined : record?.[stat]?.video_id;
}

export function formatTPEValue(record: TPERecord | undefined, stat: TPEStat): string {
    return tpeValue(record, stat)?.toFixed(3) ?? '--';
}

export async function fetchTPERanking(stat: TPEStat, start: number, end: number, signal?: AbortSignal): Promise<{ count: number; players: TPERecord[] }> {
    const { data } = await $axios.get<{ count: number; players: TPERecord[] }>('/api/effranking/tpe/rank', { params: { stat, start, end }, signal });
    return data;
}

export async function fetchTPERecord(playerId: number): Promise<TPEPlayerRecord> {
    const { data } = await $axios.get<TPEPlayerRecord>(`/api/effranking/tpe/player/${playerId}`);
    return data;
}

export async function rebuildTPERecord(playerId: number, stat: TPEStat): Promise<TPERecord> {
    const { data } = await $axios.post<TPERecord>('/api/effranking/tpe/admin/rebuild_record', { player_id: playerId, stat });
    return data;
}
