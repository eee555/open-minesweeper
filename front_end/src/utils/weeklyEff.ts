import { MS_Mode, MS_State } from './ms_const';
import { TournamentParticipant } from './tournaments';
import type { VideoAbstract } from './videoabstract';
import type { WeeklyVideoScore } from './weekly';

export function weeklyEffVideoScore(video: Pick<VideoAbstract, 'timems' | 'cl' | 'bv'>): number {
    if (![video.timems, video.cl, video.bv].every((value) => Number.isFinite(value) && value > 0)) return NaN;
    return video.timems * video.cl ** 2 / (1000 * video.bv ** 2);
}

export function isWeeklyEffSupportedVideo(video: VideoAbstract): boolean {
    if (video.mode !== MS_Mode.Standard || (video.level !== 'i' && video.level !== 'e')) return false;
    return weeklyEffVideoScore(video) < (video.level === 'i' ? 60 : 240);
}

export class WeeklyEffParticipant extends TournamentParticipant {
    public et: WeeklyVideoScore[] = [[0, 240], [0, 240]];
    public it: WeeklyVideoScore[] = Array.from({ length: 5 }, () => [0, 60]);
    public score = 780;

    public constructor(init: Partial<WeeklyEffParticipant> = {}) {
        super(init);
        Object.assign(this, init);
    }

    public get e_sum(): number {
        return this.et.reduce((sum, [, score]) => sum + score, 0);
    }

    public get i_sum(): number {
        return this.it.reduce((sum, [, score]) => sum + score, 0);
    }

    public get videos(): VideoAbstract[] | undefined {
        return super.videos;
    }

    public set videos(videos: VideoAbstract[] | undefined) {
        super.videos = videos;
        this.refresh();
    }

    public refresh(): void {
        this.et = [[0, 240], [0, 240]];
        this.it = Array.from({ length: 5 }, () => [0, 60]);
        for (const video of this._videos ?? []) this.addScore(video);
        this.score = this.e_sum + this.i_sum;
    }

    public addVideo(video: VideoAbstract): void {
        super.addVideo(video);
        this.addScore(video);
        this.score = this.e_sum + this.i_sum;
    }

    private addScore(video: VideoAbstract): void {
        if (video.state !== MS_State.Official || !isWeeklyEffSupportedVideo(video)) return;
        const scores = video.level === 'i' ? this.it : this.et;
        const score = weeklyEffVideoScore(video);
        if (score >= scores[scores.length - 1][1]) return;
        scores[scores.length - 1] = [video.id, score];
        scores.sort((left, right) => left[1] - right[1]);
    }
}
