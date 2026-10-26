import { useLocalStorage } from '@vueuse/core';
import type { useStorage, UseStorageOptions } from '@vueuse/core';
import { describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick } from 'vue';

import { restartHotkeyFromEvent } from './hotkey';
import { defaultMinigameSettings, minigameSettings } from './settings';
import type { MinigameSettings } from './settings';

const storage = vi.hoisted(() => {
    const values = new Map<string, string>();
    return {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => {
            values.set(key, value);
        },
        removeItem: (key: string) => {
            values.delete(key);
        },
    };
});

vi.mock('@vueuse/core', async (importOriginal) => {
    const actual = await importOriginal<{ useStorage: typeof useStorage }>();
    return { ...actual, useLocalStorage: (key: string, defaults: MinigameSettings, options: UseStorageOptions<MinigameSettings>) => actual.useStorage(key, defaults, storage, options) };
});

describe('shared minigame settings storage', () => {
    it('defaults to unset, restores a persisted combination and keeps it cleared after reopening', async () => {
        expect(minigameSettings.value.restartHotkey).toBeNull();
        expect(minigameSettings.value.leftClickMineOpacity).toBe(0.5);
        expect(minigameSettings.value.leftClickMinePressed).toBe(false);
        expect(minigameSettings.value.cellSize).toBe(32);
        expect(minigameSettings.value.multiTouchOrientation).toBe('horizontal');
        const restartHotkey = restartHotkeyFromEvent({ key: 'r', code: 'KeyR', ctrlKey: true, altKey: false, shiftKey: false, metaKey: false, repeat: false, isComposing: false });
        minigameSettings.value.restartHotkey = restartHotkey;
        minigameSettings.value.leftClickMineOpacity = 0.23;
        minigameSettings.value.leftClickMinePressed = true;
        minigameSettings.value.cellSize = 40;
        minigameSettings.value.multiTouchOrientation = 'vertical';
        await nextTick();
        expect(JSON.parse(storage.getItem('minigame-settings') ?? '{}')).toEqual({ restartHotkey, cellSize: 40, leftClickMineOpacity: 0.23, leftClickMinePressed: true, multiTouchOrientation: 'vertical' });
        const scope = effectScope();
        try {
            const restored = scope.run(() => useLocalStorage<MinigameSettings>('minigame-settings', defaultMinigameSettings(), { mergeDefaults: true }));
            expect(restored?.value.restartHotkey).toEqual(restartHotkey);
            expect(restored?.value.leftClickMineOpacity).toBe(0.23);
            expect(restored?.value.leftClickMinePressed).toBe(true);
            expect(restored?.value.cellSize).toBe(40);
            expect(restored?.value.multiTouchOrientation).toBe('vertical');
            minigameSettings.value.restartHotkey = null;
            await nextTick();
            const cleared = scope.run(() => useLocalStorage<MinigameSettings>('minigame-settings', defaultMinigameSettings(), { mergeDefaults: true }));
            expect(cleared?.value.restartHotkey).toBeNull();
            expect(cleared?.value.leftClickMineOpacity).toBe(0.23);
            expect(cleared?.value.leftClickMinePressed).toBe(true);
            expect(cleared?.value.cellSize).toBe(40);
            expect(cleared?.value.multiTouchOrientation).toBe('vertical');
        } finally {
            scope.stop();
        }
    });

    it('adds default cell size and opacity to older settings while preserving the saved hotkey', () => {
        const restartHotkey = restartHotkeyFromEvent({ key: 'F2', code: 'F2', ctrlKey: false, altKey: false, shiftKey: false, metaKey: false, repeat: false, isComposing: false });
        storage.setItem('minigame-settings', JSON.stringify({ restartHotkey }));
        const scope = effectScope();
        try {
            const restored = scope.run(() => useLocalStorage<MinigameSettings>('minigame-settings', defaultMinigameSettings(), { mergeDefaults: true }));
            expect(restored?.value).toEqual({ restartHotkey, cellSize: 32, leftClickMineOpacity: 0.5, leftClickMinePressed: false, multiTouchOrientation: 'horizontal' });
        } finally {
            scope.stop();
        }
    });

    it.each([0, 1])('restores the saved opacity endpoint %s', (leftClickMineOpacity) => {
        storage.setItem('minigame-settings', JSON.stringify({ restartHotkey: null, leftClickMineOpacity }));
        const scope = effectScope();
        try {
            const restored = scope.run(() => useLocalStorage<MinigameSettings>('minigame-settings', defaultMinigameSettings(), { mergeDefaults: true }));
            expect(restored?.value.leftClickMineOpacity).toBe(leftClickMineOpacity);
            expect(restored?.value.cellSize).toBe(32);
        } finally {
            scope.stop();
        }
    });
});
