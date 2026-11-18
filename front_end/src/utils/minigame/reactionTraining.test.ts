import { describe, expect, it, vi } from 'vitest';

import { reactionLevels, ReactionTraining } from './reactionTraining';

describe('reaction training', () => {
    it.each(reactionLevels)('completes fixed level $key across multiple lines', ({ length, target }) => {
        const game = new ReactionTraining(length, 0.25, target, () => 0.99);
        let column = 0;
        for (let input = 0; input < target * 2 && game.phase !== 'won'; input++) {
            const { line } = game;
            game.trigger(0, column, input * 100);
            column = line === game.line ? column + 1 : 0;
        }
        expect(game.phase).toBe('won');
        expect(game.reactions).toBe(target);
        expect(game.line).toBeGreaterThan(1);
        expect(game.board[0].at(-1)).toBe(10);
    });
    it('starts with no random mines, hides generated mines and shows the correct clues', () => {
        const random = vi.fn(() => 0);
        const game = new ReactionTraining(5, 0.25, 10, random);
        expect(random).not.toHaveBeenCalled();
        expect(game.board).toEqual([Array(5).fill(10), Array(5).fill(11)]);
        game.trigger(0, 0, 100);
        expect(game.reactions).toBe(0);
        expect(game.board[0]).toEqual([3, 10, 10, 10, 10]);
        game.trigger(0, 2, 200);
        expect(game.board[0]).toEqual([3, 10, 5, 10, 10]);
        game.trigger(0, 4, 300);
        expect(game.line).toBe(2);
        expect(game.reactions).toBe(2);
        expect(random).toHaveBeenCalledTimes(2);
    });

    it.each([0.25, 0.5])('samples using the configured probability %s', (probability) => {
        for (const [sample, next] of [[probability - 0.01, 2], [probability, 1]]) {
            const game = new ReactionTraining(5, probability, 10, () => sample);
            game.trigger(0, 0, 0);
            game.trigger(0, next, 100);
            expect(game.phase).toBe('playing');
            expect(game.reactions).toBe(1);
        }
    });

    it.each([0, 4])('ignores repeated opened cells without drawing again or stopping the clock (start %s)', (start) => {
        const random = vi.fn(() => 0);
        const game = new ReactionTraining(5, 0.25, 10, random);
        const next = 2;
        game.trigger(0, start, 100);
        game.trigger(0, next, 200);
        const { board } = game;
        game.trigger(0, start, 300);
        game.trigger(0, next, 400);
        expect(game.phase).toBe('playing');
        expect(game.board).toEqual(board);
        expect(game.reactions).toBe(1);
        expect(game.line).toBe(1);
        expect(random).toHaveBeenCalledTimes(2);
        expect(game.elapsedMs(600)).toBe(500);
        game.trigger(0, start === 0 ? 1 : 3, 700);
        expect(game.phase).toBe('lost');
        expect(game.reactions).toBe(1);
    });

    it('forces the final mine after a safe penultimate cell and keeps timing across lines', () => {
        const random = vi.fn(() => 0.99);
        const game = new ReactionTraining(5, 0.5, 10, random);
        for (let column = 0; column < 4; column++) game.trigger(0, column, 100 + column * 100);
        expect(game.line).toBe(2);
        expect(game.reactions).toBe(3);
        expect(random).toHaveBeenCalledTimes(3);
        expect(game.elapsedMs(2100)).toBe(2000);
        game.trigger(0, 4, 2200);
        expect(game.reactions).toBe(3);
        game.trigger(0, 3, 2300);
        expect(game.reactions).toBe(4);
        expect(game.elapsedMs(2300)).toBe(2200);
    });

    it('rejects a premature click and stops a failed game', () => {
        const game = new ReactionTraining(5, 0.25, 10, () => 0.99);
        game.trigger(0, 0, 100);
        game.trigger(0, 2, 200);
        expect(game.phase).toBe('lost');
        game.trigger(0, 1, 300);
        expect(game.reactions).toBe(0);
        expect(game.elapsedMs(400)).toBe(100);
    });

    it.each([0, 4])('permits either starting side and rejects hitting a known mine (start %s)', (start) => {
        const game = new ReactionTraining(5, 0.5, 10, () => 0);
        game.trigger(0, start, 100);
        game.trigger(0, start === 0 ? 1 : 3, 200);
        expect(game.phase).toBe('lost');
    });

    it('ignores the flag row before and during the game without drawing random results', () => {
        const random = vi.fn(() => 0.99);
        const game = new ReactionTraining(5, 0.25, 10, random);
        game.trigger(1, 0, 100);
        expect(game.phase).toBe('ready');
        expect(game.elapsedMs(500)).toBe(0);
        expect(random).not.toHaveBeenCalled();
        game.trigger(0, 0, 1000);
        const { board } = game;
        for (let column = 0; column < 5; column++) game.trigger(1, column, 1100 + column);
        expect(game.phase).toBe('playing');
        expect(game.reactions).toBe(0);
        expect(game.board).toEqual(board);
        expect(game.elapsedMs(1500)).toBe(500);
        expect(random).toHaveBeenCalledTimes(1);
        game.trigger(0, 1, 1600);
        expect(game.reactions).toBe(1);
    });
});
