import { isRankingRefreshError } from '@/components/Notifications';
import { uploadVideoFile } from '@/services/videoUploadService';
import { sleep } from '@/utils';
import type { CustomLevel } from '@/utils/customlevel';
import type { AnyVideo } from '@/utils/fileIO';
import { extract_stat, fileHash, load_video_file } from '@/utils/fileIO';
import { MS_State } from '@/utils/ms_const';
import { getFileExtension } from '@/utils/strings';
import type { VideoAbstract } from '@/utils/videoabstract';

export const UploadStatus = ['parse', 'pass', 'filename', 'filesize', 'fileext', 'custom', 'invalid', 'identifier', 'needApprove', 'censorship', 'collision', 'identity', 'quota', 'upload', 'process', 'success', 'incomplete'] as const;
export type UploadStatus = typeof UploadStatus[number];

export interface UploadEntry {
    hash: string;
    file: File;
    status: UploadStatus;
    stat?: VideoAbstract; // for display
    video?: AnyVideo;
}

export interface ParserProgress {
    total: number;
    parsed: number;
}

export interface UploadProgress {
    total: number;
    uploaded: number;
    failed: number;
}

export function fileCollide(e1: UploadEntry, e2: UploadEntry): boolean {
    return e1.hash === e2.hash && getFileExtension(e1.file.name) === getFileExtension(e2.file.name);
}

export function isUploadableStatus(status: UploadStatus): boolean {
    return (['pass', 'needApprove'] as UploadStatus[]).includes(status);
}

const stateToUploadStatus = {
    [MS_State.Official]: 'success',
    [MS_State.Identifier]: 'identifier',
    [MS_State.Plain]: 'needApprove',
    [MS_State.Frozen]: 'invalid',
} as const;

export async function prepareUploadEntry(file: File): Promise<UploadEntry> {
    const buffer = await file.arrayBuffer();
    const hash = await fileHash(buffer);
    let status: UploadStatus = 'pass';
    if (file.size > 5 * 1024 * 1024) status = 'filesize';
    else if (file.name.length >= 100) status = 'filename';
    else if (!['avf', 'evf', 'rmv', 'mvf'].includes(getFileExtension(file.name))) status = 'fileext';
    if (status !== 'pass') {
        return { hash, file, status };
    }

    let video: AnyVideo;
    try {
        video = load_video_file(buffer, file.name);
    } catch {
        return { hash, file, status: 'parse' };
    }

    const stat = extract_stat(video);

    if (!video.is_completed) status = 'incomplete';
    else if (video.level === 6 && !(stat.level as CustomLevel).isSupported) status = 'custom';
    else if (video.is_valid() == 1) status = 'invalid';
    else if (video.is_valid() == 3) status = 'needApprove';

    return { hash, file, status, stat, video };
}

export async function uploadEntry(entry: UploadEntry, delayMs = 0): Promise<UploadEntry> {
    if (!isUploadableStatus(entry.status)) {
        return entry;
    }
    const previousStatus = entry.status;
    entry.status = 'process';
    if (entry.stat === undefined) {
        entry.status = 'upload';
        return entry;
    }
    if (delayMs > 0) await sleep(delayMs);
    try {
        const result = await uploadVideoFile(entry.file);
        if (result.type === 'success') {
            entry.stat.id = result.id;
            entry.stat.state = result.state;
            entry.stat.upload_time = new Date(Date.now());
            entry.status = stateToUploadStatus[result.state];
        } else {
            entry.status = result.status;
        }
    } catch (error) {
        entry.status = isRankingRefreshError(error) ? previousStatus : 'upload';
        throw error;
    }
    return entry;
}
