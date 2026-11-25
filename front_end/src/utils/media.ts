import { offlineLanguages } from '@/i18n/language';

export const mediaLanguages = offlineLanguages;

export function normalizeMediaLanguage(value: string): string {
    const normalized = value.trim();
    return mediaLanguages.some(({ lang }) => lang === normalized.toLowerCase()) ? normalized.toLowerCase() : normalized;
}

export function defaultMediaLanguage(format: string): 'en' | 'zh-cn' {
    return format.startsWith('g_') ? 'en' : 'zh-cn';
}

const languageNames: Record<string, string> = {
    ...Object.fromEntries(mediaLanguages.map(({ lang, text }) => [lang, text])),
    'zh-tw': '繁體中文',
    ja: '日本語',
    ko: '한국어',
    ru: 'Русский',
    de: 'Deutsch',
    fr: 'Français',
};

export function mediaLanguageLabel(value: string): string {
    const normalized = value.trim();
    return languageNames[normalized.toLowerCase()] ?? normalized;
}

/** 展示地址仅由前端生成；GitHub 仓库的当前地址需按数字 ID 单独获取。 */
export function mediaExternalUrl(format: string, suffix: string): string | undefined {
    const id = encodeURIComponent(suffix);
    switch (format) {
        case 'B_v': return `https://www.bilibili.com/video/${id}/`;
        case 'B_a': return `https://www.bilibili.com/read/cv${id}`;
        case 'c_p': return `https://saolei.wang/bbs/${id}`;
        default: return undefined;
    }
}

export function mediaEmbedUrl(format: string, suffix: string): string | undefined {
    return format === 'B_v' ? `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(suffix)}&page=1&autoplay=0&danmaku=0` : undefined;
}
