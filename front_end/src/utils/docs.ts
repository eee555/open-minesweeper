import { resolveContentLanguage } from '@/i18n/language';

export function getDocsUrl(path: string, language = 'en'): string {
    if (import.meta.env.VITE_OFFLINE_ANALYZER === 'true') {
        const locale = resolveContentLanguage(language);
        const directory = locale === 'zh-cn' ? 'help' : `help/${locale}`;
        return `${directory}/${path}.html`;
    }
    const base = typeof import.meta.env.VITE_DOCS_URL === 'string' && import.meta.env.VITE_DOCS_URL.length > 0
        ? import.meta.env.VITE_DOCS_URL
        : import.meta.env.DEV ? 'http://localhost:5173/docs/' : '/docs/';
    const normalizedBase = base.endsWith('/') ? base : `${base}/`;
    return `${normalizedBase}${path}`;
}
