import type { MS_Level } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';
import { groupVideosByBBBv, groupVideosByDate } from '@/utils/videoabstract';

export type VideoSelection = { kind: 'all' } | { kind: 'date'; dateKey: string } | { kind: 'bv'; level: MS_Level; bv: number };
export function selectProfileVideos(videos: VideoAbstract[], selection: VideoSelection, useEndTime = false): VideoAbstract[] {
    if (selection.kind === 'date') return groupVideosByDate(videos, useEndTime ? 'end_time' : 'upload_time').get(selection.dateKey) ?? [];
    if (selection.kind === 'bv') return groupVideosByBBBv(videos, selection.level).get(selection.bv) ?? [];
    return videos;
}
