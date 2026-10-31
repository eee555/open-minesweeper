import { afterEach, describe, expect, it, vi } from 'vitest';

import { getReplayPreviewUrl, getStrangeDustAnalyzerUrl } from './replayLinks';

afterEach(() => vi.unstubAllEnvs());

describe('replay links', () => {
    it('builds preview links using only the replay ID', () => {
        vi.stubEnv('VITE_BASE_API', 'https://openms.top');
        const replayUrl = getReplayPreviewUrl(42);
        expect(replayUrl).toBe('https://openms.top/api/video/preview?id=42');
        const analyzer = new URL(getStrangeDustAnalyzerUrl(replayUrl));
        expect(analyzer.origin + analyzer.pathname).toBe('https://strange-dust.github.io/minesweeper-replay-analyzer/');
        expect(analyzer.searchParams.get('replay')).toBe(replayUrl);
        expect([...analyzer.searchParams.keys()]).toEqual(['replay']);
    });

    it('encodes the replay ID and the nested analyzer URL', () => {
        vi.stubEnv('VITE_BASE_API', 'https://openms.top');
        const preview = new URL(getReplayPreviewUrl('a&b'));
        expect(preview.searchParams.get('id')).toBe('a&b');
        expect([...preview.searchParams.keys()]).toEqual(['id']);
        const replayUrl = `${preview.href}&name=${encodeURIComponent('原始录像.evf')}#frame`;
        const analyzer = new URL(getStrangeDustAnalyzerUrl(replayUrl));
        expect(analyzer.searchParams.get('replay')).toBe(replayUrl);
        expect([...analyzer.searchParams.keys()]).toEqual(['replay']);
        expect(analyzer.hash).toBe('');
    });
});
