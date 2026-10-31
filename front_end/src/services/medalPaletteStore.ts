import { ref } from 'vue';

import { defaultMedalPalette, loadMedalPalette, parseMedalPalette, saveMedalPalette } from './medalPalette';
import type { MedalPaletteConfig, PaletteStorage } from './medalPalette';

function browserStorage(): PaletteStorage | undefined {
    try {
        return globalThis.localStorage;
    } catch {
        return undefined;
    }
}
const loaded = loadMedalPalette(browserStorage());
export const medalPalette = ref<MedalPaletteConfig>(loaded.config);
export const medalPaletteStorageStatus = ref<string>(loaded.status);

export function updateMedalPalette(config: MedalPaletteConfig): void {
    // Validate before replacing the active configuration, including imported files.
    const next = parseMedalPalette(JSON.stringify(config));
    medalPalette.value = next;
    medalPaletteStorageStatus.value = saveMedalPalette(browserStorage(), next) ? 'saved' : 'unavailable';
}

export function resetMedalPalette(): void {
    updateMedalPalette(defaultMedalPalette());
}

if (typeof window !== 'undefined') {
    window.addEventListener('storage', (event) => {
        if (event.key !== null && event.key !== 'medal-appearance-colors-v1') return;
        const updated = loadMedalPalette(browserStorage());
        medalPalette.value = updated.config;
        medalPaletteStorageStatus.value = updated.status;
    });
}
