import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import removeAttr from 'remove-attr';
import { defineConfig, loadEnv } from 'vite';
import viteCompression from 'vite-plugin-compression';
import wasm from 'vite-plugin-wasm';
// import vueDevTools from 'vite-plugin-vue-devtools'

import { cdnStyles } from './scripts/cdn-styles.ts';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    process.env = { ...process.env, ...loadEnv(mode, process.cwd(), '') };
    // 真**坑爹。vite的依赖open，10.0.1修复了这个问题。但目前vite还未更新其版本
    process.env.SYSTEMROOT = process.env.SystemRoot ?? 'C://Windows';

    return {
        plugins: [
            process.env.VITE_CDN_STYLES !== 'false' ? cdnStyles() : null,
            vue(),
            wasm(),
            // vueDevTools(),
            viteCompression({
                algorithm: 'gzip', // Or 'brotliCompress' for Brotli compression
                ext: '.gz', // Add a .gz extension to the compressed files
                filter: /\.(js|mjs|json|css|html|wasm)$/i,
                threshold: 1024, // Minimum file size in bytes to compress
            }),
            process.env.NODE_ENV === 'production'
                ? removeAttr({
                    extensions: ['vue'],
                    attributes: ['data-cy'],
                })
                : null,
        ],
        resolve: {
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url)),
                '@cy': fileURLToPath(new URL('./cypress', import.meta.url)),
            },
        },
        server: {
            open: false,
            port: 8080,
            host: process.env.Host ?? 'localhost',
        },
        build: {
            target: 'es2015',
        },
    // esbuild: {
    //   supported: {
    //     'top-level-await': true //browsers can handle top-level-await features
    //   },
    // },
    // build: {
    //   minify: false,
    // }
    // base: baseURL,
    };
});
