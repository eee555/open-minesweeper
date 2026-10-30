import { afterEach, describe, expect, it, vi } from 'vitest';

import { getReplayPreviewUrl } from './replayLinks';

afterEach(() => vi.unstubAllEnvs());

describe('replay links', () => {
    it.each([['a', 'avf'], ['e', 'evf'], ['m', 'mvf'], ['r', 'rmv']] as const)('keeps the %s replay filename', (software, extension) => {
        vi.stubEnv('VITE_BASE_API', 'https://openms.top');
        const replayUrl = getReplayPreviewUrl(42, software);
        expect(replayUrl).toBe(`https://openms.top/api/video/preview?id=42.${extension}`);
    });

    it('encodes the replay filename', () => {
        vi.stubEnv('VITE_BASE_API', 'https://openms.top');
        const preview = new URL(getReplayPreviewUrl('a&b', 'e'));
        expect(preview.searchParams.get('id')).toBe('a&b.evf');
        expect([...preview.searchParams.keys()]).toEqual(['id']);
    });
});
