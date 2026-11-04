import type { MS_Level } from '../ms_const';

export interface AccountSaoleiResponse {
    id: number;
    parent: number;
    update_time: string;
    name: string;
    banned: boolean;
    auto_sync: boolean;
    video_sync_cursor: number;
    video_update_time: string | null;
}

export class AccountSaolei {
    public id = 0;
    public parent = 0;
    public name = '';
    public banned = false;
    public auto_sync = true;
    public update_time = new Date(0);
    public video_sync_cursor = 0;
    public video_update_time: Date | null = null;

    public constructor(data?: AccountSaoleiResponse) {
        if (data === undefined) return;
        this.id = data.id;
        this.parent = data.parent;
        this.name = data.name;
        this.banned = data.banned;
        this.auto_sync = data.auto_sync;
        this.update_time = new Date(data.update_time);
        this.video_sync_cursor = data.video_sync_cursor;
        this.video_update_time = data.video_update_time === null ? null : new Date(data.video_update_time);
    }
}

export interface SaoleiVideo {
    id: number;
    remote_id: number;
    level: MS_Level;
    timems: number;
    bv: number;
    nf: boolean;
    software: string;
    status: number;
    upload_time: string;
    import_video: number | null;
    import_rejected: boolean;
}

export interface SaoleiImportSummary {
    total: number;
    imported: number;
    pending: number;
    rejected: number;
    skipped: number;
    auto_sync: boolean;
    video_sync_cursor: number;
    video_update_time: string | null;
}

export const SaoleiImportSummaryDefault: SaoleiImportSummary = {
    total: 0,
    imported: 0,
    pending: 0,
    rejected: 0,
    skipped: 0,
    auto_sync: true,
    video_sync_cursor: 0,
    video_update_time: null,
};
