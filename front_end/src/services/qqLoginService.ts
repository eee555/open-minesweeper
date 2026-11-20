import { isAxiosError } from 'axios';

import $axios from '@/http';
import type { UserProfileData } from '@/utils/userprofile';

export interface QQLoginProfile { nickname: string; avatar_url: string }
export interface QQLoginStatus {
    user_id: number;
    username: string;
    configured: boolean;
    login_enabled: boolean;
    linked: boolean;
    profile: QQLoginProfile | null;
    pending: QQLoginProfile | null;
    can_unlink: boolean;
    has_email: boolean;
    can_set_username: boolean;
}

const base = '/api/userprofile/qq';
const json = { headers: { 'Content-Type': 'application/json' } };
const errorCategories = new Set(['not_configured', 'remote_failed', 'expired', 'conflict', 'already_linked', 'disabled', 'login_unavailable', 'login_required', 'last_login_method', 'email_code', 'email_used', 'invalid_email', 'already_has_email', 'cancelled', 'rate_limited', 'invalid_username', 'username_readonly', 'username_used', 'username_rejected', 'username_unavailable']);

export function qqLoginErrorKey(error: unknown): string {
    let category: unknown = error;
    if (isAxiosError<{ category?: unknown } | null | undefined>(error)) {
        category = error.response?.status === 429 ? 'rate_limited' : error.response?.data?.category;
    }
    return `qqLogin.errors.${typeof category === 'string' && errorCategories.has(category) ? category : 'remote_failed'}`;
}

export async function startQQLogin(mode: 'login' | 'bind' = 'login'): Promise<string> {
    const { data } = await $axios.post<{ authorization_url: string }>(`${base}/start`, { mode }, json);
    const url = new URL(data.authorization_url);
    if (url.origin !== 'https://graph.qq.com' || url.pathname !== '/oauth2.0/authorize' || url.username !== '' || url.password !== '' || url.hash !== '') throw new Error('Invalid QQ authorization URL');
    return url.href;
}

export async function fetchQQLoginStatus(): Promise<QQLoginStatus> {
    return (await $axios.get<QQLoginStatus>(`${base}/status`)).data;
}

export async function registerQQAccount(): Promise<UserProfileData> {
    return (await $axios.post<{ user: UserProfileData }>(`${base}/register`)).data.user;
}

export async function cancelQQLogin(): Promise<void> {
    await $axios.post(`${base}/cancel`);
}
export async function unlinkQQLogin(): Promise<void> {
    await $axios.post(`${base}/unlink`);
}
export async function bindQQRecoveryEmail(email: string, emailKey: string, emailCaptcha: string): Promise<void> {
    await $axios.post(`${base}/recovery-email`, { email, email_key: emailKey, email_captcha: emailCaptcha }, json);
}
export async function setQQAccountUsername(username: string): Promise<UserProfileData> {
    return (await $axios.post<{ user: UserProfileData }>(`${base}/username`, { username }, json)).data.user;
}
