import { afterEach, describe, expect, it, vi } from 'vitest';

import { getDocsUrl } from './docs';

afterEach(() => vi.unstubAllEnvs());

describe('getDocsUrl', () => {
    it.each([['zh-cn', 'help/guide/replay-expressions.html'], ['en', 'help/en/guide/replay-expressions.html'], ['es-MX', 'help/es/guide/replay-expressions.html']])('opens bundled expression help in offline mode for %s', (language, expected) => {
        vi.stubEnv('VITE_OFFLINE_ANALYZER', 'true');
        expect(getDocsUrl('guide/replay-expressions', language)).toBe(expected);
    });
    it.each(['zh-cn', 'ZH-TW', 'en', 'fr'])('leaves online language selection to VitePress for %s', (language) => {
        vi.stubEnv('VITE_OFFLINE_ANALYZER', 'false');
        vi.stubEnv('VITE_DOCS_URL', '/docs/');
        expect(getDocsUrl('', language)).toBe('/docs/');
        expect(getDocsUrl('guide/replay-expressions', language)).toBe('/docs/guide/replay-expressions');
    });

    it.each(['https://example.com/help', 'https://example.com/help/'])('uses the configured documentation base %s', (base) => {
        vi.stubEnv('VITE_DOCS_URL', base);
        expect(getDocsUrl('guide/tournament?from=menu#auto-upload')).toBe('https://example.com/help/guide/tournament?from=menu#auto-upload');
    });

    it.each([
        [true, 'http://localhost:5173/docs/guide/replay-expressions'],
        [false, '/docs/guide/replay-expressions'],
    ])('uses the default documentation base when DEV is %s', (dev, expected) => {
        vi.stubEnv('VITE_DOCS_URL', '');
        vi.stubEnv('DEV', dev);
        expect(getDocsUrl('guide/replay-expressions')).toBe(expected);
    });
});
