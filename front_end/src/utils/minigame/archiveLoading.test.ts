import type { SevenZipModuleOptions } from '7z-wasm';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const cdnUrl = 'https://cdn.jsdelivr.net/npm/7z-wasm@1.2.0/7zz.wasm';
const localUrl = '/assets/7zz-local.wasm';
const binary = new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]);
const fetchMock = vi.fn<typeof fetch>();
const initialize = vi.fn<(options: Partial<SevenZipModuleOptions>) => Promise<object>>();

beforeEach(() => {
    vi.resetModules();
    vi.stubEnv('PROD', true);
    initialize.mockReset().mockResolvedValue({});
    fetchMock.mockReset().mockImplementation(() => Promise.resolve(new Response(binary)));
    vi.doMock('7z-wasm', () => ({ default: initialize }));
    vi.doMock('7z-wasm/7zz.wasm?url', () => ({ default: localUrl }));
    vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.doUnmock('7z-wasm');
    vi.doUnmock('7z-wasm/7zz.wasm?url');
});

describe('7z CDN loading', () => {
    it('waits until the codec is needed and shares initialization between concurrent callers', async () => {
        const { loadReplayArchiveCodec } = await import('./archive');
        expect(fetchMock).not.toHaveBeenCalled();
        expect(initialize).not.toHaveBeenCalled();
        const first = loadReplayArchiveCodec();
        expect(loadReplayArchiveCodec()).toBe(first);
        const codec = await first;
        expect(await loadReplayArchiveCodec()).toBe(codec);
        expect(fetchMock).toHaveBeenCalledExactlyOnceWith(cdnUrl, expect.objectContaining({ signal: expect.any(AbortSignal) }));
        expect(initialize).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ wasmBinary: binary.buffer }));
    });

    it('loads the local binary when the CDN request fails', async () => {
        fetchMock.mockRejectedValueOnce(new TypeError('CDN unavailable'));
        const { loadReplayArchiveCodec } = await import('./archive');
        await loadReplayArchiveCodec();
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([cdnUrl, localUrl]);
        expect(initialize).toHaveBeenCalledTimes(1);
    });

    it('loads the local binary when the CDN responds with an HTTP error', async () => {
        fetchMock.mockResolvedValueOnce(new Response(null, { status: 503 }));
        const { loadReplayArchiveCodec } = await import('./archive');
        await loadReplayArchiveCodec();
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([cdnUrl, localUrl]);
    });

    it('aborts a hanging CDN request after four seconds and falls back locally', async () => {
        vi.useFakeTimers();
        const requested = Promise.withResolvers<undefined>();
        fetchMock.mockImplementationOnce((_url, options) => new Promise<Response>((_resolve, reject) => {
            options?.signal?.addEventListener('abort', () => {
                reject(new DOMException('Aborted', 'AbortError'));
            });
            requested.resolve(undefined);
        }));
        const { loadReplayArchiveCodec } = await import('./archive');
        const ready = loadReplayArchiveCodec();
        await requested.promise;
        await vi.advanceTimersByTimeAsync(3999);
        expect(fetchMock).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(1);
        await ready;
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([cdnUrl, localUrl]);
        expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
    });

    it('also falls back if the downloaded CDN binary cannot initialize', async () => {
        initialize.mockRejectedValueOnce(new Error('Invalid WASM'));
        const { loadReplayArchiveCodec } = await import('./archive');
        await loadReplayArchiveCodec();
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([cdnUrl, localUrl]);
        expect(initialize).toHaveBeenCalledTimes(2);
    });

    it('allows retrying after both sources fail', async () => {
        fetchMock.mockRejectedValueOnce(new Error('CDN unavailable')).mockRejectedValueOnce(new Error('Local unavailable'));
        const { loadReplayArchiveCodec } = await import('./archive');
        await expect(loadReplayArchiveCodec()).rejects.toThrow('Local unavailable');
        await loadReplayArchiveCodec();
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([cdnUrl, localUrl, cdnUrl]);
        expect(initialize).toHaveBeenCalledTimes(1);
    });

    it('uses the offline build inline binary without any network request', async () => {
        vi.doMock('7z-wasm/7zz.wasm?url', () => ({ default: 'data:application/wasm;base64,AGFzbQEAAAA=' }));
        const { loadReplayArchiveCodec } = await import('./archive');
        await loadReplayArchiveCodec();
        expect(fetchMock).not.toHaveBeenCalled();
        expect(initialize).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ wasmBinary: binary.buffer }));
    });

    it('uses local WASM in development and component tests', async () => {
        vi.stubEnv('PROD', false);
        const { loadReplayArchiveCodec } = await import('./archive');
        await loadReplayArchiveCodec();
        expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([localUrl]);
    });
});
