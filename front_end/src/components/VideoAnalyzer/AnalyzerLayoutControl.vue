<template>
    <BoardSettingsControl ref="control" class="video-analyzer-board__layout-control" :label="t('local.layout')" icon="pi pi-table">
        <template #settings>
            <select v-model="selectedLayout" class="video-analyzer-view__layout-select" :aria-label="t('local.layout')" @change="control?.close()">
                <option value="auto">
                    {{ t('local.auto') }}
                </option>
                <option v-for="layout in layouts" :key="layout" :value="layout">
                    {{ t(`local.${layout}`) }}
                </option>
            </select>
        </template>
    </BoardSettingsControl>
</template>

<script setup lang="ts">
import { useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BoardSettingsControl from './BoardSettingsControl.vue';
import { layouts } from './config';
import type { AnalyzerLayout } from './config';

const selectedLayout = defineModel<AnalyzerLayout | 'auto'>({ required: true });
const control = useTemplateRef<{ close: () => void }>('control');
const i18nMessages = {
    'zh-cn': { local: {
        layout: '布局',
        auto: '自动',
        'counter-left': '计数器居左',
        'counter-right': '计数器居右',
        'counter-top': '计数器置顶',
        'board-top': '棋盘置顶',
    } },
    en: { local: {
        layout: 'Layout',
        auto: 'Auto',
        'counter-left': 'Counters on the left',
        'counter-right': 'Counters on the right',
        'counter-top': 'Counters on top',
        'board-top': 'Board on top',
    } },
    es: { local: {
        layout: 'Disposición',
        auto: 'Automático',
        'counter-left': 'Contadores a la izquierda',
        'counter-right': 'Contadores a la derecha',
        'counter-top': 'Contadores arriba',
        'board-top': 'Tablero arriba',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-analyzer-board__layout-control :deep(.board-settings-control__handle) {
    width: 28px;
    height: 28px;
    padding: 0;
    border-right: 1px solid var(--ui-border-color);
}
.video-analyzer-board__layout-control :deep(.board-settings-control__handle > i) {
    font-size: 14px;
}
.video-analyzer-board__layout-control :deep(.board-settings-control__settings) {
    width: 210px;
}
.video-analyzer-view__layout-select {
    min-width: 0;
    padding: 4px 8px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}
</style>
