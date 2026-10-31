import { describe, expect, it } from 'vitest';

import { clickCes, formatMinigameScore } from './scoreDisplay';

describe('click training score display', () => {
    it('shows zero before starting and excludes the first successful click', () => {
        expect(clickCes(0, 0)).toBe(0);
        expect(clickCes(0, 2)).toBe(0);
        expect(clickCes(1000, 0)).toBe(0);
        expect(clickCes(1000, 1)).toBe(0);
        expect(clickCes(500, 2)).toBe(2);
    });

    it('converts completed scores using the safe-cell count of each configuration', () => {
        for (const game of ['left-click', 'multi-touch']) {
            for (const [key, ce] of [['b-50-v1', 31], ['i-75-v1', 63], ['e-87.5-v1', 59]] as const) {
                expect(formatMinigameScore(2000, `${game}-${key}`, 'ces')).toBe((ce / 2).toFixed(3));
            }
        }
        expect(formatMinigameScore(1234, 'left-click-b-50-v1', 'ces')).toBe('25.122');
    });

    it('keeps time display and other games in seconds', () => {
        expect(formatMinigameScore(1234, 'left-click-b-50-v1', 'time')).toBe('1.234');
        expect(formatMinigameScore(1234, 'multi-touch-b-50-v1', 'time')).toBe('1.234');
        expect(formatMinigameScore(1234, 'flag-chord-b-v1', 'ces')).toBe('1.234');
        expect(formatMinigameScore(1234, 'missing-cell-b-v1', 'ces')).toBe('1.234');
    });
});
