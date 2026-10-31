import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig, normalizePath } from 'vite';
import type { Plugin } from 'vite';

import { getOfflineStyles, singleFileWithLicenses } from './scripts/offline-build';

const websiteSourceRoot = normalizePath(fileURLToPath(new URL('./src/', import.meta.url)));
const isolatedMinigame: Plugin = {
    name: 'isolated-offline-minigame',
    generateBundle() {
        const forbidden = [...this.getModuleIds()].filter((id) => {
            const normalized = normalizePath(id);
            return (normalized.startsWith(websiteSourceRoot) && (/^(?:(?:http|bootstrap|setup)\.ts(?:$|\?)|(?:store|router)\/)/u).test(normalized.slice(websiteSourceRoot.length))) || normalized.includes('/ms-toollib/');
        });
        if (forbidden.length > 0) this.error(`Offline minigame imports website or replay modules: ${forbidden.join(', ')}`);
    },
};

export default defineConfig({
    root: fileURLToPath(new URL('./local-minigame', import.meta.url)),
    base: './',
    publicDir: false,
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    css: getOfflineStyles(),
    plugins: [vue(), isolatedMinigame, singleFileWithLicenses()],
    build: { target: 'es2015', outDir: '../dist-offline-minigame', emptyOutDir: true, assetsInlineLimit: Infinity, modulePreload: false, license: { fileName: 'THIRD_PARTY_LICENSES.json' } },
});
