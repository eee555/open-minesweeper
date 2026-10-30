import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ReplayFileService from './replayFileService';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/http', () => ({ default: { get } }));
const native = createRequire(import.meta.url)('@putianyi888/msrc') as { decompress: (data: Uint8Array) => Uint8Array };
const raw = Uint8Array.from(readFileSync(new URL('../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
const archive = Uint8Array.from(readFileSync(new URL('../../cypress/fixtures/52200.evf.msrc', import.meta.url))).buffer;
let service: typeof ReplayFileService;
let createdWorkers = 0;

class DecoderWorker {
    public onmessage?: (event: { data: { id: number; data?: ArrayBuffer; error?: string } }) => void;
    public onerror?: () => void;
    public constructor() {
        createdWorkers += 1;
    }

    public terminate = vi.fn();

    public postMessage(request: { id: number; data: ArrayBuffer }) {
        queueMicrotask(() => {
            try {
                const data = native.decompress(new Uint8Array(request.data)).buffer as ArrayBuffer;
                this.onmessage?.({ data: { id: request.id, data } });
            } catch (error) {
                this.onmessage?.({ data: { id: request.id, error: String(error) } });
            }
        });
    }
}

beforeEach(async () => {
    vi.resetModules();
    get.mockReset();
    createdWorkers = 0;
    vi.stubGlobal('Worker', DecoderWorker);
    service = await import('./replayFileService');
});
afterEach(() => vi.unstubAllGlobals());

describe('site replay file protocol', () => {
    it('returns raw bytes without constructing a decoder', async () => {
        get.mockResolvedValue({ data: raw, headers: { 'x-replay-container-version': '0', 'content-disposition': 'attachment; filename="original%20replay.evf"' } });
        const replay = await service.fetchReplayFile('/api/video/preview');
        expect(replay).toEqual({ data: raw, filename: 'original replay.evf' });
        expect(createdWorkers).toBe(0);
    });

    it('restores Python-generated containers with the actual npm decoder and reuses its worker', async () => {
        get.mockImplementation(() => Promise.resolve({ data: archive.slice(0), headers: { 'x-replay-container-version': '1', 'content-disposition': 'attachment; filename="52200.evf.msrc"' } }));
        for (let i = 0; i < 2; i++) {
            const replay = await service.fetchReplayFile('/api/video/preview');
            expect(replay.filename).toBe('52200.evf');
            expect(new Uint8Array(replay.data)).toEqual(new Uint8Array(raw));
        }
        expect(createdWorkers).toBe(1);
    });

    it('rejects missing protocol headers before trying to decode', async () => {
        get.mockResolvedValue({ data: raw, headers: {} });
        await expect(service.fetchReplayFile('/api/video/preview')).rejects.toThrow('container version');
        expect(createdWorkers).toBe(0);
    });

    it('reports damaged containers', async () => {
        get.mockResolvedValue({ data: new ArrayBuffer(10), headers: { 'x-replay-container-version': '1', 'content-disposition': 'attachment; filename="bad.evf.msrc"' } });
        await expect(service.fetchReplayFile('/api/video/preview')).rejects.toThrow();
    });
});
