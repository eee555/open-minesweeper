import { isAxiosError } from 'axios';

import $axios from '@/http';

export const discordErrorCategories = [
    'access_denied', 'invalid_state', 'session_changed', 'identifier_conflict', 'not_linked',
    'account_disabled', 'not_configured', 'upstream_error', 'timeout', 'authorization_failed', 'login_required',
] as const;

export function normalizeDiscordError(category: unknown): string {
    return typeof category === 'string' && discordErrorCategories.some((known) => known === category) ? category : 'unknown';
}

export function discordHttpError(error: unknown): string {
    if (isAxiosError<{ object?: string; category?: string }>(error) && error.response?.data?.object === 'discord') {
        return normalizeDiscordError(error.response.data.category);
    }
    return 'unknown';
}

export async function discordAvailable(): Promise<boolean> {
    const { data } = await $axios.get<{ enabled: boolean }>('/api/accountlink/discord/config');
    return data.enabled;
}

export async function authorizeDiscord(mode: 'link' | 'login', setExpiry = 0): Promise<void> {
    const { data } = await $axios.post<{ authorization_url: string }>('/api/accountlink/discord/start', { mode, set_expiry: setExpiry });
    const url = new URL(data.authorization_url);
    if (url.origin !== 'https://discord.com' || url.pathname !== '/oauth2/authorize') throw new Error('Invalid Discord authorization URL');
    window.location.assign(url.href);
}

export async function unlinkDiscord(): Promise<void> {
    await $axios.post('/api/accountlink/discord/unlink');
}
