<template>
    <ElDialog :model-value="visible" class="analyzer-analysis-progress" width="340px" align-center :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" append-to-body>
        <template #header>
            <div class="analyzer-analysis-progress__title text text-regular">
                {{ t('local.title') }}
            </div>
        </template>
        <div class="analyzer-analysis-progress__body" role="status" aria-live="polite">
            <div class="analyzer-analysis-progress__label">
                {{ t(`local.${progress.key}`) }}
            </div>
            <div class="analyzer-analysis-progress__track" role="progressbar" :aria-valuenow="progress.percent" aria-valuemin="0" aria-valuemax="100" :aria-label="t('local.title')">
                <div class="analyzer-analysis-progress__fill" :style="{ width: `${progress.percent}%` }" />
            </div>
            <div class="analyzer-analysis-progress__meta text text-small">
                <span>{{ t('local.step', { current: progress.step, total: progress.steps }) }}</span>
                <span>{{ progress.percent }}%</span>
            </div>
        </div>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog } from 'element-plus';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { AnalysisProgressSnapshot } from './analysisProgress';

defineProps({
    visible: { type: Boolean, required: true },
    progress: { type: Object as PropType<AnalysisProgressSnapshot>, required: true },
});

const i18nMessages = {
    'zh-cn': { local: {
        title: '正在分析录像',
        trace: '生成鼠标轨迹',
        counter: '生成计数器事件',
        counters: '生成计数器采样',
        customEvents: '生成自定义事件',
        step: '第 {current} / {total} 步',
    } },
    en: { local: {
        title: 'Analyzing replay',
        trace: 'Building mouse trace',
        counter: 'Building counter events',
        counters: 'Building counter samples',
        customEvents: 'Building custom events',
        step: 'Step {current} of {total}',
    } },
    es: { local: {
        title: 'Analizando repetición',
        trace: 'Generando rastro del ratón',
        counter: 'Generando eventos de contador',
        counters: 'Generando muestras de contador',
        customEvents: 'Generando eventos personalizados',
        step: 'Paso {current} de {total}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.analyzer-analysis-progress__title {
    text-align: center;
}

.analyzer-analysis-progress__body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 4px 0 8px;
}

.analyzer-analysis-progress__label {
    color: var(--ui-text-color-primary);
}

.analyzer-analysis-progress__track {
    height: 6px;
    overflow: hidden;
    background: var(--ui-border-color);
}

.analyzer-analysis-progress__fill {
    height: 100%;
    background: var(--ui-color-primary);
    transition: width 0.1s linear;
}

.analyzer-analysis-progress__meta {
    display: flex;
    justify-content: space-between;
    color: var(--ui-text-color-primary);
    font-variant-numeric: tabular-nums;
}
</style>
