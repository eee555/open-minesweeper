import { AxiosHeaders } from 'axios';
import { afterEach, describe, expect, it } from 'vitest';

import { createWeeklyParticipant } from './tournamentService';
import type { TournamentParticipantResponse } from './tournamentService';

import $axios from '@/http';
import { MS_Mode, MS_State } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';
import { WeeklyParticipant, WeeklyTournamentFormat } from '@/utils/weekly';

describe('weekly participant registration', () => {
    const originalAdapter = $axios.defaults.adapter;
    afterEach(() => {
        $axios.defaults.adapter = originalAdapter;
    });

    it.each(Object.values(WeeklyTournamentFormat))('returns a participant ready to score format %s', async (format) => {
        const data: TournamentParticipantResponse = { id: 81, token: 'WEEKLY', start_time: '2026-11-25T10:00:00Z', end_time: '2026-11-25T12:00:00Z', rank: null, rank_score: 0, user_id: 99, tournament_id: 8, has_videos: false };
        $axios.defaults.adapter = (config) => {
            expect(config.url).toBe('/api/tournament/weekly/participant');
            expect(config.data).toBe('id=8');
            return Promise.resolve({ data, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
        };

        const participant = await createWeeklyParticipant(8, format);
        expect(participant).toBeInstanceOf(WeeklyParticipant);
        expect(participant).toMatchObject({ id: 81, token: 'WEEKLY', user_id: 99, tournament_id: 8, tournament_format: format });
        expect(participant.start_time).toEqual(new Date(data.start_time));
        expect(participant.end_time).toEqual(new Date('2026-11-25T12:00:00Z'));

        const mode = format === WeeklyTournamentFormat.Classic || format === WeeklyTournamentFormat.NF ? MS_Mode.Standard : MS_Mode.HardcoreNG;
        const replay = new VideoAbstract({ id: 901, level: 'i', mode, right_ce: 0, timems: 20000, bv: 80, software: 'e', state: MS_State.Official });
        participant.addVideo(replay);
        expect(participant.classic_score).toBe(740000);
    });
});
