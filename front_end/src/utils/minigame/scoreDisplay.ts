import { leftClickModes, multiTouchModes } from './leftClickTraining';

import { ms_to_s } from '@/utils';

export type ClickScoreDisplay = 'time' | 'ces';
const clickModes = new Map([...leftClickModes, ...multiTouchModes].map((mode) => [mode.rankingKey, mode]));

/** Successful clicks per second, excluding the first click that starts timing. */
export function clickCes(timeMs: number, successfulClicks: number): number {
    return timeMs > 0 ? Math.max(0, successfulClicks - 1) * 1000 / timeMs : 0;
}

/** CES for a click-training ranking, or null when the ranking has no CES metric. */
export function minigameCes(timeMs: number, rankingKey: string): number | null {
    const mode = clickModes.get(rankingKey);
    return mode === undefined ? null : clickCes(timeMs, mode.safe);
}

export function formatMinigameScore(timeMs: number, rankingKey: string, display: ClickScoreDisplay): string {
    const ces = display === 'ces' ? minigameCes(timeMs, rankingKey) : null;
    return ces === null ? ms_to_s(timeMs) : ces.toFixed(3);
}
