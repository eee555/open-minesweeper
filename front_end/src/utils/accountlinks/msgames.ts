import { isDensityCustomLevel } from '../customlevel';

export interface AccountMSGamesResponse {
    id: number;
    parent: number;
    update_time: string;
    name: string;
    local_name: string;
    joined: string | null;
    country: string;
    state: string;
    hand: string;
    mouse: string;
    video_update_time: string | null;
}

export class AccountMSGames {
    public id = 0;
    public parent = 0;
    public name = '';
    public update_time = new Date(0);
    public local_name = '';
    public joined = new Date(0);
    public country = '';
    public state = '';
    public hand = '';
    public mouse = '';

    public constructor(data?: AccountMSGamesResponse) {
        if (data === undefined) return;

        this.id = data.id;
        this.parent = data.parent;
        this.name = data.name;
        this.update_time = new Date(data.update_time);
        this.local_name = data.local_name;
        this.joined = data.joined === null ? new Date(0) : new Date(data.joined);
        this.country = data.country;
        this.state = data.state;
        this.hand = data.hand;
        this.mouse = data.mouse;
    }
}

export interface MSGamesVideo {
    id: number;
    user: number;
    url: string;
    filename: string;
    upload_date: string | null;
    category: string;
    score: string;
    import_video: number | null;
}

export type MSGamesImportBlocker = 'mvr' | 'format' | 'configuration';

export function msgamesVideoImportBlocker(video: Pick<MSGamesVideo, 'filename' | 'category' | 'score'>): MSGamesImportBlocker | null {
    if ((/\.mvr$/i).test(video.filename)) return 'mvr';
    if (!(/\.(avf|mvf|rmv)$/i).test(video.filename)) return 'format';
    const categories = video.category.split('\n').filter((line) => line.split(' / ', 1)[0] === 'Density');
    if (categories.length === 0) return null;
    const scores = video.score.split('\n').filter((line) => line.startsWith('Density: '));
    if (scores.length === 0) return 'configuration';
    const boards = categories.flatMap((line) => (line.split(' / ')[1] ?? '').split(', '));
    const supported = scores.every((score) => {
        const mines = (/(?:^|;\s*)Mines:\s*(\d+)\s*(?:;|$)/).exec(score.slice('Density: '.length));
        if (!mines) return false;
        return boards.every((board) => {
            const dimensions = (/^(\d+)x(\d+)$/).exec(board);
            return dimensions !== null && isDensityCustomLevel(Number(dimensions[2]), Number(dimensions[1]), Number(mines[1]));
        });
    });
    return supported ? null : 'configuration';
}

export function canImportMSGamesVideo(video: Pick<MSGamesVideo, 'filename' | 'category' | 'score'>): boolean {
    return msgamesVideoImportBlocker(video) === null;
}

export interface MSGamesImportSummary {
    total: number;
    imported: number;
    video_update_time: string | null;
}

export interface MSGamesImportResult {
    status: 'IMPORTED' | 'ALREADY_IMPORTED';
    import_video_id: number;
    video_state: string;
}

export interface MSGamesSyncResult {
    status: 'SYNCED';
    count: number;
    video_update_time: string;
}
