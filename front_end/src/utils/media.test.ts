import { describe, expect, it } from 'vitest';

import { mediaEmbedUrl, mediaExternalUrl } from './media';

describe('media source URLs', () => {
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
