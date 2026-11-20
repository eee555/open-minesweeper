import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getAccountLinkUpdateErrorMessageKey, importMSGamesVideo, MSGamesTaskError, syncMSGamesVideos } from './accountLinkService';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/http', () => ({ default: { get, post } }));

describe('MSGames catalogue tasks and synchronous imports', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => {
        vi.useRealTimers();
        vi.resetAllMocks();
    });

    it('imports one replay directly without a custom timeout or polling', async () => {
        const result = { status: 'IMPORTED', import_video_id: 77, video_state: 'o' };
        post.mockResolvedValue({ data: result });
        await expect(importMSGamesVideo(7)).resolves.toEqual(result);
        expect(post).toHaveBeenCalledWith('/api/accountlink/msgames/videos/7/import', undefined, { signal: undefined });
        expect(get).not.toHaveBeenCalled();
    });

    it('waits through queued and running states before resolving a list sync', async () => {
        const result = { status: 'SYNCED', count: 3, video_update_time: '2026-11-19T00:00:00Z' };
        post.mockResolvedValue({ data: { id: 'sync-task', status: 'READY', return_value: null } });
        get.
            mockResolvedValueOnce({ data: { id: 'sync-task', status: 'RUNNING', return_value: null } }).
            mockResolvedValueOnce({ data: { id: 'sync-task', status: 'SUCCESSFUL', return_value: result } });
        let finished = false;
        const pending = syncMSGamesVideos(42).then((value) => {
            finished = true; return value;
        });
        await vi.advanceTimersByTimeAsync(2000);
        expect(finished).toBe(false);
        expect(post).toHaveBeenCalledWith('/api/accountlink/msgames/42/sync', undefined, { signal: undefined });
        expect(get).toHaveBeenCalledWith('/api/accountlink/msgames/tasks/sync-task', { signal: undefined });
        await vi.advanceTimersByTimeAsync(2000);
        await expect(pending).resolves.toEqual(result);
    });

    it.each([
        ['SUCCESSFUL', { type: 'error', object: 'import', category: 'timeout' }, 'import', 'timeout'],
        ['SUCCESSFUL', { type: 'error', object: 'accountlink', category: 'not_found' }, 'accountlink', 'not_found'],
        ['FAILED', null, 'import', 'task_failed'],
        ['SUCCESSFUL', null, 'import', 'response'],
        ['NULL', null, 'import', 'response'],
    ] as const)('preserves localized error fields for %s task failures', async (status, returnValue, object, category) => {
        post.mockResolvedValue({ data: { id: 'sync-task', status: 'READY', return_value: null } });
        get.mockResolvedValue({ data: { id: 'sync-task', status, return_value: returnValue } });
        const task = syncMSGamesVideos(42);
        const pending = expect(task).rejects.toMatchObject({ object, category });
        await vi.advanceTimersByTimeAsync(2000);
        await pending;
        await expect(task).rejects.toBeInstanceOf(MSGamesTaskError);
    });

    it('stops polling after the component cancels without cancelling the server task', async () => {
        post.mockResolvedValue({ data: { id: 'sync-task', status: 'READY', return_value: null } });
        const controller = new AbortController();
        const pending = expect(syncMSGamesVideos(42, controller.signal)).rejects.toThrow();
        controller.abort();
        await vi.advanceTimersByTimeAsync(2000);
        await pending;
        expect(get).not.toHaveBeenCalled();
    });

    it('does not misclassify a lost status response as a completed list sync failure', async () => {
        post.mockResolvedValue({ data: { id: 'sync-task', status: 'READY', return_value: null } });
        const networkError = new Error('connection lost');
        get.mockRejectedValue(networkError);
        const pending = expect(syncMSGamesVideos(42)).rejects.toBe(networkError);
        await vi.advanceTimersByTimeAsync(2000);
        await pending;
    });
});

describe('getAccountLinkUpdateErrorMessageKey', () => {
    it('maps known backend account update categories to update error messages', () => {
        const cases = [
            ['cooldown', 'accountlink.updateError.cooldown'],
            ['empty', 'accountlink.updateError.empty'],
            ['indexerror', 'accountlink.updateError.indexerror'],
            ['pageempty', 'accountlink.updateError.pageempty'],
            ['requestexception', 'accountlink.updateError.requestexception'],
            ['timeout', 'accountlink.updateError.timeout'],
        ] as const;

        for (const [category, messageKey] of cases) {
            expect(getAccountLinkUpdateErrorMessageKey(category)).toBe(messageKey);
        }
    });

    it('falls back to the unknown message for missing or unexpected categories', () => {
        expect(getAccountLinkUpdateErrorMessageKey()).toBe('accountlink.updateError.unknown');
        expect(getAccountLinkUpdateErrorMessageKey('new-backend-category')).toBe('accountlink.updateError.unknown');
    });
});
