import $axios from '@/http';

const ROOT = '/api/media';
const JSON_CONFIG = { headers: { 'Content-Type': 'application/json' } };
const SUBMIT_CONFIG = { ...JSON_CONFIG, timeout: 25000 };

export type MediaFormatValue = 'B_v' | 'B_a' | 'c_p';
export type MediaStatusValue = 'pending' | 'verified' | 'rejected';
export type MediaSortKey = 'hot' | 'likes' | 'created_at';
export type MediaRankSort = 'hot' | 'likes';
export type MediaQueryField = 'title' | 'suffix';
export type MediaQueryMode = 'exact' | 'iexact' | 'contains' | 'icontains' | 'startswith' | 'istartswith' | 'endswith' | 'iendswith' | 'regex';

export interface MediaItem {
    id: number;
    title: string;
    language: string;
    created_at: string;
    submitted_at: string;
    format: string;
    status: MediaStatusValue;
    rejected_at: string | null;
    reject_reason: string;
    refunded_likes: number;
    likes: number;
    hot_value: number;
    hot_value_updated_at: string;
    metadata_pending: boolean;
    user_id: number;
    rejected_by: number | null;
    url: string;
    embed_url: string | null;
    hot_now: number;
}

export interface MediaPage {
    items: MediaItem[];
    total: number;
    start: number;
    anchor: string;
}

export interface MediaUserRankRow {
    user_id: number;
    hot: number;
    likes: number;
}

export interface MediaUserRankPage {
    items: MediaUserRankRow[];
    total: number;
    start: number;
    anchor: string;
}

export interface MediaMe {
    balance: number;
    likes_sent: number;
    banned: boolean;
}

export interface MediaLikeResult {
    likes: number;
    hot_now: number;
    balance: number;
    status: MediaStatusValue;
}

export interface MediaQueryResult {
    items: MediaItem[];
    total: number;
}

export interface MediaQueryErrorBody {
    code: string;
    detail: string;
}

export interface MediaVerifyPayload {
    id: number;
    title?: string | null;
    external_author_id?: string | null;
    created_at?: string | null;
}

export interface MediaEditPayload {
    id: number;
    title?: string | null;
    language?: string | null;
    created_at?: string | null;
    url?: string | null;
}

async function getPage(path: string, params: Record<string, string | number>): Promise<MediaPage> {
    const { data } = await $axios.get<MediaPage>(`${ROOT}${path}`, { params });
    return data;
}

export function fetchMediaRanking(sort: MediaRankSort, start: number, count: number): Promise<MediaPage> {
    return getPage('/ranking', { sort, start, count });
}

export function fetchLatestMedia(start: number, count: number): Promise<MediaPage> {
    return getPage('/latest', { start, count });
}

export function fetchPendingMedia(start: number, count: number): Promise<MediaPage> {
    return getPage('/pending', { start, count });
}

export function fetchRejectedMedia(start: number, count: number): Promise<MediaPage> {
    return getPage('/admin/rejected', { start, count });
}

export async function fetchUserMediaRanking(sort: MediaRankSort, start: number, count: number): Promise<MediaUserRankPage> {
    const { data } = await $axios.get<MediaUserRankPage>(`${ROOT}/user-ranking`, { params: { sort, start, count } });
    return data;
}

export async function fetchMediaDetailBatch(ids: number[]): Promise<MediaItem[]> {
    const { data } = await $axios.get<MediaItem[]>(`${ROOT}/detailbatch`, { params: { ids: ids.join(',') } });
    return data;
}

export async function queryMedia(mode: MediaQueryMode, value: string, field: MediaQueryField, limit = 1000): Promise<MediaQueryResult> {
    const { data } = await $axios.get<MediaQueryResult>(`${ROOT}/query/${mode}`, { params: { value, field, limit } });
    return data;
}

export function fetchUserMedia(userId: number, sort: MediaSortKey, order: 'asc' | 'desc', page: number, pageSize: number): Promise<MediaPage> {
    return getPage(`/user/${userId}`, { sort, order, page, pageSize });
}

export async function fetchMediaMe(): Promise<MediaMe> {
    const { data } = await $axios.get<MediaMe>(`${ROOT}/me`);
    return data;
}

export async function submitMedia(format: MediaFormatValue, suffix: string, language: string): Promise<MediaItem> {
    const { data } = await $axios.post<MediaItem>(`${ROOT}/submit`, { format, suffix, language }, SUBMIT_CONFIG);
    return data;
}

export async function likeMedia(mediaId: number): Promise<MediaLikeResult> {
    const { data } = await $axios.post<MediaLikeResult>(`${ROOT}/like`, { media_id: mediaId }, JSON_CONFIG);
    return data;
}

export async function verifyMediaAdmin(payload: MediaVerifyPayload): Promise<MediaItem> {
    const { data } = await $axios.post<MediaItem>(`${ROOT}/admin/verify`, payload, JSON_CONFIG);
    return data;
}

export async function rejectMediaAdmin(id: number, reason: string): Promise<MediaItem> {
    const { data } = await $axios.post<MediaItem>(`${ROOT}/admin/reject`, { id, reason }, JSON_CONFIG);
    return data;
}

export async function reopenMediaAdmin(id: number): Promise<MediaItem> {
    const { data } = await $axios.post<MediaItem>(`${ROOT}/admin/reopen`, { id }, JSON_CONFIG);
    return data;
}

export async function setMediaBanned(userId: number, banned: boolean): Promise<boolean> {
    const path = banned ? '/admin/ban' : '/admin/unban';
    const { data } = await $axios.post<boolean>(`${ROOT}${path}`, { user_id: userId }, JSON_CONFIG);
    return data;
}

export async function editMediaAdmin(payload: MediaEditPayload): Promise<MediaItem> {
    const { data } = await $axios.post<MediaItem>(`${ROOT}/admin/edit`, payload, JSON_CONFIG);
    return data;
}

export async function deleteMediaAdmin(id: number): Promise<{ deleted: boolean }> {
    const { data } = await $axios.post<{ deleted: boolean }>(`${ROOT}/admin/delete`, { id }, JSON_CONFIG);
    return data;
}
