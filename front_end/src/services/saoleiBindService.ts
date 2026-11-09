import { isAxiosError } from 'axios';

import $axios from '@/http';

const root = '/api/accountlink/saolei/bind';
const requestOptions = { timeout: 30000, headers: { 'Content-Type': 'application/json' } };

/** 扫雷网侧申请信息（openms 后端代理扫雷网公开接口 bind-request 的透传结果） */
export interface SaoleiBindRequestInfo {

    /** 0=待确认 1=已核销 2=已取消；非 0 时授权页应提示申请已失效 */
    status: number;

    /** 扫雷网用户 ID */
    uid: number;

    /** 扫雷网用户名（授权页展示「谁在申请」用） */
    username: string;
}

export function isSaoleiBindToken(token: string | undefined | null): token is string {
    return typeof token === 'string' && (/^[0-9a-f]{48}$/).test(token);
}

export async function fetchSaoleiBindRequest(token: string): Promise<SaoleiBindRequestInfo> {
    try {
        return (await $axios.get<SaoleiBindRequestInfo>(`${root}/request`, { params: { token } })).data;
    } catch (error) {
        if (isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) {
            throw new SaoleiBindError('login_required');
        }
        if (isAxiosError(error) && error.response?.status === 404) {
            throw new SaoleiBindError('invalid_token');
        }
        throw new SaoleiBindError('network');
    }
}

export async function confirmSaoleiBind(token: string, sync: boolean): Promise<void> {
    try {
        await $axios.post(`${root}/confirm`, { token, sync }, requestOptions);
    } catch (error) {
        if (isAxiosError(error)) {
            if ([401, 403].includes(error.response?.status ?? 0)) throw new SaoleiBindError('login_required');
            if (error.response?.status === 404) throw new SaoleiBindError('invalid_token');
            if (error.response?.status === 409) throw new SaoleiBindError('collision');
        }
        throw new SaoleiBindError('network');
    }
}

export type SaoleiBindErrorCategory = 'login_required' | 'invalid_token' | 'collision' | 'network';

export class SaoleiBindError extends Error {
    public category: SaoleiBindErrorCategory;

    public constructor(category: SaoleiBindErrorCategory) {
        super(category);
        this.category = category;
    }
}
