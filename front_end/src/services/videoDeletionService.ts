import $axios from '@/http';

export interface VideoDeletionResult {
    id: number;
    deleted: boolean;
    affected_tournament_ids: number[];
}

const endpoint = '/api/video/admin/delete';

export async function fetchVideoDeletionAccess(): Promise<string> {
    const { data } = await $axios.get<{ csrf_token: string }>(endpoint);
    return data.csrf_token;
}

export async function deleteVideo(id: number, csrfToken: string): Promise<VideoDeletionResult> {
    const { data } = await $axios.post<VideoDeletionResult>(endpoint, { id }, { headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken } });
    return data;
}

export async function deleteVideosSequentially(ids: readonly number[], csrfToken: string, onResult: (result: VideoDeletionResult) => void, shouldStop: () => boolean): Promise<void> {
    for (const id of ids) {
        if (shouldStop()) break;
        const result = await deleteVideo(id, csrfToken);
        onResult(result);
    }
}

function isVideoId(value: unknown): value is number {
    return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

export function parseVideoDeletionIds(text: string): number[] {
    const source = text.trim();
    if (!source) return [];
    const parsed: unknown = source.startsWith('[')
        ? JSON.parse(source)
        : source.split(/[\s,，;；]+/u).filter(Boolean).map((part) => ((/^\d+$/u).test(part) ? Number(part) : NaN));
    if (!Array.isArray(parsed)) throw new Error('Invalid video IDs');
    const ids: unknown[] = parsed;
    if (!ids.every(isVideoId)) throw new Error('Invalid video IDs');
    return [...new Set(ids)];
}
