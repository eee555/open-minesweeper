/* eslint-disable import-x/no-named-as-default */
import path from 'path';
import { fileURLToPath } from 'url';

import { defineConfig } from 'cypress';
import cypressSplit from 'cypress-split';
import vitePreprocessor from 'cypress-vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
    defaultBrowser: 'chrome',
    e2e: {
        baseUrl: 'http://localhost:8080',
        setupNodeEvents(on, config) {
            on('before:browser:launch', (browser, launchOptions) => {
                if (browser.name === 'chrome') {
                    launchOptions.args.push('--accept-lang=zh-CN');
                }
                return launchOptions;
            });
            on('file:preprocessor', vitePreprocessor({
                configFile: path.resolve(__dirname, 'vite.config.ts'),
            }));
            cypressSplit(on, config);
            return config;
        },
    },

    component: {
        specPattern: ['src/**/*.cy.{js,jsx,ts,tsx}', 'cypress/component/**/*.cy.{js,jsx,ts,tsx}'],
        setupNodeEvents(on, config) {
            cypressSplit(on, config);
            return config;
        },
        devServer: {
            framework: 'vue',
            bundler: 'vite',
        },
    },
    chromeWebSecurity: false,
    watchForFileChanges: false,
});
