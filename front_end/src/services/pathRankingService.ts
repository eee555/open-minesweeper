import $axios from '@/http';

export const pathLevels = ['b', 'i', 'e'] as const;
export const pathGroups = [...pathLevels, 'sum'] as const;
export const pathMetrics = ['path', 'cpath', 'epath'] as const;
const labels = { path: 'Path', cpath: 'CPath', epath: 'EPath' } as const;
export const pathColumns = pathGroups.flatMap((level) => pathMetrics.map((metric) => ({ stat: `${level}_${metric}` as const, level, metric, label: labels[metric] })));
export const pathStats = pathColumns.map((column) => column.stat);
export type PathStat = typeof pathStats[number];
export interface PathVideoRecord {
    value: number;
    video_id: number;
}
export type PathRecord = { player_id: number } & Record<`${typeof pathLevels[number]}_${typeof pathMetrics[number]}`, PathVideoRecord | null>;
export type PathPlayerRecord = PathRecord & { ranks: Record<PathStat, number | null> };

function isSum(stat: PathStat): stat is `sum_${typeof pathMetrics[number]}` {
    return stat.startsWith('sum_');
}

export function pathValue(record: PathRecord | undefined, stat: PathStat): number | null {
    if (!record) return null;
    if (isSum(stat)) {
        const metric = stat.slice(4) as typeof pathMetrics[number];
        const values = pathLevels.map((level) => record[`${level}_${metric}`]?.value ?? null);
        return values.every((value) => value !== null) ? values.reduce((sum, value) => sum + value, 0) : null;
    }
    return record[stat]?.value ?? null;
}

export function pathVideoId(record: PathRecord | undefined, stat: PathStat): number | undefined {
    return isSum(stat) ? undefined : record?.[stat]?.video_id;
}

export function formatPathValue(record: PathRecord | undefined, stat: PathStat): string {
    return pathValue(record, stat)?.toFixed(3) ?? '--';
}

export async function fetchPathRanking(stat: PathStat, start: number, end: number, signal?: AbortSignal): Promise<{ count: number; players: PathRecord[] }> {
    const { data } = await $axios.get<{ count: number; players: PathRecord[] }>('/api/effranking/path/rank', { params: { stat, start, end }, signal });
    return data;
}

export async function fetchPathRecord(playerId: number): Promise<PathPlayerRecord> {
    const { data } = await $axios.get<PathPlayerRecord>(`/api/effranking/path/player/${playerId}`);
    return data;
}

export async function rebuildPathRecord(playerId: number, stat: PathStat): Promise<PathRecord> {
    const { data } = await $axios.post<PathRecord>('/api/effranking/path/admin/rebuild_record', { player_id: playerId, stat });
    return data;
}
