import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchVideoInfo = vi.hoisted(() => vi.fn());
const videoplayerstore = vi.hoisted(() => ({
    visible: false,
    id: 0,
    url: '',
}));

vi.mock('@/services/videoInfoService', () => ({ fetchVideoInfo }));
vi.mock('@/store', () => ({ videoplayerstore }));

describe('preview', () => {
    beforeEach(() => {
        fetchVideoInfo.mockReset();
        Object.assign(videoplayerstore, {
            visible: false,
            id: 0,
            url: '',
        });
    });

    it('opens a replay immediately without fetching its software', async () => {
        const { preview } = await import('./PlayerDialog');
        preview(12);

        expect(fetchVideoInfo).not.toHaveBeenCalled();
        expect(videoplayerstore.id).toBe(12);
        expect(videoplayerstore.url).toContain('/api/video/preview?id=12');
        expect(videoplayerstore.visible).toBe(true);
    });

    it.each([undefined, null, 0, -1])('does not open an invalid replay ID %s', async (id) => {
        const { preview } = await import('./PlayerDialog');

        preview(id);

        expect(fetchVideoInfo).not.toHaveBeenCalled();
        expect(videoplayerstore.url).toBe('');
        expect(videoplayerstore.visible).toBe(false);
    });
});
