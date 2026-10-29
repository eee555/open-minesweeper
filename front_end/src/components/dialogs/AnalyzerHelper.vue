<template>
    <section class="analyzer-helper text" aria-label="OpenMinesweeper Video Analyzer">
        <h3 class="text-medium">
            OpenMinesweeper Video Analyzer
        </h3>
        <p>{{ t('local.description') }}</p>
        <p>{{ t('local.openOffline') }}</p>
        <BaseTable>
            <template #head>
                <tr>
                    <th scope="col">
                        {{ t('software.version') }}
                    </th>
                    <th scope="col">
                        {{ t('software.releaseDate') }}
                    </th>
                    <th scope="col">
                        {{ t('software.download') }}
                    </th>
                </tr>
            </template>
            <tr v-for="row in tableData" :key="row.version">
                <td>v{{ row.version }}</td>
                <td><time :datetime="row.date">{{ row.date }}</time></td>
                <td><a class="link" :href="`${downloadBaseUrl}${row.filename}`" :download="row.filename">OpenMS</a></td>
            </tr>
        </BaseTable>
    </section>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';

const downloadBaseUrl = `${import.meta.env.BASE_URL}assets/`;
// 发布历史手动维护：新版本提供下载后，添加版本、日期及实际 ZIP 文件名；不读取 version.json 自动更新。
const tableData = [
    { version: '0.2.0', date: '2026-10-19', filename: 'OpenMinesweeperVideoAnalyzer-0.2.0.zip' },
    { version: '0.1.3', date: '2026-10-18', filename: 'OpenMinesweeperVideoAnalyzer-0.1.3.zip' },
    { version: '0.1.2', date: '2026-10-13', filename: 'OpenMinesweeperVideoAnalyzer-0.1.2.zip' },
];

const i18nMessages = {
    'zh-cn': { local: {
        description: '开源扫雷网的离线录像分析器，支持 EVF / AVF / MVF / RMV 格式。',
        openOffline: '解压后用 Chrome 或 Edge 打开 index.html，即可选择本地录像进行分析，无需网络连接。',
    } },
    en: { local: {
        description: 'Open Minesweeper’s offline replay analyzer, supporting EVF / AVF / MVF / RMV files.',
        openOffline: 'Extract the ZIP and open index.html in Chrome or Edge to analyze local replays. No internet connection is required.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.analyzer-helper {
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-align: left;
}
.analyzer-helper h3,
.analyzer-helper p {
    margin: 0;
}
</style>
