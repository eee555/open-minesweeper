import { describe, expect, it } from 'vitest';

import { MS_Mode, TournamentState, TournamentSubclass } from './ms_const';
import { Tournament, TournamentParticipant } from './tournaments';
import { VideoAbstract } from './videoabstract';

describe('TournamentParticipant', () => {
    it('maintains replay presence for participant deletion controls when personal videos load or upload', () => {
        const participant = new TournamentParticipant({ has_videos: true });
        participant.videos = [];
        expect(participant.has_videos).toBe(false);
        participant.addVideo(new VideoAbstract({ level: 'i', mode: MS_Mode.Standard, software: 'e', timems: 1000, bv: 30 }));
        expect(participant.has_videos).toBe(true);
    });
    describe('constructor', () => {
        it('Default initialization', () => {
            const participant = new TournamentParticipant();

            expect(participant.id).toBe(0);
            expect(participant.token).toBe('');
            expect(participant.arbiter_identifier__identifier).toBeUndefined();
            expect(participant.tournament_id).toBe(0);
            expect(participant.user_id).toBe(0);
            expect(participant.start_time).toBeUndefined();
            expect(participant.end_time).toBeUndefined();
            expect(participant.rank).toBeUndefined();
            expect(participant.rank_score).toBe(0);
        });

        it('Partial initialization', () => {
            const participant = new TournamentParticipant({
                id: 7,
                token: 'TOKEN',
                tournament_id: 3,
                user_id: 11,
                start_time: new Date('2026-01-01T08:00:00+08:00'),
                end_time: new Date('2026-01-01T10:00:00+08:00'),
                rank: 2,
                rank_score: 32,
            });

            expect(participant.id).toBe(7);
            expect(participant.token).toBe('TOKEN');
            expect(participant.tournament_id).toBe(3);
            expect(participant.user_id).toBe(11);
            expect(participant.start_time).toEqual(new Date('2026-01-01T08:00:00+08:00'));
            expect(participant.end_time).toEqual(new Date('2026-01-01T10:00:00+08:00'));
            expect(participant.rank).toBe(2);
            expect(participant.rank_score).toBe(32);
        });
    });
});

describe('Tournament', () => {
    describe('constructor', () => {
        it('Default initialization', () => {
            const tournament = new Tournament({});

            expect(tournament.id).toBe(0);
            expect(tournament.name).toBe('');
            expect(tournament.description).toBeUndefined();
            expect(tournament.startDate).toBeUndefined();
            expect(tournament.endDate).toBeUndefined();
            expect(tournament.hostId).toBe(0);
            expect(tournament.hostName).toBe('');
            expect(tournament.state).toBe(TournamentState.Pending);
            expect(tournament.getDisplayState()).toBe(TournamentState.Pending);
            expect(tournament.subclass).toBe(TournamentSubclass.Unknown);
        });

        it('Uses camelCase fields', () => {
            const tournament = new Tournament({
                id: 1,
                name: 'Spring Cup',
                description: 'Fast games',
                startDate: '2025-01-02T03:04:05Z',
                endDate: '2025-01-03T04:05:06Z',
                hostId: 9,
                hostName: 'Host',
                state: TournamentState.Ongoing,
                subclass: TournamentSubclass.Weekly,
            });

            expect(tournament.id).toBe(1);
            expect(tournament.name).toBe('Spring Cup');
            expect(tournament.description).toBe('Fast games');
            expect(tournament.startDate).toEqual(new Date('2025-01-02T03:04:05Z'));
            expect(tournament.endDate).toEqual(new Date('2025-01-03T04:05:06Z'));
            expect(tournament.hostId).toBe(9);
            expect(tournament.hostName).toBe('Host');
            expect(tournament.state).toBe(TournamentState.Ongoing);
            expect(tournament.subclass).toBe(TournamentSubclass.Weekly);
        });

        it('Uses snake_case fallback fields', () => {
            const tournament = new Tournament({
                start_time: '2025-02-02T03:04:05Z',
                end_time: '2025-02-03T04:05:06Z',
                host_id: 11,
                host_realname: 'Fallback Host',
            });

            expect(tournament.startDate).toEqual(new Date('2025-02-02T03:04:05Z'));
            expect(tournament.endDate).toEqual(new Date('2025-02-03T04:05:06Z'));
            expect(tournament.hostId).toBe(11);
            expect(tournament.hostName).toBe('Fallback Host');
        });

        it('Derives GSC display fields from subclass data', () => {
            const tournament = new Tournament({
                subclass: TournamentSubclass.GSC,
                data: {
                    order: 8,
                    token: 'G12345',
                },
            });

            expect(tournament.getLocalName('zh-CN')).toBe('第8届金羊杯');
            expect(tournament.getLocalName('en')).toBe('GSC#8');
            expect(tournament.description).toBe('');
        });

        it('Derives weekly display fields from subclass data', () => {
            const tournament = new Tournament({
                subclass: TournamentSubclass.Weekly,
                data: {
                    year: 2026,
                    week: 12,
                    tournament_format: 'c',
                },
            });

            expect(tournament.getLocalName('zh-CN')).toBe('经典竞速打卡赛 2026年第12周');
            expect(tournament.getLocalName('en')).toBe('Classic Speed Weekly 2026#12');
            expect(tournament.description).toBe('');
        });
    });

    describe('getLocalDescription', () => {
        it('String description', () => {
            const tournament = new Tournament({ description: 'Plain text' });
            expect(tournament.getLocalDescription('zh-CN')).toBe('Plain text');
        });

        it('Locale fallback', () => {
            const tournament = new Tournament({
                description: {
                    en: 'English',
                    zh: 'Chinese',
                },
            });

            expect(tournament.getLocalDescription('zh-CN')).toBe('Chinese');
            expect(tournament.getLocalDescription('fr')).toBe('English');
            expect(tournament.getLocalDescription('zh')).toBe('Chinese');
        });

        it('Missing description returns empty string', () => {
            const tournament = new Tournament({});
            expect(tournament.getLocalDescription('en')).toBe('');
        });
    });

    describe('getLocalName', () => {
        it('String name', () => {
            const tournament = new Tournament({ name: 'Cup' });
            expect(tournament.getLocalName('fr')).toBe('Cup');
        });

        it('Locale fallback for object name', () => {
            const tournament = new Tournament({
                name: {
                    en: 'Cup',
                    zh: '杯赛',
                },
            });

            expect(tournament.getLocalName('zh-Hans')).toBe('杯赛');
            expect(tournament.getLocalName('fr')).toBe('Cup');
        });
    });

    describe('localFallback', () => {
        it('Chinese variants fall back to zh', () => {
            expect(Tournament.localFallback('zh-CN')).toBe('zh');
        });

        it('Unknown locales fall back to en', () => {
            expect(Tournament.localFallback('fr')).toBe('en');
        });

        it('Base locales end fallback chain', () => {
            expect(Tournament.localFallback('zh')).toBeUndefined();
            expect(Tournament.localFallback('en')).toBeUndefined();
            expect(Tournament.localFallback(undefined)).toBeUndefined();
        });
    });

    describe('display time', () => {
        it('displayStartTime', () => {
            const tournament = new Tournament({ startDate: new Date(2025, 0, 5, 8, 9, 10) });
            expect(tournament.displayStartTime()).toBe('2025-01-05 08:09:10');
        });

        it('displayEndTime', () => {
            const tournament = new Tournament({ endDate: new Date(2025, 0, 5, 8, 9, 10) });
            expect(tournament.displayEndTime()).toBe('2025-01-05 08:09:10');
        });

        it('Missing dates return empty string', () => {
            const tournament = new Tournament({});
            expect(tournament.displayStartTime()).toBe('');
            expect(tournament.displayEndTime()).toBe('');
        });
    });

    describe('display state', () => {
        const now = new Date('2025-01-02T00:00:00Z');

        it('keeps explicit non-normal states', () => {
            const tournament = new Tournament({
                state: TournamentState.Awarded,
                startDate: '2025-01-01T00:00:00Z',
                endDate: '2025-01-03T00:00:00Z',
            });

            expect(tournament.getDisplayState(now)).toBe(TournamentState.Awarded);
        });

        it('derives preparing from normal tournaments before start time', () => {
            const tournament = new Tournament({
                state: TournamentState.Normal,
                startDate: '2025-01-03T00:00:00Z',
                endDate: '2025-01-04T00:00:00Z',
            });

            expect(tournament.getDisplayState(now)).toBe(TournamentState.Preparing);
        });

        it('derives ongoing from normal tournaments within the time window', () => {
            const tournament = new Tournament({
                state: TournamentState.Normal,
                startDate: '2025-01-01T00:00:00Z',
                endDate: '2025-01-03T00:00:00Z',
            });

            expect(tournament.getDisplayState(now)).toBe(TournamentState.Ongoing);
        });

        it('derives finished from normal tournaments after end time', () => {
            const tournament = new Tournament({
                state: TournamentState.Normal,
                startDate: '2025-01-01T00:00:00Z',
                endDate: '2025-01-02T00:00:00Z',
            });

            expect(tournament.getDisplayState(now)).toBe(TournamentState.Finished);
        });

        it('keeps normal when dates are incomplete', () => {
            const tournament = new Tournament({ state: TournamentState.Normal });

            expect(tournament.getDisplayState(now)).toBe(TournamentState.Normal);
        });
    });

    describe('validation state', () => {
        it('can validate pending tournaments with a valid time range', () => {
            const tournament = new Tournament({
                state: TournamentState.Pending,
                startDate: '2025-01-01T00:00:00Z',
                endDate: '2025-01-02T00:00:00Z',
            });

            expect(tournament.canValidate).toBe(true);
        });

        it('cannot validate tournaments with invalid time ranges', () => {
            const missingDates = new Tournament({ state: TournamentState.Pending });
            const reversedDates = new Tournament({
                state: TournamentState.Pending,
                startDate: '2025-01-02T00:00:00Z',
                endDate: '2025-01-01T00:00:00Z',
            });

            expect(missingDates.canValidate).toBe(false);
            expect(reversedDates.canValidate).toBe(false);
        });

        it('cannot validate tournaments that are already active or finalized', () => {
            const states = [
                TournamentState.Awarded,
                TournamentState.Normal,
                TournamentState.Finished,
                TournamentState.Ongoing,
                TournamentState.Preparing,
            ];

            for (const state of states) {
                expect(new Tournament({
                    state,
                    startDate: '2025-01-01T00:00:00Z',
                    endDate: '2025-01-02T00:00:00Z',
                }).canValidate).toBe(false);
            }
        });

        it('can invalidate every state except awarded and cancelled', () => {
            expect(new Tournament({ state: TournamentState.Awarded }).canInvalidate).toBe(false);
            expect(new Tournament({ state: TournamentState.Cancelled }).canInvalidate).toBe(false);
            expect(new Tournament({ state: TournamentState.Pending }).canInvalidate).toBe(true);
            expect(new Tournament({ state: TournamentState.Ongoing }).canInvalidate).toBe(true);
        });
    });
});
