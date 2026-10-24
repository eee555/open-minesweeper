import type { useRafFn } from '@vueuse/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { effectScope } from 'vue';
import type { EffectScope } from 'vue';

import { leftClickModes } from './leftClickTraining';
import { useTrainingReplay } from './useTrainingReplay';

// Same Node frame source as the existing playback clock tests; run the real scheduler.
vi.mock('@vueuse/core', async (importOriginal) => {
    const original = await importOriginal<{ useRafFn: typeof useRafFn }>();
    return { ...original,
        useRafFn: (callback: Parameters<typeof original.useRafFn>[0], options?: Parameters<typeof original.useRafFn>[1]) => original.useRafFn(callback, {
            ...options, window: { requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame } as Window,
        }) };
});

describe('shared minigame playback and chart previews', () => {
    let now = 0;
    let nextFrameId = 0;
    let scope: EffectScope;
    const frames = new Map<number, FrameRequestCallback>();
    function advance(ms: number) {
        now += ms;
        const callbacks = [...frames.values()];
        frames.clear();
        for (const callback of callbacks) callback(now);
    }
    beforeEach(() => {
        now = 0;
        nextFrameId = 0;
        scope = effectScope();
        frames.clear();
        vi.spyOn(performance, 'now').mockImplementation(() => now);
        vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
            const id = ++nextFrameId;
            frames.set(id, callback);
            return id;
        });
        vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
    });
    afterEach(() => {
        scope.stop();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it('locks chart previews while preserving time and play state, and cleans up on a new game', () => {
        const replay = scope.run(() => useTrainingReplay());
        if (replay === undefined) throw new Error('Missing replay controller');
        replay.finish({ game: 'left-click', mode: leftClickModes[0], durationMs: 1000, initialBoard: [[0]], recording: { version: 1, cellSize: 32, initialBoard: 'AAAAAAAAAAA', events: [], specialEvents: [] }, events: [], snapshots: [{ eventIndex: -1, board: [[0]], remaining: 0 }], chords: [] });
        expect(replay.frame.value?.timeMs).toBe(1000);
        expect(replay.playback.isPlaying.value).toBe(false);
        replay.playback.seek(100);
        replay.hover({ timeMs: 400 });
        advance(100);
        expect(replay.frame.value?.timeMs).toBe(400);
        replay.hover(null);
        expect(replay.frame.value?.timeMs).toBe(100);
        expect(replay.playback.isPlaying.value).toBe(false);

        replay.playback.play();
        advance(100);
        replay.hover({ timeMs: 400 });
        advance(300);
        replay.hover({ timeMs: 700 });
        advance(100);
        expect(replay.frame.value?.timeMs).toBe(700);
        expect(replay.playback.currentMs.value).toBe(200);
        replay.hover(null);
        advance(100);
        expect(replay.frame.value?.timeMs).toBe(300);
        expect(replay.playback.isPlaying.value).toBe(true);
        replay.reset();
        expect(replay.data.value).toBeNull();
        expect(replay.frame.value).toBeNull();
        expect(replay.playback.isPlaying.value).toBe(false);
        expect(frames.size).toBe(0);
    });
});
