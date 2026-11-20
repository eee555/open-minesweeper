import { isAxiosError } from 'axios';

import $axios from '@/http';
import { assignHistoryUploadTimes } from '@/utils/historyUploadTimes';
import type { VideoAbstractData } from '@/utils/videoabstract';

const endpoint = '/api/common/admin/memorial';
const memorialErrorCategories = [
    'not_memorial', 'not_found', 'userms_missing', 'collision', 'timezone_required',
    'platform_not_assignable', 'identifier_required', 'identifier_invalid',
] as const;
type MemorialErrorCode = typeof memorialErrorCategories[number] | 'forbidden' | 'unknown';

export interface MemorialUser {
    id: number;
    userms_id: number;
    username: string;
    realname: string;
    firstname: string;
    lastname: string;
    is_memorial: boolean;
}
export interface MemorialAccess {
    csrf_token: string;
    user: MemorialUser;
}
export interface MemorialReplay {
    index: number;
    file: File;
    identifier: string;
    endTime: Date;
    timems: number;
}
export interface MemorialUpload extends MemorialReplay {
    uploadTime: Date;
    result?: VideoAbstractData;
    errorCode?: MemorialErrorCode;
}
export interface MemorialBinding {
    identifier: string;
    bound: boolean;
    error?: string | null;
}
interface UploadResult {
    video: VideoAbstractData;
    bindings: MemorialBinding[];
}

export async function fetchMemorialAccess(id: number): Promise<MemorialAccess> {
    const { data } = await $axios.get<MemorialAccess>(`${endpoint}/users/${id}/videos`);
    return data;
}

export interface MemorialAccountLink {
    platform: string;
    identifier: string;
    verified: boolean;
    name: string;
}

export interface MemorialLinks {
    csrf_token: string;
    user: MemorialUser;
    links: MemorialAccountLink[];
}

export async function fetchMemorialLinks(id: number): Promise<MemorialLinks> {
    const { data } = await $axios.get<MemorialLinks>(`${endpoint}/users/${id}/account-links`);
    return data;
}

export async function assignMemorialLink(id: number, platform: string, identifier: string, token: string): Promise<MemorialAccountLink> {
    const form = new FormData();
    form.append('platform', platform);
    form.append('identifier', identifier);
    const { data } = await $axios.post<MemorialAccountLink>(`${endpoint}/users/${id}/account-links`, form, { headers: { 'X-CSRFToken': token } });
    return data;
}

export async function removeMemorialLink(id: number, platform: string, token: string): Promise<void> {
    await $axios.delete(`${endpoint}/users/${id}/account-links`, { params: { platform }, headers: { 'X-CSRFToken': token } });
}

export function memorialErrorCode(error: unknown): MemorialErrorCode {
    if (!isAxiosError<unknown>(error)) return 'unknown';
    if (error.response?.status === 401 || error.response?.status === 403) return 'forbidden';
    const payload = error.response?.data;
    if (payload === null || typeof payload !== 'object' || !('category' in payload)) return 'unknown';
    return memorialErrorCategories.find((category) => category === payload.category) ?? 'unknown';
}

export function planMemorialUploads(replays: MemorialReplay[], identifiers: string[], anchor: Date): MemorialUpload[] {
    const selected = new Set(identifiers);
    return assignHistoryUploadTimes(replays.filter((replay) => selected.has(replay.identifier)), anchor);
}

export async function uploadMemorialBatch(
    userId: number, identifiers: string[], bindings: MemorialBinding[], uploads: MemorialUpload[], token: string,
    stopped: () => boolean = () => false,
): Promise<void> {
    let pendingIdentifiers = [...new Set(identifiers)].filter((identifier) => !bindings.some((binding) => binding.identifier === identifier && binding.bound));
    function receiveBindings(results: MemorialBinding[]) {
        for (const result of results) {
            const index = bindings.findIndex((binding) => binding.identifier === result.identifier);
            if (index < 0) bindings.push(result);
            else bindings[index] = result;
        }
        pendingIdentifiers = [];
    }
    for (const entry of uploads) {
        if (stopped()) return;
        if (entry.result) continue;
        const form = new FormData();
        form.append('file', entry.file);
        form.append('upload_time', entry.uploadTime.toISOString());
        form.append('identifiers', JSON.stringify(pendingIdentifiers));
        try {
            const { data } = await $axios.post<UploadResult>(`${endpoint}/users/${userId}/videos`, form, { headers: { 'X-CSRFToken': token } });
            receiveBindings(data.bindings);
            entry.result = data.video;
            entry.errorCode = undefined;
        } catch (error) {
            if (isAxiosError<Partial<UploadResult>>(error) && Array.isArray(error.response?.data?.bindings)) receiveBindings(error.response.data.bindings);
            entry.errorCode = memorialErrorCode(error);
        }
    }
}
