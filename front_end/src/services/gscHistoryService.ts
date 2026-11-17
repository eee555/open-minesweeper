import type { HistoryKind, HistoryScoreRow } from '@/components/GSCAdmin/history';
import $axios from '@/http';
import { fetchGSCResults } from '@/services/tournamentService';
import type { GSCParticipantResponse } from '@/services/tournamentService';
import type { GSCParticipant } from '@/utils/gsc';
import type { VideoAbstractData } from '@/utils/videoabstract';

export interface IdentifierBinding {
    identifier: string;
    bound: boolean;
}

export async function fetchGSCHistory(order: number): Promise<{ tournamentId: number; hostId: number | null; endTime: Date; participants: GSCParticipant[] }> {
    const { data } = await $axios.get<{ id: number; host_id: number | null; end_time: string | null }>('/api/tournament/gsc/admin-info', { params: { order } });
    if (data.end_time === null) throw new Error('Tournament end time is not set.');
    const participants = await fetchGSCResults(data.id);
    return { tournamentId: data.id, hostId: data.host_id, endTime: new Date(data.end_time), participants };
}

export async function prepareGSCHistory(order: number, userId: number): Promise<GSCParticipantResponse> {
    const { data } = await $axios.post<GSCParticipantResponse>('/api/tournament/gsc/history/prepare', { order, user_id: userId }, { headers: { 'Content-Type': 'application/json' } });
    return data;
}

export async function bindGSCHistoryIdentifier(participantId: number, identifier: string): Promise<IdentifierBinding> {
    const { data } = await $axios.post<IdentifierBinding>(`/api/tournament/gsc/history/participants/${participantId}/identifier`, { identifier }, { headers: { 'Content-Type': 'application/json' } });
    return data;
}

export async function uploadGSCHistoryVideo(participantId: number, file: File, uploadTime: Date): Promise<VideoAbstractData> {
    const form = new FormData();
    form.append('file', file);
    form.append('upload_time', uploadTime.toISOString());
    const { data } = await $axios.post<VideoAbstractData>(`/api/tournament/gsc/history/participants/${participantId}/videos`, form);
    return data;
}

export async function importGSCHistoryScores(kind: HistoryKind, order: number, rows: HistoryScoreRow[]): Promise<number> {
    const { data } = await $axios.post<number>(`/api/tournament/gsc/history/scores/${kind}`, { order, rows }, { headers: { 'Content-Type': 'application/json' } });
    return data;
}
