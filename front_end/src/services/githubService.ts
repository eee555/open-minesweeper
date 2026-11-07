import $axios from '@/http';

export interface GitHubPublicProfile {
    id: string;
    login: string;
    url: string;
}

export async function startGitHubLink(): Promise<string> {
    const { data } = await $axios.post<{ authorization_url: string }>('/api/accountlink/github/start');
    const url = new URL(data.authorization_url);
    if (url.origin !== 'https://github.com' || url.pathname !== '/login/oauth/authorize') throw new Error('Invalid authorization URL');
    return url.href;
}

export async function unlinkGitHub(): Promise<void> {
    await $axios.post('/api/accountlink/github/unlink');
}

export async function fetchGitHubProfile(id: string, signal?: AbortSignal): Promise<GitHubPublicProfile> {
    if (!(/^[1-9][0-9]*$/).test(id)) throw new Error('Invalid GitHub ID');
    // 使用原生 fetch，避免本站 axios 的 Cookie、认证头和拦截器进入第三方请求。
    const response = await fetch(`https://api.github.com/user/${id}`, { credentials: 'omit', signal });
    if (!response.ok) throw new Error(`GitHub HTTP ${response.status}`);
    const data: unknown = await response.json();
    if (typeof data !== 'object' || data === null || !('id' in data) || !('login' in data)
        || typeof data.id !== 'number' || !Number.isSafeInteger(data.id) || String(data.id) !== id
        || typeof data.login !== 'string' || !(/^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/).test(data.login)) throw new Error('Invalid GitHub profile');
    return { id, login: data.login, url: `https://github.com/${data.login}` };
}
