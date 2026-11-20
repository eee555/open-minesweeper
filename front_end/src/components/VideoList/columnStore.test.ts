import type { useStorage, UseStorageOptions } from '@vueuse/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';

const storage = vi.hoisted(() => {
    const values = new Map<string, string>();
    return { getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => {
            values.set(key, value);
        },
        removeItem: (key: string) => {
            values.delete(key);
        },
        clear: () => {
            values.clear();
        } };
});
vi.mock('@vueuse/core', async (importOriginal) => {
    const actual = await importOriginal<{ useStorage: typeof useStorage }>();
    return { ...actual, useLocalStorage: (key: string, defaults: unknown, options: UseStorageOptions<unknown>) => actual.useStorage(key, defaults, storage, options) };
});
beforeEach(() => {
    vi.resetModules(); storage.clear();
});

describe('video column preferences', () => {
    it('generates defaults in the active language and keeps saved names unchanged', async () => {
        const { default: i18n } = await import('@/i18n');
        const { createColumnStore } = await import('./columnStore');
        const { presetColumn } = await import('./presets');
        const originalLocale = i18n.global.locale.value;
        try {
            const key = 'localized-video-columns';
            const store = createColumnStore(key, () => [presetColumn('time')]);
            i18n.global.locale.value = 'zh-cn';
            const expected = [presetColumn('time')];
            expect(store.columns.value).toEqual(expected);
            store.columns.value = [...store.columns.value];
            await nextTick();
            i18n.global.locale.value = 'en';
            expect(store.columns.value).toEqual(expected);
            expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual(store.columns.value);
        } finally {
            i18n.global.locale.value = originalLocale;
        }
    });

    it('shares two independent groups, ignores old preferences and persists an empty array', async () => {
        storage.setItem('video-list-config', JSON.stringify({ profile: [], tournament: [], query: [] }));
        const { videoColumnStore, videoDescriptionStore } = await import('./columnStore');
        const fixed = videoColumnStore('fixed-player');
        expect(videoColumnStore('fixed-player')).toBe(fixed);
        const { defaultVideoColumns } = await import('./presets');
        expect(fixed.columns.value).toEqual(defaultVideoColumns('fixed-player'));
        const mixed = videoColumnStore('mixed-players');
        const original = [...mixed.columns.value];
        const description = [...videoDescriptionStore.columns.value];
        fixed.columns.value = [];
        await nextTick();
        expect(mixed.columns.value).toEqual(original);
        expect(videoDescriptionStore.columns.value).toEqual(description);
        expect(storage.getItem('video-list-columns-v1:fixed-player')).toBe('[]');
        const { createColumnStore } = await import('./columnStore');
        expect(createColumnStore('video-list-columns-v1:fixed-player', () => original).columns.value).toEqual([]);
    });

    it.each(['not json', '[{"type":"upload_time"}]'])('keeps broken storage intact until a valid edit: %s', async (raw) => {
        const key = 'video-list-columns-v1:mixed-players';
        storage.setItem(key, raw);
        const { videoColumnStore } = await import('./columnStore');
        const store = videoColumnStore('mixed-players');
        expect(store.columns.value.length).toBeGreaterThan(0);
        expect(store.error.value).toBe('invalidConfig');
        await nextTick();
        expect(storage.getItem(key)).toBe(raw);
        store.columns.value = [{ type: 'bool', key: 'NF', expr: 'right_ce == 0' }];
        await nextTick();
        expect(store.error.value).toBe('');
        expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual(store.columns.value);
    });
});
