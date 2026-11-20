import { useLocalStorage } from '@vueuse/core';
import { v4 as uuidv4 } from 'uuid';
import { computed, nextTick, shallowRef, watch } from 'vue';
import type { ComputedRef, WritableComputedRef } from 'vue';

import { isFixedColumnType, isVideoColumns } from './columns';
import type { VideoColumn, VideoColumnScope, VideoDescriptionItem } from './columns';
import { defaultVideoColumns, defaultVideoDescription } from './presets';

const CONFIG_VERSION = 2;

/** Validate before using cached JSON; invalid storage stays intact until an explicit edit. */
export interface ColumnStore<Item extends VideoColumn = VideoColumn> {
    columns: WritableComputedRef<Item[]>;
    error: ComputedRef<string>;
}

export function createColumnStore<Item extends VideoColumn>(key: string, defaults: () => Item[], description = false): ColumnStore<Item> {
    const diagnostic = shallowRef('');
    const migrationPending = shallowRef(false);
    const stored = useLocalStorage<Item[] | null>(key, null, {
        writeDefaults: false,
        serializer: {
            read: (text: string): Item[] | null => {
                migrationPending.value = false;
                try {
                    const config: unknown = JSON.parse(text);
                    if (typeof config !== 'object' || config === null || !('version' in config) || !('columns' in config)) throw new Error('invalidConfig');
                    let { columns } = config;
                    if (config.version === 1 && Array.isArray(columns)) {
                        columns = columns.map((item: unknown) => {
                            if (typeof item !== 'object' || item === null || !('type' in item) || typeof item.type !== 'string' || isFixedColumnType(item.type) || 'id' in item) return item;
                            return { ...item, id: uuidv4() };
                        });
                    } else if (config.version !== CONFIG_VERSION) throw new Error('invalidConfig');
                    if (!isVideoColumns(columns, description)) throw new Error('invalidConfig');
                    migrationPending.value = config.version !== CONFIG_VERSION;
                    diagnostic.value = '';
                    return columns as Item[];
                } catch {
                    diagnostic.value = 'invalidConfig'; return null;
                }
            },
            write: (columns: Item[] | null) => JSON.stringify(columns === null ? null : { version: CONFIG_VERSION, columns }),
        },
        onError: () => {
            diagnostic.value = 'storageUnavailable';
        },
    });
    watch([stored, migrationPending], async ([columns, pending]) => {
        if (!pending || columns === null) return;
        migrationPending.value = false;
        // Storage events pause VueUse's writer until the next tick.
        await nextTick();
        if (stored.value === columns) stored.value = [...columns];
    }, { immediate: true });
    const fallback = computed(defaults);
    const columns = computed<Item[]>({
        get: () => stored.value ?? fallback.value,
        set: (value) => {
            if (!isVideoColumns(value, description)) return;
            stored.value = value.map((column) => ({ ...column }));
            diagnostic.value = '';
        },
    });
    const error = computed(() => diagnostic.value);
    return { columns, error };
}

const fixed = createColumnStore('video-list-columns:fixed-player', () => defaultVideoColumns('fixed-player'));
const mixed = createColumnStore('video-list-columns:mixed-players', () => defaultVideoColumns('mixed-players'));
export const videoDescriptionStore = createColumnStore<VideoDescriptionItem>('video-abstract-description', defaultVideoDescription, true);

export function videoColumnStore(scope: VideoColumnScope): ColumnStore {
    return scope === 'fixed-player' ? fixed : mixed;
}
