<template>
    <ChartTooltip :pointer="pointer">
        <div ref="plot" class="reaction-chart" role="img" :aria-label="label" @pointermove="hoverBar" @pointerleave="leave">
            <TransformGroup :domain="domain" :size="size" :padding="padding">
                <Bar ref="bars" :values="values" :baseline="0" fill="var(--ui-color-success)" :gap="0.12" />
                <Bar v-if="parts" :values="parts" :baseline="0" fill="var(--ui-color-primary)" :gap="0.12" />
                <Axis direction="horizontal" :ticks="ticks" :position="0">
                    <template #tick="{ tick }">
                        {{ labels[Math.floor(tick)] }}
                    </template>
                </Axis>
            </TransformGroup>
            <svg class="reaction-chart-highlights" :width="size.width" :height="size.height" aria-hidden="true">
                <rect v-for="bar in highlightedBars" :key="bar.index" :x="bar.x" :y="bar.y" :width="bar.width" :height="Math.max(1, bar.height)" :data-index="bar.index" data-cy="reaction-bar-highlight" />
            </svg>
        </div>
        <template #content>
            <div class="reaction-chart-tooltip" data-cy="reaction-chart-tooltip">
                {{ tooltipText }}
            </div>
        </template>
    </ChartTooltip>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-plots/style.css';

import { Axis, Bar, TransformGroup } from '@putianyi888/vue3-plots';
import { useElementSize } from '@vueuse/core';
import { computed, ref, shallowRef, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';

import ChartTooltip from './ChartTooltip.vue';

const props = defineProps({
    values: { type: Array as PropType<number[]>, required: true },
    parts: { type: Array as PropType<number[]>, default: undefined },
    labels: { type: Array as PropType<string[]>, required: true },
    tooltips: { type: Array as PropType<string[]>, required: true },
    label: { type: String, required: true },
    highlighted: { type: Array as PropType<number[]>, default: () => [] },
});
const emit = defineEmits<{ hover: [index: number | null] }>();
const plot = useTemplateRef<HTMLDivElement>('plot');
const bars = useTemplateRef<InstanceType<typeof Bar>>('bars');
const { width } = useElementSize(plot);
const size = computed(() => ({ width: Math.max(1, width.value), height: 180 }));
const padding = { top: 8, right: 8, bottom: 36, left: 8 };
const domain = computed(() => ({ xMin: 0, xMax: Math.max(1, props.values.length), yMin: 0, yMax: Math.max(1, ...props.values) * 1.1 }));
const ticks = computed(() => props.values.flatMap((_value, index) => (index % Math.max(1, Math.ceil(props.values.length / Math.max(1, Math.floor(width.value / 90)))) === 0 ? [index + 0.5] : [])));
const hoveredIndex = ref<number | null>(null);
const pointer = shallowRef<PointerEvent | null>(null);
const tooltipText = computed(() => (hoveredIndex.value === null ? '' : props.tooltips[hoveredIndex.value] ?? ''));
const highlightedBars = computed(() => bars.value?.bars.filter((bar) => props.highlighted.includes(bar.index)) ?? []);
watch(hoveredIndex, (index) => {
    emit('hover', index);
}, { flush: 'sync' });
watch(() => props.values, leave);
function leave() {
    hoveredIndex.value = null;
    pointer.value = null;
}
function hoverBar(event: PointerEvent) {
    const rect = plot.value?.getBoundingClientRect();
    if (rect === undefined) return;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = bars.value?.bars.find((bar) => x >= bar.x && x <= bar.x + bar.width && y >= bar.y && y <= bar.y + Math.max(1, bar.height));
    if (hit === undefined) {
        leave();
        return;
    }
    hoveredIndex.value = hit.index;
    pointer.value = event;
}
</script>

<style scoped>
.reaction-chart {
    position: relative;
    min-width: 0;
    height: 180px;
}

.reaction-chart-tooltip {
    white-space: pre-line;
}

.reaction-chart-highlights {
    position: absolute;
    inset: 0;
    pointer-events: none;
    fill: none;
    stroke: var(--ui-text-color-primary);
    stroke-width: 2;
}
</style>
