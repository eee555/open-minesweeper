import { leftClickModes, multiTouchModes } from './leftClickTraining';

import { ms_to_s } from '@/utils';

export type ClickScoreDisplay = 'time' | 'ces';
const clickModes = new Map([...leftClickModes, ...multiTouchModes].map((mode) => [mode.rankingKey, mode]));

/** Successful clicks per second, excluding the first click that starts timing. */
export function clickCes(timeMs: number, successfulClicks: number): number {
    return timeMs > 0 ? Math.max(0, successfulClicks - 1) * 1000 / timeMs : 0;
}

export function formatMinigameScore(timeMs: number, rankingKey: string, display: ClickScoreDisplay): string {
    const mode = display === 'ces' ? clickModes.get(rankingKey) : undefined;
    return mode ? clickCes(timeMs, mode.safe).toFixed(3) : ms_to_s(timeMs);
}
