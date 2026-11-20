import { onBeforeMount } from 'vue';

import i18n from '@/i18n';
import { resolveContentLanguage } from '@/i18n/language';
import { local } from '@/store';

export const languageOptions = [
    { lang: 'zh-cn', text: '简体中文' },
    { lang: 'en', text: 'English (99%)' },
    { lang: 'es', text: 'Español' },
    { lang: 'de', text: 'Deutsch (7%)' },
    { lang: 'pl', text: 'Polski (10%)' },
    { lang: 'dev', text: 'dev' },
] as const;

type Language = typeof languageOptions[number]['lang'];

function isLanguage(value: unknown): value is Language {
    return typeof value === 'string' && languageOptions.some((option) => option.lang === value);
}

export function changeLanguage(value: unknown): void {
    if (!isLanguage(value)) return;
    i18n.global.locale.value = value;
    document.documentElement.lang = value;
    local.value.language = value;
}

export function useLanguage(): { options: typeof languageOptions; changeLanguage: typeof changeLanguage } {
    onBeforeMount(() => {
        const { language } = local.value;
        changeLanguage(isLanguage(language) ? language : resolveContentLanguage(language));
    });
    return { options: languageOptions, changeLanguage };
}
