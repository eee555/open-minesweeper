import { columnKey, isFixedColumn } from './columns';
import type { FixedColumnType, VideoColumn } from './columns';

import type { MS_Software } from '@/utils/ms_const';
import { isStandardLevel, MS_Mode, MS_ServerStates, MS_Softwares, MS_State } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';
import { compileVideoExpression, createVideoExpressionContext, evaluateVideoExpression } from '@/utils/videoExpression';

export const CUSTOM_LEVEL_FILTER = 'custom';

export interface VideoListFilters {
    state: string[];
    software: MS_Software[];
    level: string | null;
    mode: string[];
    bool: Record<string, { expr: string; value: boolean }>;
}

export function createVideoListFilters(): VideoListFilters {
    return {
        state: Object.values(MS_State),
        software: [...MS_Softwares],
        level: null,
        mode: Object.values(MS_Mode),
        bool: {},
    };
}

export function isColumnFilterActive(choice: FixedColumnType, filters: VideoListFilters, includeLocal = false): boolean {
    switch (choice) {
        case 'state': {
            const states: readonly string[] = includeLocal ? Object.values(MS_State) : MS_ServerStates;
            return !states.every((state) => filters.state.includes(state));
        }
        case 'software': return !MS_Softwares.every((software) => filters.software.includes(software));
        case 'mode': return !Object.values(MS_Mode).every((mode) => filters.mode.includes(mode));
        case 'level': return filters.level !== null;
        default: return false;
    }
}

function levelMatches(video: VideoAbstract, level: string): boolean {
    if (level === CUSTOM_LEVEL_FILTER) return !isStandardLevel(video.level);
    return video.level === level;
}

export function filterVideos(videos: readonly VideoAbstract[], filters: VideoListFilters): VideoAbstract[] {
    const states = new Set<string>(filters.state);
    const softwares = new Set<string>(filters.software);
    const modes = new Set<string>(filters.mode);
    const boolFilters = Object.values(filters.bool).map((filter) => ({ ...filter, compiled: compileVideoExpression(filter.expr) }));
    return videos.filter((video) => states.has(video.state)
        && softwares.has(video.software)
        && modes.has(video.mode)
        && (filters.level === null || levelMatches(video, filters.level))
        && matchesBoolFilters(video));

    function matchesBoolFilters(video: VideoAbstract): boolean {
        if (boolFilters.length === 0) return true;
        const context = createVideoExpressionContext(video);
        return boolFilters.every((filter) => {
            const result = evaluateVideoExpression(filter.compiled, context);
            return result.error === '' && result.value === filter.value;
        });
    }
}

function compareSortValues(a: number | undefined, b: number | undefined, order: number): number {
    if (a === undefined || !Number.isFinite(a)) return b === undefined || !Number.isFinite(b) ? 0 : 1;
    if (b === undefined || !Number.isFinite(b)) return -1;
    return Math.sign(a - b) * (order < 0 ? -1 : 1);
}

export function sortVideos(videos: readonly VideoAbstract[], order: number | undefined, valueFor: (video: VideoAbstract) => number | undefined): VideoAbstract[] {
    const result = [...videos];
    if (order === undefined || order === 0) return result;
    const decorated = result.map((video, index) => ({ video, index, value: valueFor(video) }));
    decorated.sort((a, b) => compareSortValues(a.value, b.value, order) || a.index - b.index);
    return decorated.map((entry) => entry.video);
}

export function sliceVideos(videos: readonly VideoAbstract[], first: number, rows: number): VideoAbstract[] {
    if (!Number.isFinite(rows) || rows <= 0) return [];
    const start = Number.isFinite(first) ? Math.max(0, Math.floor(first)) : 0;
    return videos.slice(start, start + Math.floor(rows));
}

export interface VideoListColumnConfig {
    sortable: boolean;
    sortField: string;
    cellClass: string;
    filterable: boolean;
    headLabel: boolean;
}

export function columnConfig(column: VideoColumn): VideoListColumnConfig {
    if (column.type === 'bool') return { sortable: false, sortField: columnKey(column), cellClass: 'video-list__col-icon', filterable: true, headLabel: false };
    if (!isFixedColumn(column)) return { sortable: true, sortField: columnKey(column), cellClass: column.type === 'date' ? 'table-col-datetime' : 'table-col-number', filterable: false, headLabel: true };
    const choice = column.type;
    switch (choice) {
        case 'state':
        case 'software':
        case 'level': return { sortable: false, sortField: choice, cellClass: 'video-list__col-icon', filterable: true, headLabel: false };
        case 'mode': return { sortable: false, sortField: 'mode', cellClass: 'table-col-mode', filterable: true, headLabel: false };
        case 'player': return { sortable: false, sortField: 'player', cellClass: 'table-col-player', filterable: false, headLabel: true };
    }
}
