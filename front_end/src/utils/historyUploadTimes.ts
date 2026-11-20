import { HistoryImportError } from './historyImportError';

export interface HistoryReplayTime {
    endTime: Date;
    timems: number;
}

export function assignHistoryUploadTimes<T extends HistoryReplayTime>(videos: T[], anchor: Date): (T & { uploadTime: Date })[] {
    if (!Number.isFinite(anchor.getTime())) throw new HistoryImportError('uploadTime', 'Invalid upload time');
    for (const video of videos) {
        if (!Number.isFinite(video.endTime?.getTime()) || !Number.isSafeInteger(video.timems) || video.timems <= 0) throw new HistoryImportError('duration', 'Invalid replay end time or duration');
    }
    const sorted = [...videos].sort((a, b) => a.endTime.getTime() - b.endTime.getTime());
    const result: (T & { uploadTime: Date })[] = [];
    let time = anchor.getTime();
    for (let i = sorted.length - 1; i >= 0; i--) {
        result.unshift({ ...sorted[i], uploadTime: new Date(time) });
        time -= sorted[i].timems;
        if (!Number.isFinite(new Date(time).getTime())) throw new HistoryImportError('range', 'Upload time out of range');
    }
    return result;
}
