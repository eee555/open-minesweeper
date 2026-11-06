import $axios from '@/http';
import { ms_to_s } from '@/utils';

export const StrictNgLevels = ['b', 'i', 'e'] as const;
export type StrictNgLevel = typeof StrictNgLevels[number];
export const StrictNgStat = {
    t: 'time',
    b: 'bvs',
} as const;
export type StrictNgStat = keyof typeof StrictNgStat;
export type StrictNgRankingName = 'strict_ng' | 'strict_ng_nf';
export type StrictNgField = `${StrictNgLevel | 'sum'}${StrictNgStat}`;
export const strictNgFields = ['bt', 'bb', 'it', 'ib', 'et', 'eb', 'sumt', 'sumb'] as const satisfies readonly StrictNgField[];
export type StrictNgRecord = Record<StrictNgField, number | null> & Record<`${StrictNgLevel}${StrictNgStat}_id`, number | null> & { player_id: number };
export type StrictNgPlayerRecord = StrictNgRecord & { ranks: Record<StrictNgField, number | null> };

export function isStrictNgTimeStat(stat: StrictNgField): boolean {
    return stat.endsWith('t');
}

export function formatStrictNgValue(record: StrictNgRecord | undefined, stat: StrictNgField): string {
    const value = record?.[stat];
    if (value == null) return '--';
    return isStrictNgTimeStat(stat) ? ms_to_s(value) : value.toFixed(3);
}

export function strictNgVideoId(record: StrictNgRecord | undefined, stat: StrictNgField): number | undefined {
    if (stat === 'sumt' || stat === 'sumb') return undefined;
    return record?.[`${stat}_id`] ?? undefined;
}

export async function fetchStrictNgRanking(rankingName: StrictNgRankingName, stat: StrictNgField, start: number, end: number): Promise<{ count: number; players: StrictNgRecord[] }> {
    const { data } = await $axios.get<{ count: number; players: StrictNgRecord[] }>('/api/speedranking/strict_ng/rank', {
        params: { ranking_name: rankingName, stat, start, end },
    });
    return data;
}

export async function fetchStrictNgRecords(playerId: number): Promise<Record<StrictNgRankingName, StrictNgPlayerRecord>> {
    const { data } = await $axios.get<Record<StrictNgRankingName, StrictNgPlayerRecord>>(`/api/speedranking/strict_ng/player/${playerId}`);
    return data;
}

export async function rebuildStrictNgRecord(playerId: number, rankingName: StrictNgRankingName, stat: StrictNgField): Promise<StrictNgRecord> {
    const { data } = await $axios.post<StrictNgRecord>('/api/speedranking/strict_ng/admin/rebuild_record', { player_id: playerId, ranking_name: rankingName, stat });
    return data;
}
