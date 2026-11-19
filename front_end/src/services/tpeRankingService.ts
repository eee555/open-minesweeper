import $axios from '@/http';

export const tpeLevels = ['i', 'e'] as const;
export const tpeGroups = [...tpeLevels, 'sum'] as const;
const tpeSuffixes = ['', '2', '3'] as const;
export const tpeColumns = tpeGroups.flatMap((level) => tpeSuffixes.map((suffix) => ({ stat: `${level}${suffix}` as const, level, metric: `TPE${suffix}` })));
export const tpeStats = tpeColumns.map((column) => column.stat);
export type TPEStat = typeof tpeStats[number];
export interface TPEVideoRecord {
    value: number;
    video_id: number;
}
export type TPERecord = { player_id: number } & Record<`${typeof tpeLevels[number]}${typeof tpeSuffixes[number]}`, TPEVideoRecord | null>;
export type TPEPlayerRecord = TPERecord & { ranks: Record<TPEStat, number | null> };

export function tpeValue(record: TPERecord | undefined, stat: TPEStat): number | null {
    if (!record) return null;
    if (stat === 'sum' || stat === 'sum2' || stat === 'sum3') {
        const suffix = stat.slice(3) as typeof tpeSuffixes[number];
        const intermediate = record[`i${suffix}`];
        const expert = record[`e${suffix}`];
        return intermediate != null && expert != null ? intermediate.value + expert.value : null;
    }
    return record[stat]?.value ?? null;
}

export function tpeVideoId(record: TPERecord | undefined, stat: TPEStat): number | undefined {
    return stat === 'sum' || stat === 'sum2' || stat === 'sum3' ? undefined : record?.[stat]?.video_id;
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
