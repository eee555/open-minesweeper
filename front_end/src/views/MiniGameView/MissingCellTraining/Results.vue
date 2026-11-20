<template>
    <div class="missing-cell-results" data-cy="missing-cell-results">
        <figure>
            <div ref="plot" class="missing-cell-results-plot" role="img" :aria-label="t('local.roundTimes')" data-cy="missing-cell-round-times" @pointermove="hoverBar" @pointerleave="emit('hover', null)">
                <TransformGroup :size="size" :domain="domain" :padding="padding">
                    <Bar ref="bars" :values="seconds" :baseline="0" fill="var(--ui-color-primary)" />
                    <Axis direction="horizontal" :ticks="[]" :position="0" :tick-size="0" />
                </TransformGroup>
            </div>
        </figure>
        <figure>
            <div role="img" :aria-label="t('local.totalTime')" data-cy="missing-cell-time-stack">
                <StackBar :data="segments" height="24px" :legend="false" :tooltip="false" @item-enter="emit('hover', $event)" @item-leave="emit('hover', null)" />
            </div>
        </figure>
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-plots/style.css';

import { Axis, Bar, TransformGroup } from '@putianyi888/vue3-plots';
import { useElementSize } from '@vueuse/core';
import { computed, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import StackBar from '@/components/visualization/StackBar/App.vue';

const props = defineProps({ timesMs: { type: Array as PropType<readonly number[]>, required: true } });
const emit = defineEmits<{ hover: [index: number | null] }>();
const bars = useTemplateRef<InstanceType<typeof Bar>>('bars');
const plot = useTemplateRef<HTMLDivElement>('plot');
const { width } = useElementSize(plot);
const size = computed(() => ({ width: Math.max(1, width.value), height: 160 }));
const padding = { top: 4, right: 0, bottom: 0, left: 0 };
const seconds = computed(() => props.timesMs.map((time) => time / 1000));
const domain = computed(() => ({ xMin: 0, xMax: props.timesMs.length, yMin: 0, yMax: Math.max(0.001, ...seconds.value) * 1.1 }));
const colors = ['primary', 'success', 'warning', 'danger', 'info'];
const segments = computed(() => props.timesMs.map((time, index) => ({
    name: t('local.round', { round: index + 1 }), value: time / 1000, color: `var(--ui-color-${colors[index % colors.length]})`,
})));

function hoverBar(event: PointerEvent) {
    const rect = plot.value?.getBoundingClientRect();
    if (rect === undefined) return;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = bars.value?.bars.find((bar) => x >= bar.x && x <= bar.x + bar.width && y >= bar.y && y <= bar.y + bar.height);
    emit('hover', hit?.index ?? null);
}

const i18nMessages = {
    'zh-cn': { local: {
        roundTimes: '每局用时（秒）',
        totalTime: '总用时构成',
        round: '第 {round} 局',
    } },
    en: { local: {
        roundTimes: 'Time per board (seconds)',
        totalTime: 'Total time breakdown',
        round: 'Board {round}',
    } },
    es: { local: {
        roundTimes: 'Tiempo por tablero (segundos)',
        totalTime: 'Desglose total del tiempo',
        round: 'Tablero {round}',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.missing-cell-results {
    display: grid;
    gap: 0.75rem;
    width: 100%;
    max-width: 52rem;
    min-width: 0;
    margin-inline: auto;
}

figure {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
    margin: 0;
}

.missing-cell-results-plot {
    position: relative;
    height: 160px;
}

.missing-cell-results-plot :deep(.plot-bar rect:nth-child(5n + 2)) {
    fill: var(--ui-color-success);
}

.missing-cell-results-plot :deep(.plot-bar rect:nth-child(5n + 3)) {
    fill: var(--ui-color-warning);
}

.missing-cell-results-plot :deep(.plot-bar rect:nth-child(5n + 4)) {
    fill: var(--ui-color-danger);
}

.missing-cell-results-plot :deep(.plot-bar rect:nth-child(5n + 5)) {
    fill: var(--ui-color-info);
}
</style>
