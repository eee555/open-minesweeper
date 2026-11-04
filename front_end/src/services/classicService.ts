import { isAxiosError } from 'axios';

import $axios from '@/http';
import { ClassicAccountLink } from '@/utils/accountlinks';
import type { ClassicAccountLinkResponse } from '@/utils/accountlinks';

interface ClassicAccountLinkBackendErrorResponse {
    type?: string;
    object?: string;
    category?: string;
}

export async function startClassicAccountLink(uid: string): Promise<ClassicAccountLink> {
    const { data } = await $axios.post<ClassicAccountLinkResponse>('/api/accountlink/classic/start/', { uid });
    return new ClassicAccountLink(data);
}

export async function fetchClassicAccountLink(): Promise<ClassicAccountLink> {
    const { data } = await $axios.get<ClassicAccountLinkResponse>('/api/accountlink/classic/status/');
    return new ClassicAccountLink(data);
}

export function getClassicAccountLinkHttpErrorCategory(error: unknown): string | undefined {
    if (!isAxiosError(error)) return undefined;
    const data: unknown = error.response?.data;
    if (typeof data !== 'object' || data === null) return undefined;
    const body = data as ClassicAccountLinkBackendErrorResponse;
    return body.object === 'classic' ? body.category : undefined;
}
