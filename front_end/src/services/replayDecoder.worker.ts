import type initializeDecoder from '@putianyi888/msrc/web';
import type { decompress } from '@putianyi888/msrc/web';
import localWasmUrl from '@putianyi888/msrc/web/msrc_bg.wasm?url';
import localModuleUrl from '@putianyi888/msrc/web?url';

interface Decoder { default: typeof initializeDecoder; decompress: typeof decompress }
const cdnBase = 'https://cdn.jsdelivr.net/npm/@putianyi888/msrc@0.2.0/web/';
let initialization: Promise<Decoder> | undefined;

async function withTimeout<T>(request: Promise<T>): Promise<T> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
        return await Promise.race([request, new Promise<never>((_resolve, reject) => {
            timer = setTimeout(() => {
                reject(new Error('CDN decoder loading timed out'));
            }, 4000);
        })]);
    } finally {
        clearTimeout(timer);
    }
}

async function loadDecoder(): Promise<Decoder> {
    try {
        const module = await withTimeout(import(/* @vite-ignore */ `${cdnBase}msrc.js`)) as Decoder;
        await withTimeout(module.default({ module_or_path: `${cdnBase}msrc_bg.wasm` }));
        return module;
    } catch {
        const module = await import(/* @vite-ignore */ localModuleUrl) as Decoder;
        await module.default({ module_or_path: localWasmUrl });
        return module;
    }
}

function decoder(): Promise<Decoder> {
    initialization ??= loadDecoder().catch((error: unknown) => {
        initialization = undefined;
        throw error;
    });
    return initialization;
}

let queue = Promise.resolve();
self.onmessage = (event: MessageEvent<{ id: number; data: ArrayBuffer }>) => {
    const { id, data } = event.data;
    queue = queue.then(async () => {
        try {
            const module = await decoder();
            const decoded = module.decompress(new Uint8Array(data), 64 * 1024 * 1024, 64 * 1024);
            const buffer = decoded.buffer as ArrayBuffer;
            self.postMessage({ id, data: buffer }, { transfer: [buffer] });
        } catch (error) {
            self.postMessage({ id, error: error instanceof Error ? error.message : String(error) });
        }
    });
};
