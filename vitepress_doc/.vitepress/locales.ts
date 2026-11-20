export const docLocales = ['zh', 'en', 'es'] as const;
export type DocLocale = typeof docLocales[number];
export type LocalizedPages = Record<DocLocale, string[]>;

export const languageNames = { zh: '简体中文', en: 'English', es: 'Español' };
export const missingTitles = {
    zh: '此页面暂无中文版本',
    en: 'This page is not available in English',
    es: 'Esta página aún no está disponible en español',
};

export function isDocLocale(value: string | null): value is DocLocale {
    return docLocales.some((locale) => locale === value);
}
