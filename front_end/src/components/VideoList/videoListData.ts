import type { ColumnChoice, MS_Software } from '@/utils/ms_const';
import { isStandardLevel, MS_Mode, MS_ServerStates, MS_Softwares, MS_State } from '@/utils/ms_const';
import { getStat_keys } from '@/utils/videoabstract';
import type { getStat_stat, VideoAbstract } from '@/utils/videoabstract';

export const CUSTOM_LEVEL_FILTER = 'custom';

export interface VideoListFilters {
    state: string[];
    software: MS_Software[];
    level: string | null;
    mode: string[];
}

export function createVideoListFilters(): VideoListFilters {
    return {
        state: Object.values(MS_State),
        software: [...MS_Softwares],
        level: null,
        mode: Object.values(MS_Mode),
    };
}

export function isColumnFilterActive(choice: ColumnChoice, filters: VideoListFilters, includeLocal = false): boolean {
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
    return videos.filter((video) => states.has(video.state)
        && softwares.has(video.software)
        && modes.has(video.mode)
        && (filters.level === null || levelMatches(video, filters.level)));
}

export function isStatKey(field: string): field is getStat_stat {
    return (getStat_keys as readonly string[]).includes(field);
}

export type SortValue = number | string | Date | null | undefined;

export function sortValue(video: VideoAbstract, field: string): SortValue {
    switch (field) {
        case 'upload_time': return video.upload_time;
        case 'end_time': return video.end_time;
        case 'state': return video.state;
        case 'software': return video.software;
        case 'mode': return video.mode;
        case 'level': return isStandardLevel(video.level) ? video.level : video.level.code;
        case 'player': return video.player_id;
        case 'file_size': return video.file_size;
        default: {
            if (!isStatKey(field)) return undefined;
            const value: unknown = video[field];
            return typeof value === 'number' ? value : undefined;
        }
    }
}

export function isMissingSortValue(value: SortValue): boolean {
    if (value === undefined || value === null) return true;
    if (typeof value === 'number') return !Number.isFinite(value);
    if (value instanceof Date) return !Number.isFinite(value.getTime());
    return false;
}

function compareDefinedValues(a: SortValue, b: SortValue): number {
    if (typeof a === 'number' && typeof b === 'number') return Math.sign(a - b);
    if (a instanceof Date && b instanceof Date) return Math.sign(a.getTime() - b.getTime());
    return String(a).localeCompare(String(b));
}

export function compareSortValues(a: SortValue, b: SortValue, order: number): number {
    const aMissing = isMissingSortValue(a);
    const bMissing = isMissingSortValue(b);
    if (aMissing !== bMissing) return aMissing ? 1 : -1;
    if (aMissing) return 0;
    return compareDefinedValues(a, b) * (order < 0 ? -1 : 1);
}

export function sortVideos(videos: readonly VideoAbstract[], field: string, order: number | undefined): VideoAbstract[] {
    const result = [...videos];
    if (order === undefined || order === 0 || field === '') return result;
    const decorated = result.map((video, index) => ({ video, index, value: sortValue(video, field) }));
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

export function columnConfig(choice: ColumnChoice): VideoListColumnConfig {
    switch (choice) {
        case 'state': return { sortable: false, sortField: 'state', cellClass: 'video-list__col-icon', filterable: true, headLabel: false };
        case 'software': return { sortable: false, sortField: 'software', cellClass: 'video-list__col-icon', filterable: true, headLabel: false };
        case 'mode': return { sortable: false, sortField: 'mode', cellClass: 'table-col-mode', filterable: true, headLabel: false };
        case 'level': return { sortable: false, sortField: 'level', cellClass: 'video-list__col-icon', filterable: true, headLabel: false };
        case 'player': return { sortable: false, sortField: 'player', cellClass: 'table-col-player', filterable: false, headLabel: true };
        case 'upload_time': return { sortable: true, sortField: 'upload_time', cellClass: 'table-col-datetime', filterable: false, headLabel: true };
        case 'end_time': return { sortable: true, sortField: 'end_time', cellClass: 'table-col-datetime', filterable: false, headLabel: true };
        case 'file_size': return { sortable: true, sortField: 'file_size', cellClass: 'table-col-number', filterable: false, headLabel: true };
        default: return { sortable: true, sortField: choice, cellClass: 'table-col-number', filterable: false, headLabel: true };
    }
}
