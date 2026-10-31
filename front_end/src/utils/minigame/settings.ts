import { onKeyStroke, useLocalStorage } from '@vueuse/core';

import { matchesRestartHotkey } from './hotkey';
import type { RestartHotkey } from './hotkey';
import type { ClickScoreDisplay } from './scoreDisplay';

export interface MinigameSettings {
    restartHotkey: RestartHotkey | null;
    cellSize: number;
    leftClickMineOpacity: number;
    leftClickMinePressed: boolean;
    leftClickScoreDisplay: ClickScoreDisplay;
    multiTouchOrientation: 'horizontal' | 'vertical';
}

export function defaultMinigameSettings(): MinigameSettings {
    return { restartHotkey: null, cellSize: 32, leftClickMineOpacity: 0.5, leftClickMinePressed: false, leftClickScoreDisplay: 'time', multiTouchOrientation: 'horizontal' };
}

export const minigameSettings = useLocalStorage<MinigameSettings>('minigame-settings', defaultMinigameSettings(), { mergeDefaults: true });

export function useRestartHotkey(restart: () => void): void {
    onKeyStroke((event) => {
        if (event.defaultPrevented || !matchesRestartHotkey(minigameSettings.value.restartHotkey, event)) return;
        const target = event.target instanceof HTMLElement ? event.target : document.activeElement;
        if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select') !== null)) return;
        event.preventDefault();
        restart();
    }, { dedupe: true });
}
