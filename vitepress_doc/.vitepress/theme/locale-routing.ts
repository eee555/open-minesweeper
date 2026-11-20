import { docLocales, isDocLocale, type LocalizedPages } from '../locales.ts';

export function getLocaleRedirect(url: URL, base: string, pages: LocalizedPages, browserLanguage: string): string | undefined {
    const basePath = base.replace(/\/$/, '');
    if (url.pathname !== basePath && !url.pathname.startsWith(`${basePath}/`)) return;
    const path = url.pathname.slice(basePath.length).replace(/^\//, '').replace(/\.html$/, '').replace(/(^|\/)index$/, '$1');
    if (isDocLocale(path.split('/')[0])) return;
    const requested = url.searchParams.get('lang');
    const language = isDocLocale(requested) ? requested : browserLanguage.toLowerCase().split('-')[0];
    const locale = isDocLocale(language) ? language : 'en';
    const page = path.replace(/\/$/, '');
    // Aliases also exist for known pages that have no translation in the preferred language.
    for (const candidate of [locale, ...docLocales]) {
        const target = pages[candidate].find((entry) => entry.replace(/\/$/, '') === page);
        if (target !== undefined) return `${basePath}/${locale}/${target}${url.search}${url.hash}`;
    }
}
