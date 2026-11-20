import { getLocalizedPages } from './.vitepress/localized-pages';

import { docLocales } from './.vitepress/locales';

export default {
    watch: docLocales.map((locale) => `${locale}/**/*.md`),
    paths() {
        const pages = getLocalizedPages();
        return [...new Set(Object.values(pages).flat())].flatMap((page) => {
            const path = page.endsWith('/') ? `${page}index` : page;
            const aliases = page ? [path] : [];
            for (const locale of docLocales) {
                if (!pages[locale].includes(page)) aliases.push(`${locale}/${path}`);
            }
            return aliases.map((path) => ({ params: { path } }));
        });
    },
};
