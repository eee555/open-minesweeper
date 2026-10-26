import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchMinigameRankings, fetchMinigameReplay, submitMinigameScore } from './minigameRankingService';

import $axios from '@/http';
import type { MinigameReplayData } from '@/utils/minigame/history';

describe('minigame ranking API', () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('shares ranking metadata requests and retries after a failure', async () => {
        const get = vi.spyOn($axios, 'get').mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: [{ game: 'flag-chord', rankings: [] }] });
        await expect(fetchMinigameRankings()).rejects.toThrow('offline');
        const [first, second] = await Promise.all([fetchMinigameRankings(), fetchMinigameRankings()]);
        expect(first).toBe(second);
        expect(get).toHaveBeenCalledTimes(2);
        expect(get).toHaveBeenLastCalledWith('/api/minigame/rankings');
    });

    it('loads the 7z as binary with its matching score and forwards cancellation', async () => {
        const archive = new Uint8Array([0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c]).buffer;
        const get = vi.spyOn($axios, 'get').mockResolvedValue({ data: archive, headers: { 'x-minigame-score': '1234' } });
        const { signal } = new AbortController();
        await expect(fetchMinigameReplay('left-click', 'b-50-v1', 42, signal)).resolves.toEqual({ archive, scoreMs: 1234 });
        expect(get).toHaveBeenCalledWith('/api/minigame/left-click/replay', { params: { player: 42, key: 'b-50-v1' }, responseType: 'arraybuffer', signal });
        get.mockResolvedValue({ data: archive, headers: {} });
        await expect(fetchMinigameReplay('left-click', 'b-50-v1', 42)).rejects.toThrow('Missing minigame replay score');
    });

    it.each<[string, MinigameReplayData]>([
        ['left-click-b-50-v1', { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [], specialEvents: [] }],
        ['multi-touch-b-50-v1', { version: 1, cellSize: 32, initialBoard: 'AAAAAP////8', events: [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]] }],
        ['flag-chord-b-v1', { version: 1, cellSize: 32, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], events: [], specialEvents: [] }],
        ['missing-cell-b-v1', { version: 1, rounds: Array.from({ length: 10 }, (_, index) => ({ board: 'gAAAAAAAAAA', target: [7, 7], timeMs: index === 0 ? 1234 : 0 })) }],
    ])('submits score and replay JSON for %s', async (rankingKey, replay) => {
        const response = { improved: true, record: { id: 1, ranking_key: rankingKey, player_id: 42, score: 1234, achieved_at: '2026-10-24T08:00:00Z' } };
        const post = vi.spyOn($axios, 'post').mockResolvedValue({ data: response });
        await expect(submitMinigameScore(rankingKey, 1234, replay)).resolves.toEqual(response);
        expect(post).toHaveBeenCalledWith(`/api/minigame/${rankingKey}/score`, { score: 1234, replay: JSON.stringify(replay) });
    });
});
