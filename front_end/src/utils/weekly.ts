import { MS_State } from './ms_const';
import { TournamentParticipant } from './tournaments';
import type { VideoAbstract } from './videoabstract';
import { matchesWeeklyFormat, WeeklyTournamentFormat } from './weeklyFormat';

export { WeeklyTournamentFormat } from './weeklyFormat';

export type WeeklyVideoScore = [number, number];

const DEFAULT_WEEKLY_EXPERT_TIME = 240000;
const DEFAULT_WEEKLY_INTERMEDIATE_TIME = 60000;

function makeDefaultScores(count: number, score: number): WeeklyVideoScore[] {
    return Array.from({ length: count }, () => [0, score]);
}

export class WeeklyParticipant extends TournamentParticipant {
    public tournament_format: WeeklyTournamentFormat = WeeklyTournamentFormat.Classic;
    public classic_et: WeeklyVideoScore[] = makeDefaultScores(2, DEFAULT_WEEKLY_EXPERT_TIME);
    public classic_it: WeeklyVideoScore[] = makeDefaultScores(5, DEFAULT_WEEKLY_INTERMEDIATE_TIME);
    public classic_score = DEFAULT_WEEKLY_EXPERT_TIME * 2 + DEFAULT_WEEKLY_INTERMEDIATE_TIME * 5;

    public constructor(init: Partial<WeeklyParticipant> = {}) {
        super();
        this.tournament_format = init.tournament_format ?? WeeklyTournamentFormat.Classic;
        Object.assign(this, init);
    }

    public get classic_e_sum(): number {
        return this.classic_et.reduce((sum, score) => sum + score[1], 0);
    }

    public get classic_i_sum(): number {
        return this.classic_it.reduce((sum, score) => sum + score[1], 0);
    }

    public get videos(): VideoAbstract[] | undefined {
        return super.videos;
    }

    public set videos(videos: VideoAbstract[] | undefined) {
        this._videos = videos;
        this.refresh();
    }

    public refresh(): void {
        this.classic_et = makeDefaultScores(2, DEFAULT_WEEKLY_EXPERT_TIME);
        this.classic_it = makeDefaultScores(5, DEFAULT_WEEKLY_INTERMEDIATE_TIME);
        this.classic_score = DEFAULT_WEEKLY_EXPERT_TIME * 2 + DEFAULT_WEEKLY_INTERMEDIATE_TIME * 5;
        if (this.videos === undefined) return;

        for (const video of this.videos) {
            refreshWithVideo(this, video);
        }
    }

    public addVideo(video: VideoAbstract): void {
        if (this._videos === undefined) this._videos = [video];
        else this._videos.push(video);
        refreshWithVideo(this, video);
    }
}

function refreshWithVideo(participant: WeeklyParticipant, video: VideoAbstract): void {
    if (video.state !== MS_State.Official || !matchesWeeklyFormat(video, participant.tournament_format)) return;
    if (video.level === 'i') {
        const diff = participant.classic_it[4][1] - video.timems;
        if (diff > 0) {
            participant.classic_it[4] = [video.id, video.timems];
            participant.classic_it.sort((a, b) => a[1] - b[1]);
            participant.classic_score -= diff;
        }
    } else if (video.level === 'e') {
        const diff = participant.classic_et[1][1] - video.timems;
        if (diff > 0) {
            participant.classic_et[1] = [video.id, video.timems];
            participant.classic_et.sort((a, b) => a[1] - b[1]);
            participant.classic_score -= diff;
        }
    }
}
