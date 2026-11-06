import type { SevenZipModule } from '7z-wasm';
import wasmUrl from '7z-wasm/7zz.wasm?url';
import sevenZipPackage from '7z-wasm/package.json';

import { replayObject, requireReplay } from './boardEncoding';

const filename = 'replay.json';
const cdnWasmUrl = `https://cdn.jsdelivr.net/npm/7z-wasm@${sevenZipPackage.version}/7zz.wasm`;
let codec: Promise<ReplayArchiveCodec> | undefined;

export interface ReplayArchiveCodec {
    pack: (replay: unknown) => ArrayBuffer;
    unpack: (archive: ArrayBuffer) => unknown;
}

async function fetchWasm(url: string, timeout?: number): Promise<ArrayBuffer> {
    const controller = new AbortController();
    const timer = timeout === undefined
        ? undefined
        : setTimeout(() => {
            controller.abort();
        }, timeout);
    try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error(`Failed to load 7z WASM: HTTP ${response.status}`);
        return await response.arrayBuffer();
    } finally {
        clearTimeout(timer);
    }
}

async function initializeSevenZip(): Promise<SevenZipModule> {
    const { default: SevenZip } = await import('7z-wasm');
    const options = { print: () => undefined, printErr: () => undefined };
    // The offline build's unlimited assetsInlineLimit keeps this URL as data:.
    if (wasmUrl.startsWith('data:')) {
        const binary = Uint8Array.from(atob(wasmUrl.slice(wasmUrl.indexOf(',') + 1)), (char) => char.charCodeAt(0));
        return SevenZip({ ...options, wasmBinary: binary.buffer });
    }
    if (import.meta.env.PROD) {
        try {
            return await SevenZip({ ...options, wasmBinary: await fetchWasm(cdnWasmUrl, 4000) });
        } catch {
            // Use the same-version local binary if fetching or initialization fails.
        }
    }
    return SevenZip({ ...options, wasmBinary: await fetchWasm(wasmUrl) });
}

/** Initialize before opening an IndexedDB upgrade transaction; codec operations are synchronous. */
export function loadReplayArchiveCodec(): Promise<ReplayArchiveCodec> {
    codec ??= (async () => {
        const zip = await initializeSevenZip();
        return {
            pack(replay: unknown): ArrayBuffer {
                return withArchiveFiles(zip, () => {
                    zip.FS.writeFile(filename, new TextEncoder().encode(JSON.stringify(replay)));
                    run(zip, ['a', '-t7z', '-m0=LZMA2', '-mx=1', '-md=1m', '-mmt=off', 'replay.7z', filename]);
                    return Uint8Array.from(zip.FS.readFile('replay.7z')).buffer;
                });
            },
            unpack(archive: ArrayBuffer): unknown {
                return withArchiveFiles(zip, () => {
                    zip.FS.writeFile('replay.7z', new Uint8Array(archive));
                    run(zip, ['e', '-y', 'replay.7z', filename]);
                    const replay: unknown = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(zip.FS.readFile(filename)));
                    replayObject(replay);
                    return replay;
                });
            },
        };
    })().catch((error: unknown) => {
        codec = undefined;
        throw error;
    });
    return codec;
}

function run(zip: SevenZipModule, args: string[]): void {
    // Upstream's declaration says void, but callMain returns the CLI exit status.
    const status = (zip.callMain as (args: string[]) => number)(args);
    requireReplay(status === 0, '7z replay operation failed');
}

function withArchiveFiles<T>(zip: SevenZipModule, operation: () => T): T {
    try {
        return operation();
    } finally {
        for (const path of [filename, 'replay.7z']) {
            if (zip.FS.readdir('.').includes(path)) zip.FS.unlink(path);
        }
    }
}

export async function unpackReplayArchive(archive: ArrayBuffer): Promise<unknown> {
    return (await loadReplayArchiveCodec()).unpack(archive);
}
