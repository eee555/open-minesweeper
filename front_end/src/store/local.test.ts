import type { useStorage, UseStorageOptions } from '@vueuse/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';

import type { LocalSettings } from './local';

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
    return {
        ...actual,
        useLocalStorage: (key: string, defaults: LocalSettings, options: UseStorageOptions<LocalSettings>) => actual.useStorage(key, defaults, storage, options),
    };
});

beforeEach(() => {
    vi.resetModules();
    storage.removeItem('local');
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    vi.stubGlobal('navigator', { language: 'en-US' });
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('local settings', () => {
    it.each([true, false])('removes the retired help preference %s without resetting other settings', async (tooltipShow) => {
        const preferences = { language: 'fr', navigation_layout: 'sidebar', notification_duration: 0, vienna_logo_legacy: true };
        storage.setItem('local', JSON.stringify({ ...preferences, tooltip_show: tooltipShow }));

        const { local } = await import('./local');
        expect(local.value).not.toHaveProperty('tooltip_show');
        expect(local.value).toMatchObject(preferences);
        await nextTick();
        const saved: unknown = JSON.parse(storage.getItem('local') ?? '{}');
        expect(saved).not.toHaveProperty('tooltip_show');
        expect(saved).toMatchObject(preferences);
    });

    it('does not add a help preference to new settings', async () => {
        const { local } = await import('./local');
        expect(local.value).not.toHaveProperty('tooltip_show');
        expect(local.value.language).toBe('en-us');
    });
});
