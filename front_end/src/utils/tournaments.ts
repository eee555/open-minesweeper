import { toDate, toISODateTimeString } from './datetime';
import { TournamentState, TournamentSubclass } from './ms_const';
import type { VideoAbstract } from './videoabstract';

export class TournamentParticipant {
    public id = 0;
    public token = '';
    public arbiter_identifier__identifier?: string;
    public tournament_id = 0;
    public user_id = 0;
    public start_time?: Date;
    public end_time?: Date;
    public rank?: number;
    public rank_score = 0;
    public has_videos = false;
    protected _videos?: VideoAbstract[];

    public constructor(init: Partial<TournamentParticipant> = {}) {
        Object.assign(this, init);
    }

    public get videos(): VideoAbstract[] | undefined {
        return this._videos;
    }

    public set videos(videos: VideoAbstract[] | undefined) {
        this._videos = videos;
        if (videos !== undefined) this.has_videos = videos.length > 0;
    }

    public addVideo(video: VideoAbstract): void {
        this.has_videos = true;
        if (this._videos === undefined) this._videos = [video];
        else this._videos.push(video);
    }
}

type LocalizedString = string | Partial<Record<string, string>>;

interface GSCTournamentData {
    order: number;
    token: string;
}

interface WeeklyTournamentData {
    year: number;
    week: number;
    tournament_format: 'c';
}

interface WeeklyEffTournamentData {
    year: number;
    week: number;
}

type TournamentData = GSCTournamentData | WeeklyTournamentData | WeeklyEffTournamentData | Record<string, never>;

export interface TournamentInfo {
    [key: string]: unknown;
    id?: number;
    name?: LocalizedString;
    description?: LocalizedString;
    subclass?: TournamentSubclass;
    data?: TournamentData;
    startDate?: string | Date | null;
    start_time?: string | Date | null;
    endDate?: string | Date | null;
    end_time?: string | Date | null;
    hostId?: number;
    host_id?: number;
    hostName?: string;
    host_realname?: string;
    state?: TournamentState;
}

export class Tournament {
    private static readonly cannotValidateStates: readonly TournamentState[] = [
        TournamentState.Awarded,
        TournamentState.Normal,
        TournamentState.Finished,
        TournamentState.Ongoing,
        TournamentState.Preparing,
    ];
    private static readonly cannotInvalidateStates: readonly TournamentState[] = [
        TournamentState.Awarded,
        TournamentState.Cancelled,
    ];
    public id: number;
    public name: LocalizedString;
    public description?: LocalizedString;
    public startDate?: Date;
    public endDate?: Date;
    public hostId: number;
    public hostName: string;
    public state: TournamentState;
    public subclass: TournamentSubclass;
    public data: TournamentData;

    public constructor(info: TournamentInfo) {
        this.id = info.id ?? 0;
        this.subclass = info.subclass ?? TournamentSubclass.Unknown;
        this.data = info.data ?? {};
        this.name = info.name ?? this.buildName();
        this.description = info.description ?? this.buildDescription();

        this.startDate = toDate(info.startDate) ?? toDate(info.start_time);
        this.endDate = toDate(info.endDate) ?? toDate(info.end_time);

        this.hostId = info.hostId ?? info.host_id ?? 0;
        this.hostName = info.hostName ?? info.host_realname ?? '';
        this.state = info.state ?? TournamentState.Pending;
    }

    public get canValidate(): boolean {
        if (Tournament.cannotValidateStates.includes(this.state)) return false;
        if (!this.startDate || !this.endDate || this.startDate >= this.endDate) return false;
        return true;
    }

    public get canInvalidate(): boolean {
        return !Tournament.cannotInvalidateStates.includes(this.state);
    }

    public get gscData(): GSCTournamentData | undefined {
        if (this.subclass !== TournamentSubclass.GSC) return undefined;
        return this.data as GSCTournamentData;
    }

    public get weeklyData(): WeeklyTournamentData | undefined {
        if (this.subclass !== TournamentSubclass.Weekly) return undefined;
        return this.data as WeeklyTournamentData;
    }

    public get weeklyEffData(): WeeklyEffTournamentData | undefined {
        if (this.subclass !== TournamentSubclass.WeeklyEff) return undefined;
        return this.data as WeeklyEffTournamentData;
    }

    public static localFallback(local: string | undefined): 'zh' | 'en' | undefined {
        if (local === undefined) return undefined;
        if (local === 'zh') return undefined;
        if (local.startsWith('zh')) return 'zh';
        if (local === 'en') return undefined;
        return 'en';
    }

    public static getLocalString(message: LocalizedString, local?: string): string {
        if (typeof message === 'string') return message;
        let _local = local;
        while (_local !== undefined) {
            const nextMessage = message[_local];
            if (nextMessage !== undefined) return nextMessage;
            _local = Tournament.localFallback(_local);
        }
        return '';
    }

    public getDisplayState(now = new Date()): TournamentState {
        if (this.state !== TournamentState.Normal) return this.state;
        if (!this.startDate || !this.endDate) return TournamentState.Normal;
        if (now < this.startDate) return TournamentState.Preparing;
        if (now < this.endDate) return TournamentState.Ongoing;
        return TournamentState.Finished;
    }

    /**
     * 根据提供的本地化标识符获取对应的描述文本
     *
     * @param local - 本地化标识符，用于指定要获取的描述文本的语言或地区
     * @returns 返回匹配的描述文本。如果找不到匹配项，则返回空字符串
     *
     * @remarks
     * 该方法会检查description属性是否存在，如果不存在则直接返回空字符串。
     * 如果description是字符串类型，则直接返回该字符串。
     * 对于对象类型的description，会尝试使用提供的local参数作为键查找对应的值。
     * 如果找不到匹配项，会使用Tournament.localFallback方法进行回退查找。
     *
     * @example
     */
    public getLocalDescription(local: string): string {
        if (this.description === undefined) return '';
        return Tournament.getLocalString(this.description, local);
    }

    public getLocalName(local?: string): string {
        return Tournament.getLocalString(this.name, local);
    }

    public buildName(): LocalizedString {
        switch (this.subclass) {
            case TournamentSubclass.GSC:
                return {
                    zh: `第${this.gscData?.order ?? ''}届金羊杯`,
                    en: `GSC#${this.gscData?.order ?? ''}`,
                };
            case TournamentSubclass.Weekly:
                return {
                    zh: `${this.weeklyData?.year ?? ''}年第${this.weeklyData?.week ?? ''}周竞速打卡赛`,
                    en: `Speed Weekly ${this.weeklyData?.year ?? ''}#${this.weeklyData?.week ?? ''}`,
                };
            case TournamentSubclass.WeeklyEff:
                return {
                    zh: `${this.weeklyEffData?.year ?? ''}年第${this.weeklyEffData?.week ?? ''}周效率打卡赛`,
                    en: `Efficiency Weekly ${this.weeklyEffData?.year ?? ''}#${this.weeklyEffData?.week ?? ''}`,
                };
            default:
                return '';
        }
    }

    public buildDescription(): LocalizedString | undefined {
        if (this.subclass === TournamentSubclass.Unknown) return undefined;
        return '';
    }

    public displayStartTime(): string {
        if (!this.startDate) return '';
        return toISODateTimeString(this.startDate);
    }

    public displayEndTime(): string {
        if (!this.endDate) return '';
        return toISODateTimeString(this.endDate);
    }
}
