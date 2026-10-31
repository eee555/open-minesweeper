import 'element-plus/es/components/drawer/style/css';
import 'element-plus/es/components/pagination/style/css';
import 'element-plus/theme-chalk/dark/css-vars.css';
import '../src/styles/theme/index.css';
import '../src/styles/text.css';
import '../src/styles/checkbox-buttons.css';

import { createApp } from 'vue';

import App from './App.vue';

import i18n from '@/i18n';

i18n.global.locale.value = navigator.language.toLowerCase().startsWith('zh') ? 'zh-cn' : 'en';

// eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- 与网站和 Analyzer 入口一致：根 SFC 的类型由 vue-tsc 检查。
createApp(App).use(i18n).mount('#app');
