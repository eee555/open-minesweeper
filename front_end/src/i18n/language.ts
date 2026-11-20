export const offlineLanguages = [
    { lang: 'zh-cn', text: '简体中文' },
    { lang: 'en', text: 'English' },
    { lang: 'es', text: 'Español' },
] as const;

export function resolveContentLanguage(language: unknown): 'zh-cn' | 'en' | 'es' {
    const primary = typeof language === 'string' ? language.toLowerCase().split('-')[0] : '';
    if (primary === 'zh') return 'zh-cn';
    return primary === 'es' ? 'es' : 'en';
}
