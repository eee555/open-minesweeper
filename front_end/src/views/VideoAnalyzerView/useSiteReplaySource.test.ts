import { readFileSync } from 'node:fs';

import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';
import { EvfVideo } from 'ms-toollib';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { computed, effectScope, nextTick, ref } from 'vue';
import type { EffectScope } from 'vue';

import { useSiteReplaySource } from './useSiteReplaySource';

import { useReplaySource } from '@/components/VideoAnalyzer/useReplaySource';

const { get, fetchVideoInfo } = vi.hoisted(() => ({
    get: vi.fn<AxiosInstance['get']>(),
    fetchVideoInfo: vi.fn<(id: number) => Promise<{ software: 'e' }>>(),
}));
vi.mock('@/http', () => ({ default: { get } }));
vi.mock('@/services/videoInfoService', () => ({ fetchVideoInfo }));

const scopes: EffectScope[] = [];

function fixture() {
    return Uint8Array.from(readFileSync(new URL('../../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
}

function response<T>(data: T): AxiosResponse<T> {
    return { data, status: 200, statusText: 'OK', headers: { 'x-replay-container-version': '0' }, config: { headers: new AxiosHeaders() } };
}

function setup() {
    const id = ref('52200');
    const scope = effectScope();
    scopes.push(scope);
    const replay = scope.run(() => {
        const site = useSiteReplaySource(id);
        const parsed = useReplaySource(site.source);
        return { ...parsed, loading: site.loading, errorMessage: computed(() => site.errorMessage.value || parsed.errorMessage.value) };
    });
    if (replay === undefined) throw new Error('Replay scope did not start');
    return { id, scope, ...replay };
}

function mockRequests() {
    fetchVideoInfo.mockResolvedValueOnce({ software: 'e' });
    get.mockResolvedValueOnce(response(fixture()));
}

afterEach(() => {
    for (const scope of scopes.splice(0)) scope.stop();
    vi.restoreAllMocks();
    get.mockReset();
    fetchVideoInfo.mockReset();
});

describe('analyzer replay loading', () => {
    it('creates an independent export parser from loaded bytes without new requests or page seeks', async () => {
        mockRequests();
        const replay = setup();
        expect(() => replay.createExportVideo()).toThrow('Replay is not loaded');
        await vi.waitFor(() => {
            expect(replay.video.value).not.toBeNull();
        });
        const visible = replay.video.value;
        if (visible === null) throw new Error('Expected a loaded replay');
        visible.current_time = 5;
        const originalBoard = visible.game_board;
        const originalIndex = visible.current_event_id;
        const exported = replay.createExportVideo();
        try {
            expect(exported).not.toBe(visible);
            exported.current_time = Infinity;
            expect(exported.bbbv_solved).toBe(52);
            expect(visible.game_board).toEqual(originalBoard);
            expect(visible.current_event_id).toBe(originalIndex);
            expect(get).toHaveBeenCalledOnce();
        } finally {
            exported.free();
        }
        replay.scope.stop();
        expect(() => replay.createExportVideo()).toThrow('Replay is not loaded');
    });

    it('requests the format and original bytes and exposes the real duration', async () => {
        mockRequests();
        const replay = setup();
        expect(replay.loading.value).toBe(true);
        expect(replay.durationMs.value).toBe(0);
        expect(replay.globalBoard.value).toBeNull();
        await vi.waitFor(() => {
            expect(replay.video.value).not.toBeNull();
        });
        expect(replay.durationMs.value).toBe(10732);
        expect(replay.globalBoard.value).toEqual(replay.video.value?.board);
        const globalBoard = replay.globalBoard.value;
        const video = replay.video.value;
        if (video === null) throw new Error('Expected a loaded replay');
        video.current_time = Infinity;
        expect(replay.globalBoard.value).toBe(globalBoard);
        expect(replay.loading.value).toBe(false);
        expect(replay.errorMessage.value).toBe('');
        const signal = get.mock.calls[0][1]?.signal;
        expect(fetchVideoInfo).toHaveBeenCalledWith(52200);
        expect(get).toHaveBeenCalledWith('/api/video/preview', {
            params: { id: '52200.evf' }, responseType: 'arraybuffer', signal,
        });
    });

    it('reports HTTP errors and does not request bytes if the format request fails', async () => {
        const denied = response('Forbidden');
        denied.status = 403;
        denied.statusText = 'Forbidden';
        fetchVideoInfo.mockRejectedValueOnce(new AxiosError('Request failed', undefined, undefined, undefined, denied));
        const replay = setup();
        await vi.waitFor(() => {
            expect(replay.loading.value).toBe(false);
        });
        expect(replay.errorMessage.value).toBe('403 Forbidden');
        expect(replay.durationMs.value).toBe(0);
        expect(replay.globalBoard.value).toBeNull();
        expect(get).not.toHaveBeenCalled();
    });

    it('reports parse errors without publishing or leaking the video', async () => {
        mockRequests();
        const free = vi.spyOn(EvfVideo.prototype, 'free');
        vi.spyOn(EvfVideo.prototype, 'parse').mockImplementation(() => {
            throw new Error('Invalid replay');
        });
        const replay = setup();
        await vi.waitFor(() => {
            expect(replay.loading.value).toBe(false);
        });
        expect(replay.video.value).toBeNull();
        expect(replay.errorMessage.value).toBe('Invalid replay');
        expect(free).toHaveBeenCalledOnce();
    });

    it('frees the previous video on URL changes and frees the new video on disposal', async () => {
        mockRequests();
        const replay = setup();
        await vi.waitFor(() => {
            expect(replay.video.value).not.toBeNull();
        });
        const oldVideo = replay.video.value;
        const oldBoard = replay.globalBoard.value;
        if (oldVideo === null) throw new Error('Expected the old replay');
        const freeOld = vi.spyOn(oldVideo, 'free');
        const oldSignal = get.mock.calls[0][1]?.signal;
        mockRequests();
        replay.id.value = '123';
        await nextTick();
        expect(freeOld).toHaveBeenCalledOnce();
        expect(oldSignal?.aborted).toBe(true);
        await vi.waitFor(() => {
            expect(replay.video.value).not.toBeNull();
        });
        expect(replay.video.value).not.toBe(oldVideo);
        expect(replay.globalBoard.value).not.toBe(oldBoard);
        expect(replay.globalBoard.value).toEqual(oldBoard);
        const newVideo = replay.video.value;
        if (newVideo === null) throw new Error('Expected the new replay');
        const freeNew = vi.spyOn(newVideo, 'free');
        replay.scope.stop();
        expect(freeNew).toHaveBeenCalledOnce();
        expect(replay.globalBoard.value).toBeNull();
        expect(oldBoard?.flat().filter((cell) => cell === -1)).toHaveLength(40);
    });

    it('ignores a late binary response after the URL changes', async () => {
        const oldRequest = Promise.withResolvers<AxiosResponse<ArrayBuffer>>();
        fetchVideoInfo.mockResolvedValueOnce({ software: 'e' });
        get.mockReturnValueOnce(oldRequest.promise);
        const replay = setup();
        await vi.waitFor(() => {
            expect(get).toHaveBeenCalledOnce();
        });
        const oldSignal = get.mock.calls[0][1]?.signal;
        fetchVideoInfo.mockResolvedValueOnce({ software: 'e' });
        const newRequest = Promise.withResolvers<AxiosResponse<ArrayBuffer>>();
        get.mockReturnValueOnce(newRequest.promise);
        replay.id.value = '123';
        await vi.waitFor(() => {
            expect(get).toHaveBeenCalledTimes(2);
        });
        expect(oldSignal?.aborted).toBe(true);
        oldRequest.resolve(response(fixture()));
        await nextTick();
        expect(replay.video.value).toBeNull();
        expect(replay.globalBoard.value).toBeNull();
        expect(replay.loading.value).toBe(true);
        newRequest.resolve(response(fixture()));
        await vi.waitFor(() => {
            expect(replay.video.value).not.toBeNull();
        });
        expect(replay.loading.value).toBe(false);
        expect(replay.errorMessage.value).toBe('');
    });
});
