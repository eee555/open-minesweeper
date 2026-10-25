import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchMinigameRankings, submitMinigameScore } from './minigameRankingService';

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
