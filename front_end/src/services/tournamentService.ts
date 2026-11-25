import $axios from '@/http';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';
import { toDate } from '@/utils/datetime';
import { GSCParticipant } from '@/utils/gsc';
import { TournamentParticipant } from '@/utils/tournaments';
import type { TournamentInfo } from '@/utils/tournaments';
import type { VideoAbstractData } from '@/utils/videoabstract';
import { WeeklyParticipant, WeeklyTournamentFormat } from '@/utils/weekly';
import { WeeklyEffParticipant } from '@/utils/weeklyEff';

export interface GSCParticipantResponse {
    id: number;
    user_id: number;
    rank: number | null;
    rank_score: number;
    manual_scores: boolean;
    arbiter_identifier: string | null;
    has_videos: boolean;
    bt1st: number;
    bt20th: number;
    bt20sum: number;
    it1st: number;
    it12th: number;
    it12sum: number;
    et1st: number;
    et5th: number;
    et5sum: number;
}

export interface WeeklyScoreResponse {
    id: number;
    user_id: number;
    start_time: string;
    end_time: string | null;
    rank: number | null;
    rank_score: number;
    classic_et: [number, number][];
    classic_it: [number, number][];
    classic_score: number;
}

interface WeeklyEffScoreResponse extends Pick<WeeklyScoreResponse, 'id' | 'user_id' | 'start_time' | 'end_time' | 'rank' | 'rank_score'> {
    et: [number, number][];
    it: [number, number][];
    score: number;
}

export interface TournamentParticipantResponse {
    id: number;
    token: string;
    start_time: string;
    end_time: string | null;
    rank: number | null;
    rank_score: number;
    user_id: number;
    tournament_id: number;
    has_videos: boolean;
    arbiter_identifier__identifier?: string | null;
}

interface ParticipantVideosParams {
    userId: number;
    tournamentId: number;
}

export type TournamentListCategory = 'normal' | 'awarded' | 'other' | 'all';
export const TournamentUserRankFields = [
    'score_current', 'score_total',
    'gsc_total', 'gsc_best',
    'weekly_total', 'weekly_classic_total', 'weekly_classic_best',
    'weekly_nf_total', 'weekly_nf_best', 'weekly_qwc_total', 'weekly_qwc_best', 'weekly_qwc_nf_total', 'weekly_qwc_nf_best',
    'weekly_eff_total', 'weekly_eff_best',
] as const;
export type TournamentUserRankField = typeof TournamentUserRankFields[number];

export interface TournamentUserRankingRow {
    user_id: number;
    score_current: number;
    last_updated: string;
    score_total: number;
    gsc_total: number;
    gsc_best: number;
    weekly_total: number;
    weekly_classic_total: number;
    weekly_classic_best: number;
    weekly_nf_total: number;
    weekly_nf_best: number;
    weekly_qwc_total: number;
    weekly_qwc_best: number;
    weekly_qwc_nf_total: number;
    weekly_qwc_nf_best: number;
    weekly_eff_total: number;
    weekly_eff_best: number | null;
    weekly_eff_best_year: number | null;
    weekly_eff_best_week: number | null;
}

export interface TournamentUserRankingResponse {
    total: number;
    data: TournamentUserRankingRow[];
}

interface TournamentUserRankingParams {
    sortBy: TournamentUserRankField;
    start: number;
    end: number;
}

export async function fetchTournamentList(category: TournamentListCategory = 'all'): Promise<TournamentInfo[]> {
    const { data } = await $axios.get<TournamentInfo[]>('/api/tournament/get_list', {
        params: { category },
    });
    return data;
}

export async function fetchTournament(tournamentId: number | string): Promise<TournamentInfo> {
    const { data } = await $axios.get<TournamentInfo>('/api/tournament/get', {
        params: { tournament_id: tournamentId },
    });
    return data;
}

export async function fetchParticipantList(tournamentId: number): Promise<TournamentParticipant[]> {
    const { data } = await $axios.get<TournamentParticipantResponse[]>('/api/tournament/participants', {
        params: { tournament_id: tournamentId },
    });
    return data.map(tournamentParticipantFromResponse);
}

export async function resetParticipant(participantId: number): Promise<void> {
    await $axios.post(`/api/tournament/participant/${participantId}/reset`);
}

export interface ParticipantDisqualificationTask {
    id: string;
    status: DjangoTaskResultStatus;
    traceback: string;
}

export async function disqualifyParticipant(participantId: number): Promise<ParticipantDisqualificationTask> {
    const { data } = await $axios.post<ParticipantDisqualificationTask>(`/api/tournament/participant/${participantId}/disqualify`);
    return data;
}

export async function fetchDisqualificationTask(taskId: string): Promise<ParticipantDisqualificationTask> {
    const { data } = await $axios.get<ParticipantDisqualificationTask>(`/api/tournament/disqualification-task/${taskId}`);
    return data;
}

export async function createWeeklyParticipant(tournamentId: number, tournamentFormat: WeeklyTournamentFormat): Promise<WeeklyParticipant> {
    const { data } = await $axios.post<TournamentParticipantResponse>('/api/tournament/weekly/participant', {
        id: tournamentId,
    });
    return new WeeklyParticipant(Object.assign({}, tournamentParticipantFromResponse(data), { tournament_format: tournamentFormat }));
}

export async function createWeeklyEffParticipant(tournamentId: number): Promise<WeeklyEffParticipant> {
    const { data } = await $axios.post<TournamentParticipantResponse>('/api/tournament/weekly-eff/participant', { id: tournamentId });
    return new WeeklyEffParticipant(tournamentParticipantFromResponse(data));
}

export async function fetchWeeklyEffResults(tournamentId: number): Promise<WeeklyEffParticipant[]> {
    const { data } = await $axios.get<WeeklyEffScoreResponse[]>('/api/tournament/weekly-eff/results', { params: { tournament_id: tournamentId } });
    return data.map((row) => new WeeklyEffParticipant({
        id: row.id,
        user_id: row.user_id,
        tournament_id: tournamentId,
        start_time: toDate(row.start_time),
        end_time: toDate(row.end_time),
        rank: row.rank ?? undefined,
        rank_score: row.rank_score,
        et: row.et,
        it: row.it,
        score: row.score,
    }));
}

export async function fetchTournamentUserRanking(params: TournamentUserRankingParams): Promise<TournamentUserRankingResponse> {
    const { data } = await $axios.get<TournamentUserRankingResponse>('/api/tournament/user-ranking', {
        params: {
            sort_by: params.sortBy,
            start: params.start,
            end: params.end,
        },
    });
    return data;
}

export async function fetchGSCResults(tournamentId: number): Promise<GSCParticipant[]> {
    const { data } = await $axios.get<GSCParticipantResponse[]>('/api/tournament/gsc/results', {
        params: { tournament_id: tournamentId },
    });
    return data.map((participant) => gscParticipantFromResponse(participant, tournamentId));
}

export async function fetchWeeklyResults(tournamentId: number, tournamentFormat: WeeklyTournamentFormat = WeeklyTournamentFormat.Classic): Promise<WeeklyParticipant[]> {
    const { data } = await $axios.get<WeeklyScoreResponse[]>('/api/tournament/weekly/results', {
        params: { tournament_id: tournamentId },
    });
    return data.map((participant) => weeklyParticipantFromResponse(participant, tournamentId, tournamentFormat));
}

export async function fetchParticipantVideos(params: ParticipantVideosParams): Promise<VideoAbstractData[]> {
    const { data } = await $axios.get<VideoAbstractData[]>('/api/tournament/get_videos/participant', {
        params: {
            user_id: params.userId,
            tournament_id: params.tournamentId,
        },
    });
    return data;
}

export async function fetchTournamentVideos(tournamentId: number): Promise<VideoAbstractData[]> {
    const { data } = await $axios.get<VideoAbstractData[]>('/api/tournament/get_videos/tournament', {
        params: { tournament_id: tournamentId },
    });
    return data;
}

function tournamentParticipantFromResponse(data: TournamentParticipantResponse): TournamentParticipant {
    return new TournamentParticipant({
        id: data.id,
        token: data.token,
        arbiter_identifier__identifier: data.arbiter_identifier__identifier ?? undefined,
        tournament_id: data.tournament_id,
        user_id: data.user_id,
        start_time: toDate(data.start_time),
        end_time: toDate(data.end_time),
        rank: data.rank ?? undefined,
        rank_score: data.rank_score,
        has_videos: data.has_videos,
    });
}

export function gscParticipantFromResponse(data: GSCParticipantResponse, tournamentId: number): GSCParticipant {
    return new GSCParticipant({
        id: data.id,
        user_id: data.user_id,
        tournament_id: tournamentId,
        rank: data.rank ?? undefined,
        rank_score: data.rank_score,
        has_videos: data.has_videos,
        manual_scores: data.manual_scores,
        arbiter_identifier__identifier: data.arbiter_identifier ?? undefined,
        bt1st: data.bt1st,
        bt20th: data.bt20th,
        bt20sum: data.bt20sum,
        it1st: data.it1st,
        it12th: data.it12th,
        it12sum: data.it12sum,
        et1st: data.et1st,
        et5th: data.et5th,
        et5sum: data.et5sum,
    });
}

function weeklyParticipantFromResponse(data: WeeklyScoreResponse, tournamentId: number, tournamentFormat: WeeklyTournamentFormat): WeeklyParticipant {
    return new WeeklyParticipant({
        tournament_format: tournamentFormat,
        id: data.id,
        user_id: data.user_id,
        tournament_id: tournamentId,
        start_time: toDate(data.start_time),
        end_time: toDate(data.end_time),
        rank: data.rank ?? undefined,
        rank_score: data.rank_score,
        classic_et: data.classic_et,
        classic_it: data.classic_it,
        classic_score: data.classic_score,
    });
}
