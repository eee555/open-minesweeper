/* eslint-disable @typescript-eslint/member-ordering */
import { CustomLevel } from './customlevel';
import { toDate, toISODateString } from './datetime';
import type { MS_Level, MS_Mode, MS_Software } from './ms_const';
import { isStandardLevel, MS_State } from './ms_const';
import { STNB_COEFFICIENTS } from './stnb';
import { formatBytes } from './strings';

type VideoLevel = MS_Level | CustomLevel;
export type StandardVideoAbstract = VideoAbstract & { level: MS_Level };

export interface VideoAbstractInfo {
    id: number;
    upload_time: string | Date;
    end_time: Date | null;
    level: VideoLevel;
    mode: MS_Mode;
    timems: number;
    bv: number;
    state: string;
    software: string;
    cl: number | null;
    ce: number | null;
    right_ce?: number | null;
    file_size: number;
    pluck: number | null;
}

export interface VideoRedisInfo {
    state: string;
    software: string;
    time: string;
    player_id: number;
    level: VideoLevel;
    mode: MS_Mode;
    timems: number;
    bv: number;
    identifier: string;
    cl?: number;
    ce?: number;
    right_ce?: number | null;
}

export interface VideoAbstractData {
    id?: number;
    upload_time?: string | Date;
    time?: string | Date;
    end_time?: string | Date | null;
    level: string | CustomLevel;
    mode: MS_Mode;
    timems: number;
    bv: number;
    state?: string;
    software: string;
    cl?: number | null;
    ce?: number | null;
    right_ce?: number | null;
    path?: number | null;
    pluck?: number | null;
    player_id?: number;
    player?: number;
    file_size?: number;
    ongoing_tournament?: boolean;
}

export const getStat_keys = ['time', 'bvs', 'timems', 'bv', 'qg', 'rqp', 'stnb', 'ce', 'ces', 'cl', 'cls', 'ioe', 'thrp', 'corr', 'path', 'pluck', 'npath', 'mov', 'iome', 'file_size'] as const;
export type getStat_stat = typeof getStat_keys[number];

export class VideoAbstract {
    public id = 0;
    public upload_time = new Date();
    public end_time?: Date;
    public level: VideoLevel;
    public mode: MS_Mode;
    public timems: number;
    public bv: number;
    public state: MS_State = MS_State.Plain;
    public software: MS_Software;
    public cl = NaN;
    public ce = NaN;
    public right_ce = NaN;
    public path = NaN;
    public pluck = NaN;
    public player_id?: number;
    public file_size = 0;
    public ongoing_tournament?: boolean;

    public constructor(info: VideoAbstractData) {
        this.id = info.id ?? this.id;

        const uploadTime = info.upload_time ?? info.time;
        if (uploadTime !== undefined) this.upload_time = new Date(uploadTime);

        this.end_time = toDate(info.end_time);

        this.level = parseLevel(info.level);
        this.mode = info.mode;
        this.timems = info.timems;
        this.bv = info.bv;
        if (info.state !== undefined) this.state = info.state as MS_State;
        this.software = info.software as MS_Software;

        this.cl = info.cl ?? NaN;
        this.ce = info.ce ?? NaN;
        this.right_ce = info.right_ce ?? NaN;
        this.path = info.path ?? NaN;
        this.pluck = info.pluck ?? NaN;
        this.player_id = info.player_id ?? info.player;

        this.file_size = info.file_size ?? this.file_size;

        this.ongoing_tournament = info.ongoing_tournament ?? undefined;
    }

    public static fromVideoRedisInfo(key: number, info: VideoRedisInfo): VideoAbstract {
        return new VideoAbstract({
            id: key,
            upload_time: new Date(info.time),
            level: info.level,
            mode: info.mode,
            timems: info.timems,
            bv: info.bv,
            state: info.state,
            software: info.software,
            player_id: info.player_id,
            cl: info.cl,
            ce: info.ce,
            right_ce: info.right_ce,
        });
    }

    public static fromArbiterCsv(info: VideoAbstractData & { end_time: Date }): VideoAbstract {
        return new VideoAbstract({ ...info, id: 0, state: MS_State.Local, software: 'a', mode: '00', upload_time: info.end_time, file_size: NaN });
    }

    public get isLocal(): boolean {
        return this.state === MS_State.Local;
    }

    public get rowKey(): string {
        return this.isLocal ? `local:${Math.floor((this.end_time ?? this.upload_time).getTime() / 1000)}:${this.timems}` : `server:${this.id}`;
    }

    public get isNF(): boolean {
        return this.right_ce === 0;
    }

    public get time(): number {
        return this.timems / 1000;
    }

    public get bvs(): number {
        return this.bv / this.time;
    }

    public get qg(): number {
        return Math.pow(this.time, 1.7) / this.bv;
    }

    public get rqp(): number {
        return this.time * (this.time - 1) / this.bv;
    }

    public get stnb(): number {
        if (!isStandardLevel(this.level)) return NaN;
        return STNB_COEFFICIENTS[this.level] / this.qg;
    }

    public get ioe(): number {
        return this.bv / this.cl;
    }

    public get thrp(): number {
        return this.bv / this.ce;
    }

    public get corr(): number {
        return this.ce / this.cl;
    }

    public get cls(): number {
        return this.cl / this.time;
    }

    public get ces(): number {
        return this.ce / this.time;
    }

    public get npath(): number {
        return this.path / 16;
    }

    public get mov(): number {
        return this.npath / this.time;
    }

    public get iome(): number {
        return this.bv / this.npath;
    }

    public displayStat(stat: getStat_stat): string {
        if (this.isLocal && !Number.isFinite(this[stat])) return '—';
        switch (stat) {
            case 'timems':
            case 'time': return this.time.toFixed(3);
            case 'bvs': return this.bvs.toFixed(3);
            case 'bv': return this.bv.toString();
            case 'qg': return this.qg.toFixed(3);
            case 'rqp': return this.rqp.toFixed(3);
            case 'stnb': return this.stnb.toFixed(1);
            case 'ce': return this.ce.toString();
            case 'ces': return this.ces.toFixed(3);
            case 'cl': return this.cl.toString();
            case 'cls': return this.cls.toFixed(3);
            case 'ioe': return this.ioe.toFixed(3);
            case 'thrp': return this.thrp.toFixed(3);
            case 'corr': return this.corr.toFixed(3);
            case 'path': return this.path.toFixed(0);
            case 'pluck': return this.pluck.toFixed(3);
            case 'npath': return this.npath.toFixed(1);
            case 'mov': return this.mov.toFixed(3);
            case 'iome': return this.iome.toFixed(3);
            case 'file_size': return formatBytes(this.file_size);
        }
    }
}

function parseLevel(level: string | CustomLevel): VideoLevel {
    if (typeof level !== 'string') return level;
    const customLevel = CustomLevel.fromCode(level);
    return customLevel ?? level as MS_Level;
}

export function groupVideosByDate(videos: VideoAbstract[], attr: 'upload_time' | 'end_time' = 'upload_time'): Map<string, VideoAbstract[]> {
    const result = new Map<string, VideoAbstract[]>();

    videos.forEach((video) => {
        let date = video[attr];
        date ??= video.upload_time; // fallback to upload_time if end_time is not available
        const dateKey = toISODateString(date); // Extract date part as string (YYYY-MM-DD)
        if (!result.has(dateKey)) {
            result.set(dateKey, []);
        }
        result.get(dateKey)?.push(video);
    });

    return result;
}

export function groupVideosByBBBv(videos: VideoAbstract[], level: MS_Level): Map<number, VideoAbstract[]> {
    const result = new Map<number, VideoAbstract[]>();

    videos.forEach((video) => {
        if (video.level !== level) {
            return;
        }
        const bbbv = video.bv;
        if (video.isLocal && !Number.isFinite(bbbv)) return;
        if (!result.has(bbbv)) {
            result.set(bbbv, []);
        }
        result.get(bbbv)?.push(video);
    });

    return result;
}

export function isStandardVideo(video: VideoAbstract): video is StandardVideoAbstract {
    return isStandardLevel(video.level);
}
