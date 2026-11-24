import $axios from '@/http';

export interface GitHubPublicProfile {
    id: string;
    login: string;
    url: string;
}

export interface GitHubRepositoryInfo {
    id: string;
    fullName: string;
    description: string;
    htmlUrl: string;
}

const REPOSITORY_CACHE_MS = 10 * 60 * 1000;
const repositoryCache = new Map<string, { expires: number; value: GitHubRepositoryInfo }>();

/** 清除按仓库 ID 缓存的公开信息；测试用于隔离不同的 API 响应。 */
export function resetGitHubRepositoryCache(): void {
    repositoryCache.clear();
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

export async function cancelGitHubLink(state: string): Promise<void> {
    await $axios.post('/api/accountlink/github/cancel', { state }, { headers: { 'Content-Type': 'application/json' } });
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

function parseRepository(data: unknown, id: string): GitHubRepositoryInfo {
    if (typeof data !== 'object' || data === null || !('id' in data) || !('html_url' in data)
        || typeof data.id !== 'number' || !Number.isSafeInteger(data.id) || String(data.id) !== id
        || typeof data.html_url !== 'string'
        || !(/^https:\/\/github\.com\/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}\/?$/).test(data.html_url)) throw new Error('Invalid GitHub repository');
    const path = new URL(data.html_url).pathname.split('/').filter(Boolean);
    if (path.length !== 2 || path[1] === '.' || path[1] === '..') throw new Error('Invalid GitHub repository');
    const fullName = path.join('/');
    if ('full_name' in data && data.full_name !== fullName) throw new Error('Invalid GitHub repository');
    const description = 'description' in data && typeof data.description === 'string' ? data.description : '';
    return { id, fullName, description, htmlUrl: data.html_url };
}

async function requestRepository(id: string, signal?: AbortSignal): Promise<GitHubRepositoryInfo> {
    const response = await fetch(`https://api.github.com/repositories/${id}`, { credentials: 'omit', signal });
    if (!response.ok) throw new Error(`GitHub HTTP ${response.status}`);
    return parseRepository(await response.json(), id);
}

export async function fetchGitHubRepositoryInfo(id: string, signal?: AbortSignal): Promise<GitHubRepositoryInfo> {
    if (!(/^[1-9][0-9]*$/).test(id)) throw new Error('Invalid GitHub repository ID');
    const cached = repositoryCache.get(id);
    if (cached && cached.expires > Date.now()) return cached.value;
    const value = await requestRepository(id, signal);
    repositoryCache.set(id, { value, expires: Date.now() + REPOSITORY_CACHE_MS });
    return value;
}

export async function fetchGitHubRepositoryUrl(id: string, signal?: AbortSignal): Promise<string> {
    return (await fetchGitHubRepositoryInfo(id, signal)).htmlUrl;
}
