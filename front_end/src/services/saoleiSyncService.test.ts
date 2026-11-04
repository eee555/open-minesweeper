import { beforeEach, describe, expect, it, vi } from 'vitest';

import { synchronizeSaolei } from './saoleiSyncService';
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

describe('frontend-controlled Saolei synchronization', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('waits for each page and import, preserves cursors, and continues after a definite file rejection', async () => {
        const firstImport = Promise.withResolvers<{ data: { status: string; import_video: number } }>();
        const progress = vi.fn<(value: SaoleiSyncProgress) => void>();
        const failure = vi.fn<(id: number, error: unknown) => void>();
        post.mockImplementation((url) => {
            if (url.endsWith('/start')) return Promise.resolve({ data: { cursor: 10, upper_bound: 30 } });
            if (url.endsWith('/page')) {
                const count = post.mock.calls.filter(([path]) => path.endsWith('/page')).length;
                return Promise.resolve({ data: { cursor: count === 1 ? 20 : 30, has_more: count === 1 } });
            }
            if (url.endsWith('/1/import')) return firstImport.promise;
            if (url.endsWith('/2/import')) return Promise.reject(Object.assign(new Error('file rejected'), { isAxiosError: true, response: { status: 400 } }));
            return Promise.resolve({ data: { status: 'imported', import_video: 43 } });
        });
        get.mockResolvedValue({ data: { items: [video(1), video(2), video(3), video(4, { import_rejected: true }), video(5, { software: 'Saolei.wang' })], next_after: null } });
        const result = synchronizeSaolei(101, false, () => false, progress, failure);
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledWith(`${root}/videos/1/import`, undefined, expect.anything());
        });
        expect(post).not.toHaveBeenCalledWith(`${root}/videos/2/import`, undefined, expect.anything());
        firstImport.resolve({ data: { status: 'imported', import_video: 41 } });
        await result;
        expect(post.mock.calls.map(([url]) => url)).toEqual([
            `${root}/101/sync/start`, `${root}/101/sync/page`, `${root}/101/sync/page`,
            `${root}/videos/1/import`, `${root}/videos/2/import`, `${root}/videos/3/import`,
        ]);
        expect(post).toHaveBeenCalledWith(`${root}/101/sync/page`, { cursor: 20, upper_bound: 30 }, expect.objectContaining({ headers: { 'Content-Type': 'application/json' } }));
        expect(failure).toHaveBeenCalledOnce();
        expect(progress).toHaveBeenLastCalledWith({ stage: 'videos', pages: 2, completed: 3, failed: 1 });
    });

    it('stops after an in-flight page completes when the dialog is closed', async () => {
        let cancelled = false;
        const page = Promise.withResolvers<{ data: { cursor: number; has_more: boolean } }>();
        post.mockResolvedValueOnce({ data: { cursor: 0, upper_bound: 10 } }).mockReturnValueOnce(page.promise);
        const result = synchronizeSaolei(101, true, () => cancelled, vi.fn<() => void>(), vi.fn<() => void>());
        await vi.waitFor(() => {
            expect(post).toHaveBeenCalledTimes(2);
        });
        cancelled = true;
        page.resolve({ data: { cursor: 1, has_more: true } });
        await result;
        expect(get).not.toHaveBeenCalled();
        expect(post).toHaveBeenCalledTimes(2);
    });

    it('uses local keyset pagination for pending files and stops on rate limits or network failures', async () => {
        for (const status of [429, 502]) {
            vi.resetAllMocks();
            post.mockResolvedValueOnce({ data: { cursor: 0, upper_bound: 0 } }).
                mockResolvedValueOnce({ data: { cursor: 0, has_more: false } }).
                mockResolvedValueOnce({ data: { status: 'imported', import_video: 1 } }).
                mockRejectedValueOnce(Object.assign(new Error('upstream failed'), { isAxiosError: true, response: { status } }));
            get.mockResolvedValueOnce({ data: { items: [video(1)], next_after: 1 } }).
                mockResolvedValueOnce({ data: { items: [video(2), video(3)], next_after: null } });
            await expect(synchronizeSaolei(101, false, () => false, vi.fn<() => void>(), vi.fn<() => void>())).rejects.toMatchObject({ response: { status } });
            expect(get).toHaveBeenLastCalledWith(`${root}/101/videos`, { params: { after: 1, pending: true } });
            expect(post).not.toHaveBeenCalledWith(`${root}/videos/3/import`, undefined, expect.anything());
        }
    });
});
