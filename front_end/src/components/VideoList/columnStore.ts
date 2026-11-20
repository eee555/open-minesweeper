import { useLocalStorage } from '@vueuse/core';
import { computed, shallowRef } from 'vue';
import type { ComputedRef, WritableComputedRef } from 'vue';

import { isVideoColumns } from './columns';
import type { VideoColumn, VideoColumnScope, VideoDescriptionItem } from './columns';
import { defaultVideoColumns, defaultVideoDescription } from './presets';

/** Validate before using cached JSON; invalid storage stays intact until an explicit edit. */
export interface ColumnStore<Item extends VideoColumn = VideoColumn> {
    columns: WritableComputedRef<Item[]>;
    error: ComputedRef<string>;
}

export function createColumnStore<Item extends VideoColumn>(key: string, defaults: () => Item[], description = false): ColumnStore<Item> {
    const diagnostic = shallowRef('');
    const stored = useLocalStorage<unknown>(key, null, {
        writeDefaults: false,
        serializer: {
            read: (text: string): unknown => {
                try {
                    return JSON.parse(text) as unknown;
                } catch {
                    diagnostic.value = 'invalidConfig'; return null;
                }
            },
            write: (value: unknown) => JSON.stringify(value) ?? 'null',
        },
        onError: () => {
            diagnostic.value = 'storageUnavailable';
        },
    });
    const fallback = computed(defaults);
    const columns = computed<Item[]>({
        get: () => {
            if (stored.value === null) return fallback.value;
            return isVideoColumns(stored.value, description) ? stored.value as Item[] : fallback.value;
        },
        set: (value) => {
            if (!isVideoColumns(value, description)) return;
            stored.value = value.map((column) => ({ ...column }));
            diagnostic.value = '';
        },
    });
    const error = computed(() => (stored.value !== null && !isVideoColumns(stored.value, description) ? 'invalidConfig' : diagnostic.value));
    return { columns, error };
}

const fixed = createColumnStore('video-list-columns-v1:fixed-player', () => defaultVideoColumns('fixed-player'));
const mixed = createColumnStore('video-list-columns-v1:mixed-players', () => defaultVideoColumns('mixed-players'));
export const videoDescriptionStore = createColumnStore<VideoDescriptionItem>('video-abstract-description-v1', defaultVideoDescription, true);

export function videoColumnStore(scope: VideoColumnScope): ColumnStore {
    return scope === 'fixed-player' ? fixed : mixed;
}
