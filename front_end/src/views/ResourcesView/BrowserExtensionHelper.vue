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
import { useI18n } from 'vue-i18n';

import { getDocsUrl } from '@/utils/docs';

const guideUrl = getDocsUrl('zh/guide/tools/browser-extension');

const i18nMessages = {
    'zh-cn': { local: {
        name: '浏览器扩展（元神助手）',
        description: '第三方浏览器扩展「元神助手」，不是网站官方产品，提供搜索用户、自动上传录像、成绩分析等辅助功能。',
        install: '安装：解压到一个固定文件夹，在浏览器扩展管理界面打开「开发者模式」，点「加载已解压的扩展程序」，选择刚才解压的文件夹。',
        project: '项目主页',
        releases: 'GitHub Releases',
        guide: '使用说明',
    } },
    en: { local: {
        name: 'Browser Extension (Yuanshen Helper)',
        description: 'Yuanshen Helper is a third-party browser extension, not an official site product. It provides player search, automatic replay upload and result analysis.',
        install: 'Install: extract it into a permanent folder, enable Developer mode on the browser extensions page, then choose "Load unpacked" and select that folder.',
        project: 'Project',
        releases: 'GitHub Releases',
        guide: 'Guide (Chinese)',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
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
