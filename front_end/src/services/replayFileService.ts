import { CanceledError } from 'axios';

import $axios from '@/http';

export interface ReplayFile {
    data: ArrayBuffer;
    filename: string;
}

let worker: Worker | undefined;
let sequence = 0;
const pending = new Map<number, { resolve: (data: ArrayBuffer) => void; reject: (error: Error) => void }>();

function decoderWorker(): Worker {
    if (worker !== undefined) return worker;
    worker = new Worker(new URL('./replayDecoder.worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = (event: MessageEvent<{ id: number; data?: ArrayBuffer; error?: string }>) => {
        const result = event.data;
        const request = pending.get(result.id);
        if (request === undefined) return;
        pending.delete(result.id);
        if (result.data !== undefined) request.resolve(result.data);
        else request.reject(new Error(result.error ?? 'Replay decompression failed'));
    };
    worker.onerror = () => {
        worker?.terminate();
        worker = undefined;
        for (const request of pending.values()) request.reject(new Error('Replay decoder failed'));
        pending.clear();
    };
    return worker;
}

function decompress(data: ArrayBuffer, signal?: AbortSignal): Promise<ArrayBuffer> {
    signal?.throwIfAborted();
    return new Promise((resolve, reject) => {
        const id = ++sequence;
        const abort = () => {
            pending.delete(id);
            reject(new CanceledError());
        };
        signal?.addEventListener('abort', abort, { once: true });
        const cleanup = () => signal?.removeEventListener('abort', abort);
        pending.set(id, {
            resolve: (result) => {
                cleanup(); resolve(result);
            },
            reject: (error) => {
                cleanup(); reject(error);
            },
        });
        try {
            decoderWorker().postMessage({ id, data }, [data]);
        } catch (error) {
            pending.delete(id);
            cleanup();
            reject(error instanceof Error ? error : new Error(String(error)));
        }
    });
}

export function replayResponseFilename(header: unknown, fallback: string): string {
    if (typeof header !== 'string') return fallback;
    const encoded = (/filename\*=UTF-8''([^;]+)/i).exec(header)?.[1];
    const value = encoded ?? (/filename="([^"]+)"/i).exec(header)?.[1];
    if (value === undefined) return fallback;
    try {
        return decodeURIComponent(value);
    } catch {
        return value;
    }
}

export async function fetchReplayFile(url: string, options: { signal?: AbortSignal; params?: Record<string, string>; filename?: string } = {}): Promise<ReplayFile> {
    const response = await $axios.get<ArrayBuffer>(url, { responseType: 'arraybuffer', signal: options.signal, ...options.params ? { params: options.params } : {} });
    options.signal?.throwIfAborted();
    const version = String(response.headers['x-replay-container-version'] ?? '');
    if (!(/^\d+$/).test(version)) throw new Error('Missing or invalid replay container version');
    let filename = replayResponseFilename(response.headers['content-disposition'], options.filename ?? 'replay');
    if (Number(version) === 0) return { data: response.data, filename };
    if (!filename.endsWith('.msrc')) throw new Error('Invalid compressed replay filename');
    filename = filename.slice(0, -5);
    const data = await decompress(response.data, options.signal);
    return { data, filename };
}
