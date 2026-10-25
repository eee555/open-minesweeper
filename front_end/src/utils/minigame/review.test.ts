import { describe, expect, it } from 'vitest';

import { leftClickModes, multiTouchModes } from './leftClickTraining';
import { replayFrame } from './replay';
import { rebuildMinigameReplay } from './review';

const mouse = { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [[0, 16, 16, 2], [10, 32, 0, 1], [10, 0, 0, 2]], specialEvents: [] };

describe('opening minigame ranking replays', () => {
    it('resolves the selected ranking and rebuilds mouse and touch states with the saved score', () => {
        const left = rebuildMinigameReplay('left-click', leftClickModes[0].rankingKey, mouse, 30);
        if (left.game !== 'left-click') throw new Error('Expected a mouse replay');
        expect(left.durationMs).toBe(30);
        expect(replayFrame(left, { timeMs: 0 }).remaining).toBe(31);
        expect(replayFrame(left, { timeMs: 15 }).pressed).toEqual({ row: 0, column: 1, chord: false });
        expect(replayFrame(left, { timeMs: 30 }).remaining).toBe(30);
        const touch = rebuildMinigameReplay('multi-touch', multiTouchModes[0].rankingKey, { version: 1, cellSize: 32, initialBoard: mouse.initialBoard, events: [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]] }, 10);
        if (touch.game !== 'multi-touch') throw new Error('Expected a touch replay');
        expect(replayFrame(touch, { timeMs: 10 })).toMatchObject({ remaining: 30, contacts: [{ id: 0 }, { id: 1 }] });
        expect(touch.mode).toEqual(multiTouchModes[0]);
    });

    it('rebuilds flag-and-chord boards and every missing-cell round', () => {
        const flag = rebuildMinigameReplay('flag-chord', 'flag-chord-b-v1', { ...mouse, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], events: [] }, 1000);
        if (flag.game !== 'flag-chord') throw new Error('Expected a flag-and-chord replay');
        expect(flag.snapshots[0].remaining).toBe(4);
        expect(flag.initialBoard[1][1]).toBe(1);
        const missing = rebuildMinigameReplay('missing-cell', 'missing-cell-b-v1', { version: 1, rounds: Array.from({ length: 10 }, (_, index) => ({ board: 'gAAAAAAAAAA', target: [7, 7], timeMs: index + 100 })) }, 1045);
        if (missing.game !== 'missing-cell') throw new Error('Expected a missing-cell replay');
        expect(missing.durationMs).toBe(1045);
        expect(missing.rounds.map((round) => round.timeMs)).toEqual(Array.from({ length: 10 }, (_, index) => index + 100));
        expect(missing.rounds[0].board[7][7]).toBe(10);
        expect(missing.rounds[0].board[0][0]).toBe(16);
    });

    it('rejects mismatched rankings and damaged recordings instead of creating a new game', () => {
        expect(() => rebuildMinigameReplay('left-click', 'multi-touch-b-50-v1', mouse, 1000)).toThrow('Unknown minigame replay ranking');
        expect(() => rebuildMinigameReplay('flag-chord', 'flag-chord-e-v1', mouse, 1000)).toThrow('Unknown minigame replay ranking');
        expect(() => rebuildMinigameReplay('left-click', leftClickModes[0].rankingKey, { ...mouse, initialBoard: 'bad' }, 1000)).toThrow();
    });
});
