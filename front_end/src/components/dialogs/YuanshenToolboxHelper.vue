<template>
    <section class="text yuanshen-helper" aria-label="元神工具箱">
        <h3 class="text-medium">
            {{ t('local.title') }}
        </h3>
        <p>{{ t('local.description') }}</p>
        <p>{{ t('local.usage') }}</p>
        <p>
            <a class="link" href="https://github.com/Corday-nkusky/yuanshen-toolbox/releases/latest" target="_blank" rel="noopener noreferrer">
                {{ t('local.download') }}
            </a>
            &nbsp;
            <a class="link" :href="guideUrl" target="_blank" rel="noopener noreferrer">
                {{ t('local.guide') }}
            </a>
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { getDocsUrl } from '@/utils/docs';

const i18nMessages = {
    'zh-cn': { local: {
        title: '元神工具箱',
        description: '第三方工具：在本机读取元扫雷（EVF）与阿比特（AVF）录像，统计 PB 表与前端成绩，并把完成局上传到开源扫雷网。',
        usage: '放到元扫雷的 replay 目录上一级，双击运行即可，无需安装。',
        download: 'GitHub Releases',
        guide: '使用说明',
    } },
    en: { local: {
        title: 'Yuanshen Toolbox',
        description: 'A third-party tool that reads Metasweeper (EVF) and Arbiter (AVF) replays locally, builds your PB table and Top-5 results, and uploads finished games to Open Minesweeper.',
        usage: 'Place it one level above Metasweeper’s replay folder and run it. No installation required.',
        download: 'GitHub Releases',
        guide: 'Guide',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });

const guideUrl = computed(() => getDocsUrl('guide/tools/yuanshen-toolbox', locale.value));
</script>

<style scoped>
.yuanshen-helper {
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-align: left;
}
.yuanshen-helper h3,
.yuanshen-helper p {
    margin: 0;
}
</style>
