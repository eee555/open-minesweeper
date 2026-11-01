import type { Plugin, PluginOption, UserConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

// SVG font fragments remain external in Vite. Keep the upstream icon classes with an inline WOFF2 source.
const offlineStyles: UserConfig['css'] = { postcss: { plugins: [{
    postcssPlugin: 'offline-primeicons-font',
    AtRule: {
        'font-face': (rule) => {
            if (rule.nodes?.some((node) => node.type === 'decl' && node.prop === 'font-family' && node.value.toLowerCase().includes('primeicons')) !== true) return;
            rule.walkDecls('src', (declaration) => {
                declaration.value = 'url("./fonts/primeicons.woff2") format("woff2")';
            });
        },
    },
}] } };

export function getOfflineStyles(): UserConfig['css'] {
    return offlineStyles;
}

function isBundlePlugin(option: PluginOption): option is Plugin {
    return option !== null && typeof option === 'object' && 'generateBundle' in option;
}

/** Collect dependency licenses before the single-file plugin removes JavaScript chunks. */
export function singleFileWithLicenses(): Plugin {
    const plugin = viteSingleFile();
    if (!isBundlePlugin(plugin)) throw new Error('Single-file plugin object is unavailable');
    const inlineBundle = plugin.generateBundle;
    if (typeof inlineBundle === 'function') plugin.generateBundle = { order: 'post', handler: inlineBundle };
    else if (inlineBundle && typeof inlineBundle.handler === 'function') plugin.generateBundle = { ...inlineBundle, order: 'post' };
    else throw new Error('Single-file generateBundle hook is unavailable');
    return plugin;
}
