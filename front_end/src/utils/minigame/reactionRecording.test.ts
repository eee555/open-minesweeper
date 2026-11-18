import { describe, expect, it, vi } from 'vitest';

import { reactionFrame, ReactionRecorder, rebuildReactionReplay } from './reactionRecording';
import { reactionModes } from './reactionTraining';

function complete() {
    let draw = 0;
    const recorder = new ReactionRecorder(reactionModes[0], () => (++draw % 2 === 0 ? 0 : 0.99));
    const expected: { ms: number; board: number[][]; remaining: number }[] = [];
    let now = 100.3;
    for (let index = 0; index < 30 && recorder.game.phase !== 'won'; index++) {
        const column = recorder.game.nextColumn ?? (recorder.game.line % 2 === 1 ? 0 : recorder.game.length - 1);
        recorder.capture({ action: 'lc', now });
        expect(recorder.trigger(0, column, now + 20.6)).toBe(true);
        expected.push({ ms: recorder.game.elapsedMs(now + 20.6), board: recorder.game.board, remaining: recorder.game.target - recorder.game.reactions });
        now += 120.4;
    }
    return { recorder, expected, scoreMs: recorder.game.elapsedMs(now) };
}

describe('reaction recordings', () => {
    it('rebuilds every advancing click and press from time pairs and actual draws without using randomness', () => {
        const { recorder, expected, scoreMs } = complete();
        const recording = recorder.finish();
        const random = vi.spyOn(Math, 'random').mockImplementation(() => {
            throw new Error('Unexpected replay randomness');
        });
        try {
            const replay = rebuildReactionReplay(reactionModes[0], recording, scoreMs);
            expect(Object.keys(recording).sort()).toEqual(['clicks', 'draws', 'sides', 'version']);
            expect(replay.samples).toHaveLength(10);
            expect(replay.samples.some((sample) => sample.jump)).toBe(true);
            expect(replay.samples.some((sample) => !sample.jump)).toBe(true);
            for (const frame of expected) expect(reactionFrame(replay, frame.ms)).toMatchObject({ board: frame.board, remaining: frame.remaining });
            const [sample] = replay.samples;
            expect(reactionFrame(replay, sample.downMs).pressed).not.toBeNull();
            expect(reactionFrame(replay, sample.upMs).pressed).toBeNull();
            expect(replay.samples.every((item) => item.previousUpMs <= item.downMs && item.downMs <= item.upMs)).toBe(true);
        } finally {
            random.mockRestore();
        }
    });

    it('omits opened cells, flags and canceled presses while retaining their elapsed time', () => {
        const recorder = new ReactionRecorder(reactionModes[0], () => 0.99);
        recorder.capture({ action: 'lc', now: 100 });
        recorder.trigger(0, 0, 130);
        for (const [row, column, down, up] of [[0, 0, 200, 220], [1, 0, 300, 320]]) {
            recorder.capture({ action: 'lc', now: down });
            expect(recorder.trigger(row, column, up)).toBe(false);
        }
        recorder.capture({ action: 'lc', now: 400 });
        recorder.capture({ action: null, now: 410 });
        expect(recorder.trigger(0, 1, 420)).toBe(false);
        recorder.capture({ action: 'lc', now: 500 });
        recorder.trigger(0, 1, 530);
        let now = 600;
        for (let index = 0; index < 25 && recorder.game.phase !== 'won'; index++) {
            recorder.capture({ action: 'lc', now });
            recorder.trigger(0, recorder.game.nextColumn ?? 0, now + 20);
            now += 100;
        }
        const recording = recorder.finish();
        expect(recording.clicks.slice(0, 2)).toEqual([[0, 30], [370, 30]]);
        const replay = rebuildReactionReplay(reactionModes[0], recording, recorder.game.elapsedMs(now));
        expect(replay.samples[0]).toMatchObject({ previousUpMs: 0, downMs: 370, upMs: 400, jump: false });
        expect(recording.clicks.length).toBe(10 + recording.sides.length);
    });

    it('rejects damaged timing, sides, draws, unfinished games and mismatched scores', () => {
        const { recorder, scoreMs } = complete();
        const source = recorder.finish();
        for (const change of [{ draws: [] }, { draws: [...source.draws, 0] }, { sides: [] }, { sides: [...source.sides, 1] }, { clicks: source.clicks.slice(0, -1) }, { clicks: [[-1, 1]] }, { version: 2 }]) {
            expect(() => rebuildReactionReplay(reactionModes[0], { ...source, ...change }, scoreMs)).toThrow();
        }
        expect(() => rebuildReactionReplay(reactionModes[0], source, scoreMs + 1)).toThrow('Reaction score mismatch');
        expect(() => new ReactionRecorder(reactionModes[0]).finish()).toThrow('unfinished');
    });
});
