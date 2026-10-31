import { isAxiosError } from 'axios';

import $axios from '@/http';
import { assignHistoryUploadTimes } from '@/utils/historyUploadTimes';
import type { VideoAbstractData } from '@/utils/videoabstract';

const endpoint = '/api/common/admin/memorial';

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
    error?: string;
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

export function memorialErrorText(error: unknown): string {
    if (isAxiosError<unknown>(error)) {
        if (error.response?.status === 401 || error.response?.status === 403) return '仅站长可以操作，请确认登录状态。';
        const payload: unknown = error.response?.data;
        if (payload !== null && typeof payload === 'object') {
            const category = 'category' in payload && typeof payload.category === 'string' ? payload.category : '';
            const messages: Record<string, string> = {
                not_memorial: '目标不是纪念账号。',
                not_found: '纪念账号不存在。',
                userms_missing: '纪念账号缺少 UserMS，请先在服务器上修复关联。',
                collision: '录像文件归属冲突。',
                timezone_required: '上传日期必须包含时区。',
            };
            return messages[category] ?? JSON.stringify(payload);
        }
    }
    return String(error);
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
            entry.error = undefined;
        } catch (error) {
            if (isAxiosError<Partial<UploadResult>>(error) && Array.isArray(error.response?.data?.bindings)) receiveBindings(error.response.data.bindings);
            entry.error = memorialErrorText(error);
        }
    }
}
