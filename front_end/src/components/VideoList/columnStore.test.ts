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
        const { presetColumn, presetExpressionColumn } = await import('./presets');
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
            expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual({ version: 2, columns: store.columns.value });
            store.columns.value = [{ ...presetExpressionColumn('time'), key: 'Renamed' }];
            await nextTick();
            expect(createColumnStore(key, () => []).columns.value).toEqual([{ ...presetExpressionColumn('time'), key: 'Renamed' }]);
        } finally {
            i18n.global.locale.value = originalLocale;
        }
    });

    it('shares two independent groups, ignores old preferences and persists an empty array', async () => {
        storage.setItem('video-list-config', JSON.stringify({ profile: [], tournament: [], query: [] }));
        storage.setItem('video-list-columns-v1:fixed-player', JSON.stringify([{ type: 'data', key: 'Old', expr: 'bv' }]));
        storage.setItem('video-abstract-description-v1', JSON.stringify([{ type: 'data', key: 'Old', expr: 'bv', width: 1 }]));
        const { videoColumnStore, videoDescriptionStore } = await import('./columnStore');
        const fixed = videoColumnStore('fixed-player');
        expect(videoColumnStore('fixed-player')).toBe(fixed);
        const { defaultVideoColumns, defaultVideoDescription } = await import('./presets');
        expect(fixed.columns.value).toEqual(defaultVideoColumns('fixed-player'));
        const mixed = videoColumnStore('mixed-players');
        const original = [...mixed.columns.value];
        const description = [...videoDescriptionStore.columns.value];
        expect(description).toEqual(defaultVideoDescription());
        fixed.columns.value = [];
        await nextTick();
        expect(mixed.columns.value).toEqual(original);
        expect(videoDescriptionStore.columns.value).toEqual(description);
        expect(JSON.parse(storage.getItem('video-list-columns:fixed-player') ?? 'null')).toEqual({ version: 2, columns: [] });
        const { createColumnStore } = await import('./columnStore');
        expect(createColumnStore('video-list-columns:fixed-player', () => original).columns.value).toEqual([]);
    });

    it.each([
        'not json',
        '[{"type":"upload_time"}]',
        '{"version":2,"columns":[{"type":"upload_time"}]}',
        '{"version":1,"columns":[{"type":"bool","key":"","expr":"bv > 1"}]}',
        '{"version":3,"columns":[]}',
    ])('keeps unsupported or broken storage intact until a valid edit: %s', async (raw) => {
        const key = 'video-list-columns:mixed-players';
        storage.setItem(key, raw);
        const { videoColumnStore } = await import('./columnStore');
        const store = videoColumnStore('mixed-players');
        expect(store.columns.value.length).toBeGreaterThan(0);
        expect(store.error.value).toBe('invalidConfig');
        await nextTick();
        expect(storage.getItem(key)).toBe(raw);
        store.columns.value = [{ id: 'nf', type: 'bool', key: 'NF', expr: 'right_ce == 0' }];
        await nextTick();
        expect(store.error.value).toBe('');
        expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual({ version: 2, columns: store.columns.value });
    });

    it.each([false, true])('migrates v1 in place while preserving names, expressions, existing IDs and widths (tooltip: %s)', async (description) => {
        const key = 'migration-columns';
        const columns = [
            { type: 'state' },
            { id: 'keep-id', type: 'bool', key: 'Keep', expr: 'right_ce == 0' },
            { type: 'data.3f', key: '自定义名', expr: 'bv / (timems / 1000)' },
            { type: 'data', key: 'Same expression', expr: 'bv / (timems / 1000)' },
        ].map((column, index) => ({ ...column, ...description ? { width: index % 3 + 1 } : {} }));
        storage.setItem(key, JSON.stringify({ version: 1, columns }));
        const { createColumnStore } = await import('./columnStore');
        const { defaultVideoColumns, defaultVideoDescription } = await import('./presets');
        const store = createColumnStore(key, () => (description ? defaultVideoDescription() : defaultVideoColumns('fixed-player')), description);
        expect(store.error.value).toBe('');
        expect(store.columns.value).toHaveLength(columns.length);
        columns.forEach((column, index) => {
            expect(store.columns.value[index]).toMatchObject(column);
        });
        const ids = store.columns.value.flatMap((column) => ('id' in column ? [column.id] : []));
        expect(ids).toContain('keep-id');
        expect(new Set(ids).size).toBe(3);
        await nextTick();
        await nextTick();
        const saved = JSON.parse(storage.getItem(key) ?? 'null') as unknown;
        expect(saved).toEqual({ version: 2, columns: store.columns.value });
        expect(createColumnStore(key, () => [], description).columns.value).toEqual(store.columns.value);
        await nextTick();
        expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual(saved);
    });

    it('does not overwrite a newer edit with a queued migration writeback', async () => {
        const key = 'migration-race';
        storage.setItem(key, JSON.stringify({ version: 1, columns: [{ type: 'data', key: 'Old', expr: 'bv' }] }));
        const { createColumnStore } = await import('./columnStore');
        const { presetExpressionColumn } = await import('./presets');
        const store = createColumnStore(key, () => [presetExpressionColumn('time')]);
        const edited = [{ ...presetExpressionColumn('time'), key: 'New' }];
        store.columns.value = edited;
        await nextTick();
        await nextTick();
        expect(store.columns.value).toEqual(edited);
        expect(JSON.parse(storage.getItem(key) ?? 'null')).toEqual({ version: 2, columns: edited });
    });

    it('retains the original data and usable migrated columns if writeback fails', async () => {
        const key = 'migration-write-failure';
        const raw = JSON.stringify({ version: 1, columns: [{ type: 'bool', key: 'NF', expr: 'right_ce == 0' }] });
        storage.setItem(key, raw);
        const write = vi.spyOn(storage, 'setItem').mockImplementation(() => {
            throw new Error('storageUnavailable');
        });
        try {
            const { createColumnStore } = await import('./columnStore');
            const { presetExpressionColumn } = await import('./presets');
            const store = createColumnStore(key, () => [presetExpressionColumn('time')]);
            await nextTick();
            await nextTick();
            expect(store.columns.value).toEqual([{ id: expect.any(String), type: 'bool', key: 'NF', expr: 'right_ce == 0' }]);
            expect(store.error.value).toBe('storageUnavailable');
            expect(storage.getItem(key)).toBe(raw);
        } finally {
            write.mockRestore();
        }
    });
});
