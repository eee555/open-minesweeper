import type { AxiosInstance } from 'axios';
import Cookies from 'js-cookie';

const safeMethods = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

export function installAdminCsrfInterceptor(client: AxiosInstance, isAdmin: () => boolean): number {
    const pageUrl = new URL(globalThis.location?.href ?? 'http://localhost/');
    const backendUrl = new URL(client.defaults.baseURL ?? '/', pageUrl);
    let pendingToken: Promise<string> | undefined;

    function getToken() {
        pendingToken ??= client.get<{ csrf_token: unknown }>('/api/userprofile/admin/csrf').then(({ data }) => {
            if (typeof data.csrf_token !== 'string' || !data.csrf_token) throw new Error('Missing administrator CSRF token.');
            return data.csrf_token;
        }).finally(() => {
            pendingToken = undefined;
        });
        return pendingToken;
    }

    return client.interceptors.request.use(async (config) => {
        if (!isAdmin() || safeMethods.has((config.method ?? 'get').toUpperCase()) || config.headers.has('X-CSRFToken')) return config;
        if (new URL(client.getUri(config), pageUrl).origin !== backendUrl.origin) return config;
        const cookie = pageUrl.hostname === backendUrl.hostname ? Cookies.get('csrftoken') : undefined;
        const token = cookie ?? await getToken();
        if (!isAdmin()) throw new Error('Administrative session changed before the request was sent.');
        config.headers.set('X-CSRFToken', token);
        return config;
    });
}
