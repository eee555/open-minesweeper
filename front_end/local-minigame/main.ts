import 'element-plus/dist/index.css';
import 'element-plus/theme-chalk/dark/css-vars.css';
import '../src/styles/theme/index.css';
import '../src/styles/text.css';
import '../src/styles/checkbox-buttons.css';

import { useLocalStorage } from '@vueuse/core';
import { createApp, watch } from 'vue';

import App from './App.vue';

import i18n from '@/i18n';
import { resolveContentLanguage } from '@/i18n/language';

const savedLanguage = useLocalStorage('offline-minigame-language', navigator.language);
i18n.global.locale.value = resolveContentLanguage(savedLanguage.value);
watch(i18n.global.locale, (language) => {
    savedLanguage.value = language;
    document.title = language === 'es'
        ? 'OpenMinesweeper — Minijuegos sin conexión'
        : language === 'zh-cn' ? '开源扫雷网 — 离线小游戏' : 'OpenMinesweeper Minigames — Offline';
}, { immediate: true });

// eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- 与网站和 Analyzer 入口一致：根 SFC 的类型由 vue-tsc 检查。
createApp(App).use(i18n).mount('#app');
