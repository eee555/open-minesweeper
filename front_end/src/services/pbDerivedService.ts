import $axios from '@/http';
import type { PBPlayerRecord } from '@/services/pbRankingService';
import type { MS_Level } from '@/utils/ms_const';

export type DerivedRankingName = 'collection' | 'skill' | 'typical_time';
export type DerivedMode = 'std' | 'nf';
export type DerivedLevel = MS_Level | 'sum';
export type DerivedMetric = 'count' | 'probability' | 'asb';
export type DerivedDisplayMetric = DerivedMetric | 'skill' | 'tt';
export type DerivedRecords = Record<string, number>;
export type DerivedRanks = Record<string, number | null>;
export type DerivedRecordsByRanking = Partial<Record<DerivedRankingName, DerivedRecords>>;
export type DerivedRecordsMap = Record<DerivedRankingName, DerivedRecords>;
export type DerivedRanksMap = Record<DerivedRankingName, DerivedRanks>;

export interface DerivedSegment {
    field: string;
    start: number;
    end: number;
}

export interface DerivedRankingRow {
    player_id: number;
    records: DerivedRecordsByRanking;
}

export interface DerivedRankingResponse {
    count: number;
    rows: DerivedRankingRow[];
}

export interface DerivedSummaryResponse {
    pb: PBPlayerRecord[];
    records: DerivedRecordsMap;
    ranks: DerivedRanksMap;
}

export interface DerivedColumn {
    ranking: DerivedRankingName;
    field: string;
    sort: string;
    metric: DerivedDisplayMetric;
    level: DerivedLevel;
    label: string;
    group?: string;
    color: 'none' | 'bvs' | 'bvs-third' | 'time';
}

export const derivedLevels = ['b', 'i', 'e'] as const;
export const derivedCollectionKeys = ['b:count', 'b:probability', 'b:asb', 'i:count', 'i:probability', 'i:asb', 'e:count', 'e:probability', 'e:asb', 'sum:count', 'sum:probability', 'sum:asb'] as const;
export const derivedOverviewKeys = ['skill:b:total', 'skill:i:total', 'skill:e:total', 'skill:sum:total', 'typical_time:b:total', 'typical_time:i:total', 'typical_time:e:total', 'typical_time:sum:total'] as const;
export const derivedPages = ['overview', 'skill_b', 'skill_i', 'skill_e', 'tt_b', 'tt_i', 'tt_e'] as const;
export type DerivedPage = typeof derivedPages[number];

// 与后端 pb_derived/utils.py 的 SEGMENTS 同步维护；端点均包含在内，BV 0 不属于任何分段。
export const derivedSegments: Record<MS_Level, DerivedSegment[]> = {
    b: [
        { field: 's1', start: 1, end: 9 },
        { field: 's2', start: 10, end: 19 },
        { field: 's3', start: 20, end: 29 },
        { field: 's4', start: 30, end: 54 },
    ],
    i: [
        { field: 's1', start: 1, end: 39 },
        { field: 's2', start: 40, end: 49 },
        { field: 's3', start: 50, end: 59 },
        { field: 's4', start: 60, end: 69 },
        { field: 's5', start: 70, end: 79 },
        { field: 's6', start: 80, end: 89 },
        { field: 's7', start: 90, end: 99 },
        { field: 's8', start: 100, end: 216 },
    ],
    e: [
        { field: 's1', start: 1, end: 129 },
        { field: 's2', start: 130, end: 139 },
        { field: 's3', start: 140, end: 149 },
        { field: 's4', start: 150, end: 159 },
        { field: 's5', start: 160, end: 169 },
        { field: 's6', start: 170, end: 179 },
        { field: 's7', start: 180, end: 189 },
        { field: 's8', start: 190, end: 199 },
        { field: 's9', start: 200, end: 209 },
        { field: 's10', start: 210, end: 219 },
        { field: 's11', start: 220, end: 381 },
    ],
};

export function modeKey(nf: boolean): DerivedMode {
    return nf ? 'nf' : 'std';
}

export function derivedField(mode: DerivedMode, key: string): string {
    return `${mode}:${key}`;
}

export function derivedSort(ranking: DerivedRankingName, key: string): string {
    return `${ranking}:${key}`;
}

function segmentSortKeys(ranking: 'skill' | 'typical_time'): string[] {
    return [
        ...derivedLevels.flatMap((level) => derivedSegments[level].map((segment) => derivedSort(ranking, `${level}:${segment.field}`))),
        ...derivedLevels.map((level) => derivedSort(ranking, `${level}:total`)),
        derivedSort(ranking, 'sum:total'),
    ];
}

export const derivedSkillTTSortKeys: readonly string[] = [...segmentSortKeys('skill'), ...segmentSortKeys('typical_time')];

export function parseDerivedSort(sort: string, nf: boolean): { ranking: DerivedRankingName; field: string } {
    const [ranking, ...parts] = sort.split(':');
    return { ranking: ranking as DerivedRankingName, field: derivedField(modeKey(nf), parts.join(':')) };
}

export function defaultDerivedSort(page: DerivedPage): string {
    if (page === 'overview') return derivedSort('skill', 'sum:total');
    const [kind, level] = page.split('_');
    return derivedSort(kind === 'skill' ? 'skill' : 'typical_time', `${level}:total`);
}

export async function fetchDerivedRanking(ranking: DerivedRankingName, field: string, start: number, end: number, signal?: AbortSignal): Promise<DerivedRankingResponse> {
    const { data } = await $axios.get<DerivedRankingResponse>('/api/speedranking/pb_derived/rank', {
        params: { ranking, field, start, end }, signal,
    });
    return data;
}

export async function fetchDerivedSummary(playerId: number, signal?: AbortSignal): Promise<DerivedSummaryResponse> {
    const { data } = await $axios.get<DerivedSummaryResponse>('/api/speedranking/pb_derived/summary', {
        params: { player_id: playerId }, signal,
    });
    return data;
}

export async function rebuildDerivedPlayer(playerId: number): Promise<{ player_id: number; fields: number }> {
    const { data } = await $axios.post<{ player_id: number; fields: number }>('/api/speedranking/pb_derived/admin/rebuild_player', { player_id: playerId });
    return data;
}

export function formatDerivedCount(value: number | undefined): string {
    return value === undefined ? '--' : String(Math.round(value));
}

export function formatDerivedNumber(value: number | undefined): string {
    return value === undefined ? '--' : value.toFixed(3);
}

export function formatDerivedPercent(value: number | undefined): string {
    if (value === undefined) return '--';
    if (value <= 0) return '0%';
    // 单级别概率上限为 1，三级别合计上限为 3；按更靠近边界的一侧保留 3 位有效数字，再还原成原概率。
    const bound = value <= 1 ? 1 : 3;
    if (value >= bound) return `${Number((value * 100).toPrecision(12))}%`;
    const distance = Number(Math.min(value, bound - value).toPrecision(12));
    const scale = 10 ** (2 - Math.floor(Math.log10(distance)));
    const rounded = Math.round(distance * scale) / scale;
    const shown = value <= bound - value ? rounded : bound - rounded;
    return `${Number((shown * 100).toPrecision(12))}%`;
}

export function formatDerivedValue(metric: DerivedDisplayMetric, value: number | undefined): string {
    if (metric === 'count') return formatDerivedCount(value);
    if (metric === 'probability') return formatDerivedPercent(value);
    return formatDerivedNumber(value);
}

export function derivedTitle(metric: DerivedDisplayMetric, value: number | undefined): string {
    if (value === undefined) return '--';
    return metric === 'count' ? String(Math.round(value)) : String(value);
}

export function formatRank(rank: number | null | undefined): string {
    return rank === null || rank === undefined ? '--' : String(rank);
}

export function formatWithRank(value: number | undefined, metric: DerivedDisplayMetric, rank: number | null | undefined): string {
    return `${formatDerivedValue(metric, value)}(${formatRank(rank)})`;
}
