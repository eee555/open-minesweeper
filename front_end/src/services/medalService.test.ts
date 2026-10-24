import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { MedalStateRecord, PlayerMedals } from './medalService';

const { axiosGet, axiosPut, serviceConfig } = vi.hoisted(() => ({
    axiosGet: vi.fn(),
    axiosPut: vi.fn(),
    serviceConfig: { value: { userInfoBatchDelay: 1, userInfoBatchSize: 100 } },
}));
vi.mock('@/http', () => ({ default: { get: axiosGet, put: axiosPut } }));
vi.mock('./store', () => ({ serviceConfig }));

function summary(scanPending = false, score = 0): PlayerMedals {
    return { scan_pending: scanPending, score, max_pins: 6, pin_ids: [], pins: [], series: [] };
}

function deferred() {
    let resolve!: (value: { data: PlayerMedals }) => void;
    let reject!: (reason: Error) => void;
    const promise = new Promise<{ data: PlayerMedals }>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

describe('shared medal image parts', () => {
    it('reuses one gold base and draws the number in the page', async () => {
        const { medalArtPlate, medalArtUrl } = await import('./medalService');
        expect(medalArtUrl('神速', 'ability.bvs.e', 50000)).toBe('/assets/medals/speed.webp?v=5');
        expect(medalArtUrl('神速', 'ability.bvs.b', 15000)).toBe('/assets/medals/speed.webp?v=5');
        expect(medalArtPlate('神速', 50000)).toBe('5');
        expect(medalArtPlate('神速', 15000)).toBe('1.5');
        expect(medalArtPlate('破境', 20000)).toBe('20');
        expect(medalArtPlate('实名在册', 1)).toBe('');
        expect(medalArtPlate('原始股东', 1000)).toBe('');
        expect(medalArtUrl('实名在册', 'novice.realname', 1)).toBe('/assets/medals/registered.webp?v=5');
        expect(medalArtUrl('原始股东', 'shareholder.origin', 1000)).toBe('/assets/medals/shareholder.webp?v=5');
        expect(medalArtUrl('神速', 'ability.bvs.e', null)).toBeUndefined();
        expect(medalArtUrl('unknown', 'unknown', 1)).toBeUndefined();
    });

    it('maps a medal code prefix onto the series used by the art', async () => {
        const { medalSeriesFromCode } = await import('./medalService');
        expect(medalSeriesFromCode('ability.time.b')).toBe('破境');
        expect(medalSeriesFromCode('ability.time.nf.e')).toBe('盲扫破境');
        expect(medalSeriesFromCode('ability.bvs.i')).toBe('神速');
        expect(medalSeriesFromCode('ability.bvs.nf.b')).toBe('盲扫神速');
        expect(medalSeriesFromCode('ability.stnb.e')).toBe('通明');
        expect(medalSeriesFromCode('ability.stnb.nf.b')).toBe('盲扫通明');
        expect(medalSeriesFromCode('ability.thrp.nf.b')).toBe('盲扫·精工');
        expect(medalSeriesFromCode('ability.thrp.nf.three')).toBe('三阶盲扫·精工');
        expect(medalSeriesFromCode('ability.thrp.fl.e')).toBe('标旗·精工');
        expect(medalSeriesFromCode('ability.thrp.fl.three')).toBe('三阶标旗·精工');
        expect(medalSeriesFromCode('novice.realname')).toBe('实名在册');
        expect(medalSeriesFromCode('novice.review')).toBe('录像过审');
        expect(medalSeriesFromCode('novice.levels')).toBe('扫雷新秀');
        expect(medalSeriesFromCode('novice.levels_nf')).toBe('盲扫新秀');
        expect(medalSeriesFromCode('novice.modes')).toBe('走马观花');
        expect(medalSeriesFromCode('novice.saolei')).toBe('旧迹新篇');
        expect(medalSeriesFromCode('shareholder.origin')).toBe('原始股东');
        expect(medalSeriesFromCode('manual.override')).toBe('');
    });
});

describe('shared player medal summaries', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        vi.resetModules();
        axiosGet.mockReset();
        axiosPut.mockReset();
    });
    afterEach(() => {
        vi.clearAllTimers();
        vi.useRealTimers();
    });

    it('shares inflight requests and cached summaries across sidebar and page', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        const pending = deferred();
        axiosGet.mockReturnValue(pending.promise);
        const sidebar = vi.fn<() => void>();
        const page = vi.fn<() => void>();
        const stopSidebar = subscribePlayerMedals(1, sidebar, vi.fn<() => void>());
        const stopPage = subscribePlayerMedals(1, page, vi.fn<() => void>());
        expect(axiosGet).toHaveBeenCalledTimes(1);
        const data = summary();
        pending.resolve({ data });
        await fetchPlayerMedals(1);
        expect(sidebar).toHaveBeenLastCalledWith(data);
        expect(page).toHaveBeenLastCalledWith(data);
        stopPage();
        subscribePlayerMedals(1, page, vi.fn<() => void>());
        expect(axiosGet).toHaveBeenCalledTimes(1);
        stopSidebar();
    });

    it.each(['resolve', 'reject'] as const)('ignores late %s after changing players', async (outcome) => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        const old = deferred();
        axiosGet.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: summary(false, 2) });
        const receive = vi.fn<() => void>();
        const failed = vi.fn<() => void>();
        const stop = subscribePlayerMedals(1, receive, failed);
        stop();
        subscribePlayerMedals(2, receive, failed);
        await fetchPlayerMedals(2);
        const oldRequest = fetchPlayerMedals(1).catch(() => undefined);
        if (outcome === 'resolve') old.resolve({ data: summary(false, 1) });
        else old.reject(new Error('old request failed'));
        await oldRequest;
        expect(receive).toHaveBeenCalledTimes(1);
        expect(receive).toHaveBeenLastCalledWith(summary(false, 2));
        expect(failed).not.toHaveBeenCalled();
    });

    it('polls once per player and publishes the completed scan to all subscribers', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        axiosGet.mockResolvedValueOnce({ data: summary(true) }).mockResolvedValue({ data: summary(false, 10) });
        const sidebar = vi.fn<() => void>();
        const page = vi.fn<() => void>();
        subscribePlayerMedals(1, sidebar, vi.fn<() => void>());
        subscribePlayerMedals(1, page, vi.fn<() => void>());
        await fetchPlayerMedals(1);
        await vi.advanceTimersByTimeAsync(2000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
        expect(sidebar).toHaveBeenLastCalledWith(summary(false, 10));
        expect(page).toHaveBeenLastCalledWith(summary(false, 10));
        await vi.advanceTimersByTimeAsync(60_000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('caps pending scans at ten retries and permits an explicit retry', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals, refreshPlayerMedals } = await import('./medalService');
        axiosGet.mockResolvedValue({ data: summary(true) });
        subscribePlayerMedals(1, vi.fn<() => void>(), vi.fn<() => void>());
        await fetchPlayerMedals(1);
        await vi.advanceTimersByTimeAsync(60_000);
        expect(axiosGet).toHaveBeenCalledTimes(11);
        refreshPlayerMedals(1);
        await fetchPlayerMedals(1);
        expect(axiosGet).toHaveBeenCalledTimes(12);
    });

    it('stops polling when the last subscriber leaves, including an inflight response', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        const pending = deferred();
        axiosGet.mockReturnValue(pending.promise);
        const receive = vi.fn<() => void>();
        const stop = subscribePlayerMedals(1, receive, vi.fn<() => void>());
        stop();
        pending.resolve({ data: summary(true) });
        await fetchPlayerMedals(1);
        await vi.advanceTimersByTimeAsync(60_000);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(receive).not.toHaveBeenCalled();
        const stopAgain = subscribePlayerMedals(1, receive, vi.fn<() => void>());
        await fetchPlayerMedals(1);
        stopAgain();
        await vi.advanceTimersByTimeAsync(60_000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('refreshes expired cached summaries when a viewer returns', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        axiosGet.mockResolvedValue({ data: summary() });
        const stop = subscribePlayerMedals(1, vi.fn<() => void>(), vi.fn<() => void>());
        await fetchPlayerMedals(1);
        stop();
        await vi.advanceTimersByTimeAsync(30_001);
        subscribePlayerMedals(1, vi.fn<() => void>(), vi.fn<() => void>());
        await fetchPlayerMedals(1);
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('invalidates on saving pins and rejects stale responses from before the save', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals, saveMedalPins } = await import('./medalService');
        const old = deferred();
        axiosGet.mockReturnValueOnce(old.promise).mockResolvedValue({ data: summary(false, 2) });
        axiosPut.mockResolvedValue({});
        const receive = vi.fn<() => void>();
        subscribePlayerMedals(1, receive, vi.fn<() => void>());
        const oldRequest = fetchPlayerMedals(1);
        await saveMedalPins([], 1);
        await fetchPlayerMedals(1);
        old.resolve({ data: summary(false, 1) });
        await oldRequest;
        expect(receive).toHaveBeenCalledTimes(1);
        expect(receive).toHaveBeenLastCalledWith(summary(false, 2));
        expect(await fetchPlayerMedals(1)).toEqual(summary(false, 2));
    });

    it('bounds retries after scan polling fails and keeps the last summary', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals } = await import('./medalService');
        axiosGet.mockResolvedValueOnce({ data: summary(true) }).mockRejectedValue(new Error('offline'));
        const receive = vi.fn<() => void>();
        const failed = vi.fn<() => void>();
        subscribePlayerMedals(1, receive, failed);
        await fetchPlayerMedals(1);
        await vi.advanceTimersByTimeAsync(60_000);
        expect(axiosGet).toHaveBeenCalledTimes(11);
        expect(receive).toHaveBeenCalledTimes(1);
        expect(failed).toHaveBeenCalledTimes(10);
    });

    it('only refreshes the player whose pins were saved', async () => {
        const { subscribePlayerMedals, fetchPlayerMedals, saveMedalPins } = await import('./medalService');
        axiosGet.mockResolvedValue({ data: summary() });
        axiosPut.mockResolvedValue({});
        subscribePlayerMedals(1, vi.fn<() => void>(), vi.fn<() => void>());
        subscribePlayerMedals(2, vi.fn<() => void>(), vi.fn<() => void>());
        await Promise.all([fetchPlayerMedals(1), fetchPlayerMedals(2)]);
        await saveMedalPins([], 1);
        await fetchPlayerMedals(1);
        expect(axiosGet).toHaveBeenCalledTimes(3);
        expect(axiosGet).toHaveBeenLastCalledWith('/api/medal/players/1');
    });
});

function stateRecord(overrides: Partial<MedalStateRecord> = {}): MedalStateRecord {
    return { code: 'ability.time.e', stage: 30000, timestamp: 1761123456, scope: '', tournament: null, rank: null, ...overrides };
}

async function loadMedalState() {
    vi.resetModules();
    const { fetchPlayerMedalState } = await import('./medalService');
    return fetchPlayerMedalState;
}

function waitForMedalStateBatch() {
    return new Promise((resolve) => {
        setTimeout(resolve, serviceConfig.value.userInfoBatchDelay + 30);
    });
}

describe('player medal state for name hover', () => {
    beforeEach(() => {
        axiosGet.mockReset();
        serviceConfig.value.userInfoBatchDelay = 1;
        serviceConfig.value.userInfoBatchSize = 100;
    });

    it('does not request when the user id is zero', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        await expect(fetchPlayerMedalState(0)).resolves.toEqual([]);
        expect(axiosGet).not.toHaveBeenCalled();
    });

    it('batches ids into one state request and keeps the granted rows in memory', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        const expert = stateRecord();
        const novice = stateRecord({ code: 'novice.realname', stage: 1 });
        const undated = stateRecord({ code: 'novice.review', stage: 1, timestamp: null });
        axiosGet.mockResolvedValueOnce({
            data: [
                { user_id: 1, grants: [stateRecord({ stage: 0 }), expert] },
                { user_id: 2, grants: [novice, undated] },
            ],
        });

        const first = fetchPlayerMedalState(1);
        const second = fetchPlayerMedalState(2);
        const missing = fetchPlayerMedalState(3);
        const skipped = fetchPlayerMedalState(0);
        await waitForMedalStateBatch();

        await expect(skipped).resolves.toEqual([]);
        await expect(first).resolves.toEqual([expert]);
        await expect(second).resolves.toEqual([novice, undated]);
        await expect(missing).resolves.toEqual([]);
        await expect(fetchPlayerMedalState(1)).resolves.toEqual([expert]);
        await expect(fetchPlayerMedalState(3)).resolves.toEqual([]);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(axiosGet).toHaveBeenCalledWith('/api/medal/players/state', { params: { ids: '1,2,3' } });
    });

    it('remembers an empty state list and retries after a failed request', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        axiosGet.mockResolvedValueOnce({ data: [] });
        const empty = fetchPlayerMedalState(7);
        await waitForMedalStateBatch();
        await expect(empty).resolves.toEqual([]);
        await expect(fetchPlayerMedalState(7)).resolves.toEqual([]);

        axiosGet.mockRejectedValueOnce(new Error('offline'));
        const failed = fetchPlayerMedalState(8);
        const captured = failed.catch((error: unknown) => error);
        await waitForMedalStateBatch();
        await expect(captured).resolves.toBeInstanceOf(Error);

        const expert = stateRecord();
        axiosGet.mockResolvedValueOnce({ data: [{ user_id: 8, grants: [expert] }] });
        const retried = fetchPlayerMedalState(8);
        await waitForMedalStateBatch();
        await expect(retried).resolves.toEqual([expert]);
        expect(axiosGet).toHaveBeenCalledTimes(3);
        expect(axiosGet).toHaveBeenLastCalledWith('/api/medal/players/state', { params: { ids: '8' } });
    });

    it('splits ids above the batch size into another state request', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        serviceConfig.value.userInfoBatchSize = 2;
        axiosGet.mockResolvedValue({ data: [] });
        const pending = Promise.all([fetchPlayerMedalState(1), fetchPlayerMedalState(2), fetchPlayerMedalState(3)]);
        await waitForMedalStateBatch();
        await waitForMedalStateBatch();
        await pending;
        expect(axiosGet).toHaveBeenCalledTimes(2);
        expect(axiosGet).toHaveBeenNthCalledWith(1, '/api/medal/players/state', { params: { ids: '1,2' } });
        expect(axiosGet).toHaveBeenNthCalledWith(2, '/api/medal/players/state', { params: { ids: '3' } });
    });
});
