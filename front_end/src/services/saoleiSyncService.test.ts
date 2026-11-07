import { beforeEach, describe, expect, it, vi } from 'vitest';

import { importPendingSaoleiVideos, refreshSaoleiCatalogue } from './saoleiSyncService';
import type { SaoleiSyncProgress } from './saoleiSyncService';

import type { SaoleiVideo } from '@/utils/accountlinks';

const { get, post } = vi.hoisted(() => ({
    get: vi.fn<(url: string, config?: unknown) => Promise<{ data: unknown }>>(),
    post: vi.fn<(url: string, data?: unknown, config?: unknown) => Promise<{ data: unknown }>>(),
}));
vi.mock('@/http', () => ({ default: { get, post } }));
const video = (id: number, overrides: Partial<SaoleiVideo> = {}): SaoleiVideo => ({
    id,
    remote_id: id + 1000,
    level: 'b',
    timems: 1000,
    bv: 4,
    nf: false,
    software: 'Arbiter',
    status: 0,
    upload_time: '2026-11-01T00:00:00Z',
    import_video: null,
    import_rejected: false,
    ...overrides,
});
const root = '/api/accountlink/saolei';

describe('frontend-controlled Saolei catalogue refresh and imports', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it.each([false, true])('refreshes catalogue pages sequentially without importing replays (full=%s)', async (full) => {
        const cursor = full ? 0 : 10;
        const firstPage = Promise.withResolvers<{ data: { cursor: number; has_more: boolean } }>();
        const progress = vi.fn<(value: SaoleiSyncProgress) => void>();
        post.mockResolvedValueOnce({ data: { cursor, upper_bound: 30 } }).
            mockReturnValueOnce(firstPage.promise).
            mockResolvedValueOnce({ data: { cursor: 30, has_more: false } });
        const result = refreshSaoleiCatalogue(101, full, () => false, progress);
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledTimes(2);
        });
        expect(post).toHaveBeenNthCalledWith(1, `${root}/101/sync/start`, { full }, expect.anything());
        expect(post).toHaveBeenNthCalledWith(2, `${root}/101/sync/page`, { cursor, upper_bound: 30 }, expect.anything());
        firstPage.resolve({ data: { cursor: 20, has_more: true } });
        await result;
        expect(post.mock.calls.map(([url]) => url)).toEqual([`${root}/101/sync/start`, `${root}/101/sync/page`, `${root}/101/sync/page`]);
        expect(post).toHaveBeenLastCalledWith(`${root}/101/sync/page`, { cursor: 20, upper_bound: 30 }, expect.objectContaining({ headers: { 'Content-Type': 'application/json' } }));
        expect(get).not.toHaveBeenCalled();
        expect(progress).toHaveBeenLastCalledWith({ stage: 'catalogue', pages: 2, completed: 0, failed: 0 });
    });

    it('records completion for an empty catalogue with one page call', async () => {
        post.mockResolvedValueOnce({ data: { cursor: 0, upper_bound: 0 } }).
            mockResolvedValueOnce({ data: { cursor: 0, has_more: false } });
        await refreshSaoleiCatalogue(101, false, () => false, vi.fn<() => void>());
        expect(post).toHaveBeenCalledTimes(2);
        expect(get).not.toHaveBeenCalled();
    });

    it('stops refreshing after an in-flight page completes when cancelled', async () => {
        let cancelled = false;
        const page = Promise.withResolvers<{ data: { cursor: number; has_more: boolean } }>();
        post.mockResolvedValueOnce({ data: { cursor: 0, upper_bound: 10 } }).mockReturnValueOnce(page.promise);
        const result = refreshSaoleiCatalogue(101, true, () => cancelled, vi.fn<() => void>());
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledTimes(2);
        });
        cancelled = true;
        page.resolve({ data: { cursor: 1, has_more: true } });
        await result;
        expect(get).not.toHaveBeenCalled();
        expect(post).toHaveBeenCalledTimes(2);
    });

    it('imports only eligible pending files sequentially without refreshing the catalogue', async () => {
        const firstImport = Promise.withResolvers<{ data: { status: string; import_video: number } }>();
        const progress = vi.fn<(value: SaoleiSyncProgress) => void>();
        const failure = vi.fn<(id: number, error: unknown) => void>();
        post.mockReturnValueOnce(firstImport.promise).
            mockRejectedValueOnce(Object.assign(new Error('file rejected'), { isAxiosError: true, response: { status: 400 } })).
            mockResolvedValueOnce({ data: { status: 'imported', import_video: 43 } });
        get.mockResolvedValue({ data: { items: [video(1), video(2), video(3), video(4, { import_rejected: true }), video(5, { software: 'Saolei.wang' }), video(6, { import_video: 46 })], next_after: null } });
        const result = importPendingSaoleiVideos(101, () => false, progress, failure);
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledTimes(1);
        });
        expect(post).toHaveBeenLastCalledWith(`${root}/videos/1/import`, undefined, expect.anything());
        firstImport.resolve({ data: { status: 'imported', import_video: 41 } });
        await result;
        expect(post.mock.calls.map(([url]) => url)).toEqual([`${root}/videos/1/import`, `${root}/videos/2/import`, `${root}/videos/3/import`]);
        expect(get).toHaveBeenCalledWith(`${root}/101/videos`, { params: { after: 0, pending: true } });
        expect(failure).toHaveBeenCalledOnce();
        expect(progress).toHaveBeenLastCalledWith({ stage: 'videos', pages: 0, completed: 3, failed: 1 });
    });

    it('stops importing after the current request completes when cancelled', async () => {
        let cancelled = false;
        const imported = Promise.withResolvers<{ data: { status: string; import_video: number } }>();
        get.mockResolvedValue({ data: { items: [video(1), video(2)], next_after: 2 } });
        post.mockReturnValueOnce(imported.promise);
        const result = importPendingSaoleiVideos(101, () => cancelled, vi.fn<() => void>(), vi.fn<() => void>());
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledTimes(1);
        });
        cancelled = true;
        imported.resolve({ data: { status: 'imported', import_video: 41 } });
        await result;
        expect(post).toHaveBeenCalledTimes(1);
        expect(get).toHaveBeenCalledTimes(1);
    });

    it('paginates pending files by local ID and stops on rate limits or upstream failures', async () => {
        for (const status of [429, 502]) {
            vi.resetAllMocks();
            post.mockResolvedValueOnce({ data: { status: 'imported', import_video: 1 } }).
                mockRejectedValueOnce(Object.assign(new Error('upstream failed'), { isAxiosError: true, response: { status } }));
            get.mockResolvedValueOnce({ data: { items: [video(1)], next_after: 1 } }).
                mockResolvedValueOnce({ data: { items: [video(2), video(3)], next_after: null } });
            await expect(importPendingSaoleiVideos(101, () => false, vi.fn<() => void>(), vi.fn<() => void>())).rejects.toMatchObject({ response: { status } });
            expect(get).toHaveBeenLastCalledWith(`${root}/101/videos`, { params: { after: 1, pending: true } });
            expect(post.mock.calls.map(([url]) => url)).toEqual([`${root}/videos/1/import`, `${root}/videos/2/import`]);
        }
    });
});
