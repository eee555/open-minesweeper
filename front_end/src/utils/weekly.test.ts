import { describe, expect, it } from 'vitest';

import { MS_Mode, MS_State } from './ms_const';
import { TournamentParticipant } from './tournaments';
import { VideoAbstract } from './videoabstract';
import { WeeklyParticipant, WeeklyTournamentFormat } from './weekly';
import { matchesWeeklyFormat } from './weeklyFormat';

function video(level: 'i' | 'e', mode: MS_Mode, timems: number, right_ce = 1): VideoAbstract {
    return new VideoAbstract({
        id: timems,
        upload_time: '2026-01-01T00:00:00Z',
        level,
        mode,
        timems,
        right_ce,
        bv: 100,
        software: 'e',
        state: MS_State.Official,
    });
}

describe('WeeklyParticipant', () => {
    describe('constructor', () => {
        it('Default initialization', () => {
            const participant = new WeeklyParticipant();

            expect(participant).toBeInstanceOf(TournamentParticipant);
            expect(participant.id).toBe(0);
            expect(participant.user_id).toBe(0);
            expect(participant.classic_et).toEqual([[0, 240000], [0, 240000]]);
            expect(participant.classic_it).toEqual([
                [0, 60000],
                [0, 60000],
                [0, 60000],
                [0, 60000],
                [0, 60000],
            ]);
            expect(participant.classic_score).toBe(780000);
        });

        it('Partial initialization', () => {
            const participant = new WeeklyParticipant({
                id: 9,
                token: 'WEEKLY-TOKEN',
                user_id: 5,
                classic_et: [[1, 1234], [2, 2345]],
                classic_it: [[3, 3456]],
                classic_score: 7035,
            });

            expect(participant.id).toBe(9);
            expect(participant.token).toBe('WEEKLY-TOKEN');
            expect(participant.user_id).toBe(5);
            expect(participant.classic_e_sum).toBe(3579);
            expect(participant.classic_i_sum).toBe(3456);
            expect(participant.classic_score).toBe(7035);
        });

        it('Keeps score arrays independent between instances', () => {
            const first = new WeeklyParticipant();
            const second = new WeeklyParticipant();

            first.classic_et[0][1] = 1;

            expect(second.classic_et[0][1]).toBe(240000);
        });
    });

    describe('classic score cache', () => {
        it.each([
            [WeeklyTournamentFormat.Classic, [0, 1, 4]],
            [WeeklyTournamentFormat.NF, [1]],
            [WeeklyTournamentFormat.QWC, [2, 3]],
            [WeeklyTournamentFormat.QWCNF, [3]],
        ] as const)('uses only eligible %s videos for initial and appended scores', (format, indices) => {
            const videos = [video('i', MS_Mode.Standard, 10000), video('i', MS_Mode.Standard, 20000, 0), video('i', MS_Mode.HardcoreNG, 30000), video('i', MS_Mode.HardcoreNG, 40000, 0), video('i', MS_Mode.Standard, 50000, NaN)];
            const assigned = new WeeklyParticipant({ videos, tournament_format: format });
            const appended = new WeeklyParticipant({ tournament_format: format });
            videos.forEach((replay) => {
                appended.addVideo(replay);
            });
            const expected = indices.map((index) => [videos[index].id, videos[index].timems]).concat(Array.from({ length: 5 - indices.length }, () => [0, 60000]));
            expect(assigned.classic_it).toEqual(expected);
            expect(appended.classic_it).toEqual(expected);
            expect(assigned.classic_score).toBe(480000 + expected.reduce((sum, [, time]) => sum + time, 0));
            expect(appended.classic_score).toBe(assigned.classic_score);
            expect(assigned.videos).toHaveLength(videos.length);
            expect(matchesWeeklyFormat(video('i', MS_Mode.SpeedNG, 1, 0), format)).toBe(false);
            assigned.addVideo(video('i', format === 'q' || format === 'f' ? MS_Mode.HardcoreNG : MS_Mode.Standard, 60000, 0));
            expect(assigned.classic_it).toEqual(expected);
        });

        it('excludes non-official videos from assigned and appended scores', () => {
            const participant = new WeeklyParticipant();
            const rejected = Object.values(MS_State).filter((state) => state !== MS_State.Official).flatMap((state) => {
                return (['i', 'e'] as const).map((level) => {
                    const replay = video(level, MS_Mode.Standard, 1000);
                    replay.state = state;
                    return replay;
                });
            });

            participant.videos = rejected;
            expect(participant.classic_score).toBe(780000);
            rejected.forEach((replay) => {
                participant.addVideo(replay);
            });
            expect(participant.classic_score).toBe(780000);

            const official = video('i', MS_Mode.Standard, 20000);
            participant.addVideo(official);
            expect(participant.classic_score).toBe(740000);
            official.state = MS_State.Frozen;
            participant.refresh();
            expect(participant.classic_score).toBe(780000);
        });

        it('refreshes classic score fields from assigned videos without duplicating them', () => {
            const videos = [
                video('e', MS_Mode.Standard, 110000),
                video('e', MS_Mode.SpeedNG, 90000),
                video('i', MS_Mode.Standard, 20000, 0),
            ];
            const participant = new WeeklyParticipant();

            participant.videos = videos;

            expect(participant.videos).toHaveLength(3);
            expect(participant.classic_et).toEqual([[110000, 110000], [0, 240000]]);
            expect(participant.classic_it).toEqual([
                [20000, 20000],
                [0, 60000],
                [0, 60000],
                [0, 60000],
                [0, 60000],
            ]);
            expect(participant.classic_score).toBe(610000);
        });

        it('appends a video and updates classic score fields using milliseconds', () => {
            const participant = new WeeklyParticipant();

            participant.addVideo(video('i', MS_Mode.Standard, 20000));

            expect(participant.videos).toHaveLength(1);
            expect(participant.classic_it[0]).toEqual([20000, 20000]);
            expect(participant.classic_i_sum).toBe(260000);
            expect(participant.classic_score).toBe(740000);
        });
    });
});
