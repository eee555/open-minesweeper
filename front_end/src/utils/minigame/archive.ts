import SevenZip from '7z-wasm';
import type { SevenZipModule } from '7z-wasm';
import wasmUrl from '7z-wasm/7zz.wasm?url&inline';

import { replayObject, requireReplay } from './boardEncoding';

const filename = 'replay.json';
let codec: Promise<ReplayArchiveCodec> | undefined;

export interface ReplayArchiveCodec {
    pack: (replay: unknown) => ArrayBuffer;
    unpack: (archive: ArrayBuffer) => unknown;
}

/** Initialize before opening an IndexedDB upgrade transaction; codec operations are synchronous. */
export function loadReplayArchiveCodec(): Promise<ReplayArchiveCodec> {
    codec ??= (async () => {
        const binary = Uint8Array.from(atob(wasmUrl.slice(wasmUrl.indexOf(',') + 1)), (char) => char.charCodeAt(0));
        const zip = await SevenZip({ wasmBinary: binary.buffer, print: () => undefined, printErr: () => undefined });
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
