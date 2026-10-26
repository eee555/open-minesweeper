import { existsSync } from 'node:fs';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { MedalStateRecord, PlayerMedals } from './medalService';

import { MedalSeries } from '@/utils/medal_const';

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
    it('preserves unknown series when looking up a localized name', async () => {
        const { medalSeriesLabel } = await import('./medalService');
        for (const series of ['unknown', '', 'constructor', '__proto__']) {
            expect(medalSeriesLabel(series, 'en')).toBe(series);
            expect(medalSeriesLabel(series, 'zh-cn')).toBe(series);
        }
    });

    it('has localized names and image mappings for every serialized series', async () => {
        const { medalArtUrl, medalSeriesLabel } = await import('./medalService');
        for (const series of Object.values(MedalSeries)) {
            expect(medalSeriesLabel(series, 'en')).not.toBe(series);
            expect(medalSeriesLabel(series, 'zh-cn')).not.toBe(series);
            const url = medalArtUrl(series, 'catalog.item', 1);
            if (url === undefined || url === '') throw new Error(`Missing medal image mapping: ${series}`);
            expect(url).toMatch(/^\/assets\/medals\/[\w-]+\.webp\?v=5$/);
            const [assetPath] = url.split('?');
            expect(existsSync(new URL(`../../public${assetPath}`, import.meta.url))).toBe(true);
        }
    });

    it('reuses one gold base and draws the number in the page', async () => {
        const { medalArtPlate, medalArtUrl } = await import('./medalService');
        expect(medalArtUrl(MedalSeries.SPEED, 'ability.bvs.e', 50000)).toBe('/assets/medals/speed.webp?v=5');
        expect(medalArtUrl(MedalSeries.SPEED, 'ability.bvs.b', 15000)).toBe('/assets/medals/speed.webp?v=5');
        expect(medalArtPlate(MedalSeries.SPEED, 50000)).toBe('5');
        expect(medalArtPlate(MedalSeries.SPEED, 15000)).toBe('1.5');
        expect(medalArtPlate(MedalSeries.BREAKTHROUGH, 20000)).toBe('20');
        expect(medalArtPlate(MedalSeries.REGISTERED, 1)).toBe('');
        expect(medalArtPlate(MedalSeries.SHAREHOLDER, 1000)).toBe('');
        expect(medalArtUrl(MedalSeries.REGISTERED, 'novice.realname', 1)).toBe('/assets/medals/registered.webp?v=5');
        expect(medalArtUrl(MedalSeries.SHAREHOLDER, 'shareholder.origin', 1000)).toBe('/assets/medals/shareholder.webp?v=5');
        expect(medalArtUrl(MedalSeries.SPEED, 'ability.bvs.e', null)).toBeUndefined();
        expect(medalArtUrl('unknown', 'unknown', 1)).toBeUndefined();
    });

    it('maps a medal code prefix onto the series used by the art', async () => {
        const { medalSeriesFromCode } = await import('./medalService');
        expect(medalSeriesFromCode('ability.time.b')).toBe(MedalSeries.BREAKTHROUGH);
        expect(medalSeriesFromCode('ability.time.nf.e')).toBe(MedalSeries.FLAGLESS_BREAKTHROUGH);
        expect(medalSeriesFromCode('ability.bvs.i')).toBe(MedalSeries.SPEED);
        expect(medalSeriesFromCode('ability.bvs.nf.b')).toBe(MedalSeries.FLAGLESS_SPEED);
        expect(medalSeriesFromCode('ability.stnb.e')).toBe(MedalSeries.MASTERY);
        expect(medalSeriesFromCode('ability.stnb.nf.b')).toBe(MedalSeries.FLAGLESS_MASTERY);
        expect(medalSeriesFromCode('ability.thrp.nf.b')).toBe(MedalSeries.FLAGLESS_PRECISION);
        expect(medalSeriesFromCode('ability.thrp.nf.three')).toBe(MedalSeries.THREE_FLAGLESS_PRECISION);
        expect(medalSeriesFromCode('ability.thrp.fl.e')).toBe(MedalSeries.FLAGGED_PRECISION);
        expect(medalSeriesFromCode('ability.thrp.fl.three')).toBe(MedalSeries.THREE_FLAGGED_PRECISION);
        expect(medalSeriesFromCode('novice.realname')).toBe(MedalSeries.REGISTERED);
        expect(medalSeriesFromCode('novice.review')).toBe(MedalSeries.REVIEWED);
        expect(medalSeriesFromCode('novice.levels')).toBe(MedalSeries.LEVELS);
        expect(medalSeriesFromCode('novice.levels_nf')).toBe(MedalSeries.LEVELS_NF);
        expect(medalSeriesFromCode('novice.modes')).toBe(MedalSeries.MODES);
        expect(medalSeriesFromCode('novice.saolei')).toBe(MedalSeries.SAOLEI);
        expect(medalSeriesFromCode('shareholder.origin')).toBe(MedalSeries.SHAREHOLDER);
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
        setTimeout(resolve, 0);
    });
}

describe('player medal state for name hover', () => {
    beforeEach(() => {
        axiosGet.mockReset();
        serviceConfig.value.userInfoBatchDelay = 500;
        serviceConfig.value.userInfoBatchSize = 100;
    });

    it('does not request when the user id is zero', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        await expect(fetchPlayerMedalState(0)).resolves.toEqual([]);
        expect(axiosGet).not.toHaveBeenCalled();
    });

    it('invalidates the affected hover cache on a medal refresh without touching other players or polling', async () => {
        const fetchPlayerMedalState = await loadMedalState();
        const { cachedPlayerMedalState, medalStateVersions, refreshPlayerMedals } = await import('./medalService');
        const shareholder = stateRecord({ code: 'shareholder.origin', stage: 1000 });
        axiosGet.mockResolvedValueOnce({ data: [{ user_id: 3, grants: [shareholder] }, { user_id: 4, grants: [shareholder] }] });
        const initial = Promise.all([fetchPlayerMedalState(3), fetchPlayerMedalState(4)]);
        await waitForMedalStateBatch();
        await initial;
        refreshPlayerMedals(3);
        expect(cachedPlayerMedalState(3)).toBeUndefined();
        expect(cachedPlayerMedalState(4)).toEqual([shareholder]);
        expect(medalStateVersions[3]).toBe(1);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        axiosGet.mockResolvedValueOnce({ data: [{ user_id: 3, grants: [] }] });
        const updated = fetchPlayerMedalState(3);
        await waitForMedalStateBatch();
        expect(await updated).toEqual([]);
        expect(await fetchPlayerMedalState(4)).toEqual([shareholder]);
        expect(axiosGet).toHaveBeenCalledTimes(2);
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
        expect(axiosGet).not.toHaveBeenCalled();
        await waitForMedalStateBatch();
        expect(axiosGet).toHaveBeenCalledTimes(1);

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

describe('bounded synchronization after uploads', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        vi.resetModules();
        axiosGet.mockReset();
    });
    afterEach(() => {
        vi.clearAllTimers();
        vi.useRealTimers();
    });

    it('waits for the worker and updates page, pins and hover cache together', async () => {
        const api = await import('./medalService');
        axiosGet.mockResolvedValueOnce({ data: [{ user_id: 1, grants: [] }] });
        const cached = api.fetchPlayerMedalState(1);
        await vi.advanceTimersByTimeAsync(0);
        await cached;
        axiosGet.mockResolvedValueOnce({ data: summary(false, 1) });
        const page = vi.fn<() => void>();
        const pins = vi.fn<() => void>();
        api.subscribePlayerMedals(1, page, vi.fn<() => void>());
        api.subscribePlayerMedals(1, pins, vi.fn<() => void>());
        await api.fetchPlayerMedals(1);
        axiosGet.mockClear();
        axiosGet.mockResolvedValueOnce({ data: { user_id: 1, pending: true } }).
            mockResolvedValueOnce({ data: { user_id: 1, pending: false } }).
            mockResolvedValueOnce({ data: summary(false, 2) });
        api.syncMedalsAfterUpload();
        api.syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(1000);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        expect(page).toHaveBeenLastCalledWith(summary(false, 1));
        await vi.advanceTimersByTimeAsync(2000);
        expect(axiosGet).toHaveBeenCalledTimes(3);
        expect(page).toHaveBeenLastCalledWith(summary(false, 2));
        expect(pins).toHaveBeenLastCalledWith(summary(false, 2));
        expect(api.medalStateVersions[1]).toBe(1);
        axiosGet.mockResolvedValue({ data: [{ user_id: 1, grants: [] }] });
        const updated = api.fetchPlayerMedalState(1);
        await vi.advanceTimersByTimeAsync(0);
        await updated;
        await vi.advanceTimersByTimeAsync(300_000);
        expect(axiosGet).toHaveBeenCalledTimes(4);
    });

    it('caps a missing worker at eight lightweight requests', async () => {
        const { syncMedalsAfterUpload } = await import('./medalService');
        axiosGet.mockResolvedValue({ data: { user_id: 1, pending: true } });
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(600_000);
        expect(axiosGet).toHaveBeenCalledTimes(8);
        expect(axiosGet.mock.calls.every(([url]) => url === '/api/medal/refresh-status')).toBe(true);
    });

    it('merges batches and ignores idle responses predating a newer upload', async () => {
        const { syncMedalsAfterUpload } = await import('./medalService');
        const response = Promise.withResolvers<{ data: { user_id: number; pending: boolean } }>();
        axiosGet.mockReturnValueOnce(response.promise).mockResolvedValue({ data: { user_id: 1, pending: false } });
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(1000);
        for (let i = 0; i < 100; i += 1) syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(30_000);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        response.resolve({ data: { user_id: 1, pending: false } });
        await vi.advanceTimersByTimeAsync(2000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
        await vi.advanceTimersByTimeAsync(300_000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('stops on HTTP failure and allows a later upload to retry', async () => {
        const { syncMedalsAfterUpload } = await import('./medalService');
        axiosGet.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: { user_id: 1, pending: false } });
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(300_000);
        expect(axiosGet).toHaveBeenCalledTimes(1);
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(1000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
    });

    it('invalidates a closed page without requesting an unused summary', async () => {
        const { fetchPlayerMedals, syncMedalsAfterUpload } = await import('./medalService');
        axiosGet.mockResolvedValueOnce({ data: summary(false, 1) });
        await fetchPlayerMedals(1);
        axiosGet.mockResolvedValueOnce({ data: { user_id: 1, pending: false } }).
            mockResolvedValueOnce({ data: summary(false, 2) });
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(1000);
        expect(axiosGet).toHaveBeenCalledTimes(2);
        expect(await fetchPlayerMedals(1)).toEqual(summary(false, 2));
    });

    it('rejects stale hover cache writes when a pre-upload request finishes late', async () => {
        const { fetchPlayerMedalState, syncMedalsAfterUpload } = await import('./medalService');
        const oldResponse = Promise.withResolvers<{ data: { user_id: number; grants: MedalStateRecord[] }[] }>();
        axiosGet.mockReturnValueOnce(oldResponse.promise).
            mockResolvedValueOnce({ data: { user_id: 1, pending: false } }).
            mockResolvedValueOnce({ data: [{ user_id: 1, grants: [] }] });
        const old = fetchPlayerMedalState(1);
        await vi.advanceTimersByTimeAsync(0);
        syncMedalsAfterUpload();
        await vi.advanceTimersByTimeAsync(1000);
        const current = fetchPlayerMedalState(1);
        oldResponse.resolve({ data: [{ user_id: 1, grants: [{ code: 'old', stage: 1, timestamp: null, scope: '', tournament: null, rank: null }] }] });
        await old;
        await vi.advanceTimersByTimeAsync(0);
        expect(await current).toEqual([]);
        expect(await fetchPlayerMedalState(1)).toEqual([]);
        expect(axiosGet).toHaveBeenCalledTimes(3);
    });
});

describe('medalCaption', () => {
    it.each(['en', 'zh-cn'])('has an explanation for every series in %s without unresolved placeholders', async (locale) => {
        const { medalCaption } = await import('./medalService');
        for (const series of Object.values(MedalSeries)) {
            const caption = medalCaption(series, 'catalog.item.e', 95000, locale);
            expect(caption.meaning).not.toBe('');
            expect(caption.meaning).not.toMatch(/\{\w+\}/);
        }
    });

    it.each(['en', 'zh-cn'])('has flavor text only for novice and shareholder medals in %s', async (locale) => {
        const { medalCaption } = await import('./medalService');
        expect(medalCaption(MedalSeries.REVIEWED, 'novice.review', 1, locale).flavor).not.toBe('');
        expect(medalCaption(MedalSeries.SHAREHOLDER, 'shareholder.origin', 1000, locale).flavor).not.toBe('');
        expect(medalCaption(MedalSeries.FLAGLESS_SPEED, 'ability.bvs.nf.b', 10000, locale).flavor).toBe('');
        for (const series of ['unknown', 'constructor', '__proto__']) {
            expect(medalCaption(series, '', null, locale)).toEqual({ title: series, meaning: '', flavor: '' });
        }
    });

    it.each([
        [MedalSeries.THREE_FLAGLESS_PRECISION, 'ability.thrp.nf.three', 'Three-Tier Flagless Precision · 0.95', 'no-flag thrp on all 3 levels reached 0.95.'],
        [MedalSeries.THREE_FLAGGED_PRECISION, 'ability.thrp.fl.three', 'Three-Tier Flagged Precision · 0.95', 'Thrp on all 3 levels reached 0.95.'],
    ])('formats three-tier series %s without adding a level', async (series, code, title, meaning) => {
        const { medalCaption } = await import('./medalService');
        expect(medalCaption(series, code, 95000, 'en')).toEqual({ title, meaning, flavor: '' });
    });

    it('names a worn ability medal from its code and stage', async () => {
        const { medalCaption } = await import('./medalService');
        expect(medalCaption(MedalSeries.BREAKTHROUGH, 'ability.time.e', 30000, 'en')).toEqual({
            title: 'Expert Breakthrough · Sub30',
            meaning: 'Expert best time reached 30s.',
            flavor: '',
        });
        expect(medalCaption(MedalSeries.SHAREHOLDER, 'shareholder.origin', 1000, 'zh-cn')).toMatchObject({
            title: '原始股东·1000',
            flavor: '老资历',
        });
    });
});
