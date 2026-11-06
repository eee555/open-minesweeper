import './setup.js';
import { ArrowLeft, ArrowRight, Key, Lock, Message, QuestionFilled, User } from '@element-plus/icons-vue';
import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';
import type { AxiosInstance } from 'axios';
import PrimeVue from 'primevue/config';
import { createApp } from 'vue';

import App from './App.vue';
import $axios from './http';
import router from './router';
import { pinia } from './store/create';

import i18n from '@/i18n';

updateStartupStatus('2/3 正在初始化应用…', '2/3 Initializing application…');

// eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- 根 .vue 组件在 typescript-eslint 中可能被解析为 error type；vue-tsc 已负责 SFC 类型校验。
const app = createApp(App);

if (import.meta.env.DEV) {
    app.config.warnHandler = (msg, instance, trace) => {
    // Suppress only the "extraneous non-props attributes" warning
        if (msg.includes('Extraneous non-props attributes (data-cy)')) {
            return;
        }
        console.warn(msg, trace);
    };
}

app.config.globalProperties.$axios = $axios;

// Transitional registry for bare tags and input prefix-icon strings.
const globalIcons = { ArrowLeft, ArrowRight, Key, Lock, Message, QuestionFilled, User };
for (const [key, component] of Object.entries(globalIcons)) {
    app.component(key, component);
}

const myTheme = definePreset(Aura, {
    components: {
        datatable: {
            // bodyCell: {
            //     padding: '1px 5px',
            // },
            // headerCell: {
            //     padding: '1px 5px',
            // },
        },
    },
});

app.use(PrimeVue, {
    theme: {
        preset: myTheme,
        options: {
            darkModeSelector: '.dark',
        },
    },
    autoImport: false,
});
app.use(pinia).use(router).use(i18n);
updateStartupStatus('3/3 正在准备页面…', '3/3 Preparing page…');

// Keep the HTML placeholder until the route and CDN (or local fallback) styles are ready.
void Promise.all([router.isReady(), window.__cdnStylesReady]).then(() => {
    app.mount('#app');
}).catch((error: unknown) => {
    updateStartupStatus('页面加载失败，请刷新重试。', 'Failed to load the page. Please refresh to try again.');
    document.querySelector('#startup-loading progress')?.setAttribute('hidden', '');
    console.error(error);
});

function updateStartupStatus(zh: string, en: string) {
    const label = document.querySelector('#startup-loading-label .startup-loading-status');
    const chinese = label?.querySelector('[lang="zh-CN"]');
    const english = label?.querySelector('[lang="en"]');
    if (chinese) chinese.textContent = zh;
    if (english) english.textContent = en;
}

declare module '@vue/runtime-core' {
    interface ComponentCustomProperties {
        $axios: AxiosInstance;
    }
}

// cloc-1.94.exe .\开源扫雷网 -exclude-dir=node_modules
// "ms-toollib": "file:../../ms_toollib/wasm/pkg",

// git remote set-url origin https://gitee.com/ee55/saolei_website.git
// git push -f origin main
