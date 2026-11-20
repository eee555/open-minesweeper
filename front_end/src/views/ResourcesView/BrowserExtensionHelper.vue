<template>
    <section class="browser-extension-helper text" :aria-label="t('local.name')">
        <p>{{ t('local.description') }}</p>
        <p>{{ t('local.install') }}</p>
        <p class="browser-extension-links">
            <a class="link" href="https://github.com/LockhartANR/yuanshen-helper" target="_blank" rel="noopener noreferrer">{{ t('local.project') }}</a>
            <a class="link" href="https://github.com/LockhartANR/yuanshen-helper/releases/latest" target="_blank" rel="noopener noreferrer">{{ t('local.releases') }}</a>
            <a class="link" :href="guideUrl" target="_blank" rel="noopener noreferrer">{{ t('local.guide') }}</a>
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { resolveContentLanguage } from '@/i18n/language';
import { getDocsUrl } from '@/utils/docs';

const i18nMessages = {
    'zh-cn': { local: {
        name: '浏览器扩展（元神助手）',
        description: '第三方浏览器扩展「元神助手」支持搜索用户、自动上传录像、成绩分析和全站自定义排行榜。',
        install: '安装：解压到一个固定文件夹，在浏览器扩展管理界面打开「开发者模式」，点「加载已解压的扩展程序」，选择刚才解压的文件夹。',
        project: '项目主页',
        releases: 'GitHub Releases',
        guide: '使用说明',
    } },
    en: { local: {
        name: 'Browser Extension (Yuanshen Helper)',
        description: 'Yuanshen Helper is a third-party browser extension for player search, automatic replay upload, results analysis and custom site-wide rankings.',
        install: 'Install: extract it into a permanent folder, enable Developer mode on the browser extensions page, then choose "Load unpacked" and select that folder.',
        project: 'Project',
        releases: 'GitHub Releases',
        guide: 'Guide',
    } },
    es: { local: {
        name: 'Extensión de navegador (Yuanshen Helper)',
        description: 'Yuanshen Helper es una extensión de navegador de terceros para buscar jugadores, subir repeticiones automáticamente, analizar resultados y crear clasificaciones personalizadas del sitio.',
        install: 'Instalación: extrae el archivo en una carpeta permanente, activa el modo Desarrollador en la página de extensiones del navegador, luego elige "Cargar desempaquetado" y selecciona esa carpeta.',
        project: 'Proyecto',
        releases: 'Versiones en GitHub',
        guide: 'Guía de uso',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
const guideUrl = computed(() => {
    const language = resolveContentLanguage(locale.value);
    return getDocsUrl(`${language === 'zh-cn' ? 'zh' : language}/guide/tools/browser-extension`);
});
</script>

<style scoped>
.browser-extension-helper {
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-align: left;
}
.browser-extension-helper p {
    margin: 0;
}
.browser-extension-links {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
</style>
