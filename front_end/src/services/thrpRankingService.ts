import $axios from '@/http';

export const thrpLevels = ['b', 'i', 'e'] as const;
export type ThrpLevel = typeof thrpLevels[number];
export const thrpStats = [...thrpLevels, 'sum', 'e_nf'] as const;
export type ThrpStat = typeof thrpStats[number];

export interface ThrpVideoRecord {
    value: number;
    video_id: number;
    upload_time: string;
}
export interface ThrpNFRecord {
    value: number;
    video_ids: number[];
}
export type ThrpRecord = { player_id: number; e_nf: ThrpNFRecord | null } & Record<ThrpLevel, ThrpVideoRecord | null>;
export type ThrpPlayerRecord = ThrpRecord & { ranks: Record<ThrpStat, number | null> };

export function thrpValue(record: ThrpRecord, stat: ThrpStat): number | null {
    return stat === 'sum' ? thrpLevels.reduce((sum, level) => sum + (record[level]?.value ?? 0), 0) : record[stat]?.value ?? null;
}

export function thrpVideoId(record: ThrpRecord, stat: ThrpStat): number | undefined {
    if (stat === 'sum') return undefined;
    return stat === 'e_nf' ? record.e_nf?.video_ids[0] : record[stat]?.video_id;
}

export function formatThrpValue(record: ThrpRecord | undefined, stat: ThrpStat): string {
    const value = record ? thrpValue(record, stat) : null;
    const formatted = value?.toFixed(3) ?? '--';
    const count = record?.e_nf?.video_ids.length ?? 0;
    return stat === 'e_nf' && count > 1 ? `1 x ${count}` : formatted;
}

export async function fetchThrpRanking(stat: ThrpStat, start: number, end: number, signal?: AbortSignal): Promise<{ count: number; players: ThrpRecord[] }> {
    const { data } = await $axios.get<{ count: number; players: ThrpRecord[] }>('/api/effranking/thrp/rank', { params: { stat, start, end }, signal });
    return data;
}

export async function fetchThrpRecord(playerId: number): Promise<ThrpPlayerRecord> {
    const { data } = await $axios.get<ThrpPlayerRecord>(`/api/effranking/thrp/player/${playerId}`);
    return data;
}

export async function rebuildThrpRecord(playerId: number, stat: ThrpStat): Promise<ThrpRecord> {
    const { data } = await $axios.post<ThrpRecord>('/api/effranking/thrp/admin/rebuild_record', { player_id: playerId, stat });
    return data;
}
