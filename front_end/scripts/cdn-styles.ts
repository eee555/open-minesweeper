import { readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

import { transform } from 'esbuild';
import type { Plugin } from 'vite';

import type { CdnStyle } from '../src/startup/cdnStyles.ts';

const require = createRequire(import.meta.url);

// Only the website build uses this plugin. Dev, component tests and the separate
// offline config continue to bundle the original CSS imports and fonts normally.
export function cdnStyles(): Plugin {
    const packages = [
        { name: 'element-plus', css: 'dist/index.css', font: undefined },
        { name: 'primeicons', css: 'primeicons.css', font: '16px primeicons' },
    ];
    const imports = new Set(packages.map((item) => `${item.name}/${item.css}`));
    const virtualId = '\0cdn-styles';
    let base: string;
    let assetsDir: string;
    let styles: CdnStyle[] = [];

    return {
        name: 'cdn-styles-with-local-fallback',
        apply: 'build',
        enforce: 'pre',
        configResolved(config) {
            ({ base, build: { assetsDir } } = config);
        },
        buildStart() {
            styles = packages.map((item) => {
                const packagePath = require.resolve(`${item.name}/package.json`);
                const metadata = JSON.parse(readFileSync(packagePath, 'utf8')) as { version: string };
                const root = dirname(packagePath);
                const prefix = posix.join(assetsDir, 'vendor', `${item.name}-${metadata.version}`);
                const cssFile = posix.join(prefix, item.css);
                // Preserve the upstream CSS and its relative font URLs byte for byte.
                this.emitFile({ type: 'asset', fileName: cssFile, source: readFileSync(join(root, item.css)) });
                if (item.font !== undefined && item.font !== '') {
                    for (const font of readdirSync(join(root, 'fonts'))) {
                        this.emitFile({ type: 'asset', fileName: posix.join(prefix, 'fonts', font), source: readFileSync(join(root, 'fonts', font)) });
                    }
                }
                return {
                    id: item.name,
                    cdn: `https://cdn.jsdelivr.net/npm/${item.name}@${metadata.version}/${item.css}`,
                    local: `${base}${cssFile}`,
                    font: item.font,
                };
            });
        },
        resolveId(source) {
            if (imports.has(source)) return { id: virtualId, moduleSideEffects: false };
        },
        load(id) {
            if (id === virtualId) return '';
        },
        transformIndexHtml: {
            order: 'post',
            async handler() {
                const source = readFileSync(fileURLToPath(new URL('../src/startup/cdnStyles.ts', import.meta.url)), 'utf8');
                const loader = await transform(source, { loader: 'ts', format: 'iife', globalName: '__cdnStyleLoader', target: 'es2015', minify: true });
                return [{
                    tag: 'script',
                    children: `${loader.code}\nwindow.__cdnStylesReady=__cdnStyleLoader.loadCdnStyles(${JSON.stringify(styles)});`,
                    // Keep charset and referrer metadata ahead of this script.
                    injectTo: 'head',
                }];
            },
        },
    };
}
