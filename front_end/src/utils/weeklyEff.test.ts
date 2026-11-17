import { describe, expect, it } from 'vitest';

import { MS_Mode, MS_State } from './ms_const';
import { VideoAbstract } from './videoabstract';
import { isWeeklyEffSupportedVideo, WeeklyEffParticipant, weeklyEffVideoScore } from './weeklyEff';

function video(id: number, level: 'i' | 'e', timems: number, bv = 6): VideoAbstract {
    return new VideoAbstract({ id, level, timems, bv, cl: 3, software: 'e', mode: MS_Mode.Standard, state: MS_State.Official });
}

describe('WeeklyEffParticipant', () => {
    it('uses the original floating ratio without rounding or a raw time limit', () => {
        const replay = video(1, 'i', 90001, 7);
        expect(weeklyEffVideoScore(replay)).toBe(90001 * 3 / 7000);
        expect(isWeeklyEffSupportedVideo(replay)).toBe(true);
        expect(isWeeklyEffSupportedVideo(video(2, 'i', 60000, 3))).toBe(false);
        expect(isWeeklyEffSupportedVideo(video(3, 'e', 240000, 3))).toBe(false);
    });

    it('maintains 2 Expert and 5 Intermediate results and supports score regression', () => {
        const participant = new WeeklyEffParticipant();
        const replays = [video(1, 'e', 200001), video(2, 'e', 180003), video(3, 'e', 220001), video(4, 'i', 90000)];
        participant.videos = replays;
        expect(participant.et.map(([id]) => id)).toEqual([2, 1]);
        expect(participant.it.map(([id]) => id)).toEqual([4, 0, 0, 0, 0]);
        expect(participant.score).toBe(participant.e_sum + participant.i_sum);
        const before = participant.score;
        replays[1].state = MS_State.Frozen;
        participant.refresh();
        expect(participant.et.map(([id]) => id)).toEqual([1, 3]);
        expect(participant.score).toBeGreaterThan(before);
        participant.addVideo(video(5, 'i', 10000));
        expect(participant.it[0][0]).toBe(5);
        expect(participant.has_videos).toBe(true);
    });

    it('rejects nonofficial, nonstandard and invalid metrics and keeps defaults independent', () => {
        const participant = new WeeklyEffParticipant();
        const frozen = video(1, 'i', 1);
        frozen.state = MS_State.Frozen;
        const nonstandard = video(2, 'e', 1);
        nonstandard.mode = MS_Mode.SpeedNG;
        const invalid = [video(3, 'i', 0), video(4, 'i', 1000, 0), video(5, 'i', 1000)];
        invalid[2].cl = NaN;
        participant.videos = [frozen, nonstandard, ...invalid];
        expect(participant.score).toBe(780);
        participant.et[0][1] = 0;
        expect(new WeeklyEffParticipant().et[0][1]).toBe(240);
    });
});
