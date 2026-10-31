import $axios from '@/http';
import { ms_to_s } from '@/utils';

export const nfIOELevels = ['b', 'i', 'e'] as const;
export const nfIOEStats = [...nfIOELevels, 'sum'] as const;
export type NFIOEStat = typeof nfIOEStats[number];
export interface NFIOEVideoRecord {
    value: number;
    video_id: number;
    timems: number;
}
export type NFIOERecord = { player_id: number } & Record<typeof nfIOELevels[number], NFIOEVideoRecord | null>;

export function nfIOEValue(record: NFIOERecord, stat: NFIOEStat): number | null {
    return stat === 'sum' ? nfIOELevels.reduce((sum, level) => sum + (record[level]?.value ?? 0), 0) : record[stat]?.value ?? null;
}

export function nfIOEVideoId(record: NFIOERecord, stat: NFIOEStat): number | undefined {
    return stat === 'sum' ? undefined : record[stat]?.video_id;
}

export function formatNFIOEValue(record: NFIOERecord, stat: NFIOEStat): string {
    const value = nfIOEValue(record, stat);
    const part = stat === 'sum' ? record.e : record[stat];
    const perfect = value === (stat === 'sum' ? 3 : 1);
    return `${value?.toFixed(3) ?? '--'}${perfect && part ? ` (${ms_to_s(part.timems)})` : ''}`;
}

export async function fetchNFIOERanking(stat: NFIOEStat, start: number, end: number, signal?: AbortSignal): Promise<{ count: number; players: NFIOERecord[] }> {
    const { data } = await $axios.get<{ count: number; players: NFIOERecord[] }>('/api/effranking/nf_ioe/rank', { params: { stat, start, end }, signal });
    return data;
}

export async function rebuildNFIOERecord(playerId: number, stat: NFIOEStat): Promise<NFIOERecord> {
    const { data } = await $axios.post<NFIOERecord>('/api/effranking/nf_ioe/admin/rebuild_record', { player_id: playerId, stat });
    return data;
}
