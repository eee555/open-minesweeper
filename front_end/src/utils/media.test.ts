import { describe, expect, it } from 'vitest';

import { defaultMediaLanguage, mediaEmbedUrl, mediaExternalUrl, mediaLanguageLabel, normalizeMediaLanguage } from './media';

describe('media source URLs', () => {
    it('defaults by platform and preserves custom content languages', () => {
        expect(defaultMediaLanguage('g_r')).toBe('en');
        for (const format of ['B_v', 'B_a', 'c_p']) expect(defaultMediaLanguage(format)).toBe('zh-cn');
        expect(normalizeMediaLanguage(' EN ')).toBe('en');
        expect(normalizeMediaLanguage(' ES ')).toBe('es');
        expect(normalizeMediaLanguage(' 日本語 ')).toBe('日本語');
        expect(mediaLanguageLabel('zh-cn')).toBe('简体中文');
        expect(mediaLanguageLabel('es')).toBe('Español');
        expect(mediaLanguageLabel(' Klingon ')).toBe('Klingon');
        expect(mediaLanguageLabel('')).toBe('');
    });

    it('preserves existing source links and video playback options', () => {
        expect(mediaExternalUrl('B_v', 'BV1xx411c7mD')).toBe('https://www.bilibili.com/video/BV1xx411c7mD/');
        expect(mediaExternalUrl('B_a', '1646742')).toBe('https://www.bilibili.com/read/cv1646742');
        expect(mediaExternalUrl('c_p', '9786')).toBe('https://saolei.wang/bbs/9786');
        expect(mediaEmbedUrl('B_v', 'BV1xx411c7mD')).toBe('https://player.bilibili.com/player.html?bvid=BV1xx411c7mD&page=1&autoplay=0&danmaku=0');
    });

    it('does not invent GitHub links or allow suffixes to inject URL parameters', () => {
        expect(mediaExternalUrl('g_r', '42')).toBeUndefined();
        expect(mediaExternalUrl('unknown', '42')).toBeUndefined();
        expect(mediaEmbedUrl('B_a', '1')).toBeUndefined();
        expect(mediaEmbedUrl('c_p', '1')).toBeUndefined();
        expect(mediaEmbedUrl('g_r', '42')).toBeUndefined();
        expect(mediaEmbedUrl('B_v', 'id&autoplay=1')).toContain('id%26autoplay%3D1&page=1&autoplay=0');
    });
});
