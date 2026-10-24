import { describe, expect, it } from 'vitest';

import fixtures from '../../../../back_end/saolei/minigame/fixtures/replay-archives.json';

import { loadReplayArchiveCodec } from './archive';
import type { TrainingRecording } from './recording';

describe('7z replay storage', () => {
    it.each(['python', 'browser'] as const)('reads the %s archive using the shared format fixture', async (writer) => {
        const codec = await loadReplayArchiveCodec();
        const data = Uint8Array.from(atob(fixtures[writer]), (char) => char.charCodeAt(0));
        expect(codec.unpack(data.buffer)).toEqual(fixtures.replay);
    });

    it('round-trips UTF-8 JSON as an independent LZMA2 archive and cleans files between operations', async () => {
        const codec = await loadReplayArchiveCodec();
        const source: TrainingRecording = { version: 1, cellSize: null, initialBoard: 'AAAAAP////8', events: Array.from({ length: 1000 }, (_, index) => [index === 0 ? 0 : 10, index % 2 === 0 ? 1 : -1, 0, 0]), specialEvents: [] };
        const packed = codec.pack(source);
        expect(Array.from(new Uint8Array(packed).slice(0, 6))).toEqual([0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c]);
        expect(packed.byteLength).toBeLessThan(JSON.stringify(source).length / 2);
        expect(codec.unpack(packed)).toEqual(source);
        const empty = { ...source, events: [] };
        expect(codec.unpack(codec.pack(empty))).toEqual(empty);
        expect(codec.unpack(packed)).toEqual(source);
    });

    it('rejects corrupt data and can perform the next operation', async () => {
        const codec = await loadReplayArchiveCodec();
        expect(() => codec.unpack(new Uint8Array([1, 2, 3]).buffer)).toThrow();
        const replay: TrainingRecording = { version: 1, cellSize: 32, initialBoard: 'AAAAAAAAAAA', events: [], specialEvents: [] };
        expect(codec.unpack(codec.pack(replay))).toEqual(replay);
    });
});
