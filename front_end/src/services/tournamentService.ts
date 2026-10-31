import $axios from '@/http';
import { toDate } from '@/utils/datetime';
import { GSCParticipant } from '@/utils/gsc';
import { TournamentParticipant } from '@/utils/tournaments';
import type { TournamentInfo } from '@/utils/tournaments';
import type { VideoAbstractData } from '@/utils/videoabstract';
import { WeeklyParticipant } from '@/utils/weekly';

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

export async function deleteParticipant(participantId: number): Promise<void> {
    await $axios.delete(`/api/tournament/participant/${participantId}`);
}

export async function createWeeklyParticipant(tournamentId: number): Promise<WeeklyParticipant> {
    const { data } = await $axios.post<TournamentParticipantResponse>('/api/tournament/weekly/participant', {
        id: tournamentId,
    });
    return weeklyParticipantFromParticipantResponse(data);
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

export async function fetchWeeklyResults(tournamentId: number): Promise<WeeklyParticipant[]> {
    const { data } = await $axios.get<WeeklyScoreResponse[]>('/api/tournament/weekly/results', {
        params: { tournament_id: tournamentId },
    });
    return data.map((participant) => weeklyParticipantFromResponse(participant, tournamentId));
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

function weeklyParticipantFromParticipantResponse(data: TournamentParticipantResponse): WeeklyParticipant {
    return new WeeklyParticipant(tournamentParticipantFromResponse(data));
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

function weeklyParticipantFromResponse(data: WeeklyScoreResponse, tournamentId: number): WeeklyParticipant {
    return new WeeklyParticipant({
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
