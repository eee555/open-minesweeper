<template>
    <ChartTooltip :pointer="pointer">
        <div class="minigame-speed-labels text text-small">
            <span class="mouse-label">{{ t('local.mouseSpeed') }}</span>
            <span v-if="clicks" class="click-label">{{ t('local.clickSpeed') }}</span>
        </div>
        <div ref="plot" class="minigame-analysis-plot" role="img" :aria-label="t('local.mouseSpeed')" data-cy="minigame-speed-plot" @pointermove="hoverAt" @pointerleave="leave">
            <TransformGroup :domain="domain" :size="size" :padding="padding">
                <Line class="minigame-mouse-speed" :points="mousePoints" stroke-color="var(--ui-color-primary)" :stroke-width="1.5" />
                <Line v-if="clicks" class="minigame-click-speed" :points="clickPoints" :domain="clickDomain" stroke-color="var(--ui-color-success)" :stroke-width="1.5" />
                <Axis direction="horizontal" :ticks="xTicks" :position="0">
                    <template #tick="{ tick }">
                        {{ formatTick(tick / 1000) }}
                    </template>
                </Axis>
                <template v-if="clicks">
                    <Axis class="minigame-speed-axis-left" direction="vertical" :ticks="getNiceTicks(0, domain.yMax, 4)" :position="0" :offset="-6" text-anchor="end" />
                    <Axis class="minigame-speed-axis-right" direction="vertical" :domain="clickDomain" :ticks="getNiceTicks(0, clickDomain.yMax, 4)" :position="domain.xMax" :offset="6" text-anchor="start" />
                </template>
                <template v-if="markedSample">
                    <Line class="minigame-speed-marker" :points="[{ x: markedSample.timeMs, y: 0 }, { x: markedSample.timeMs, y: domain.yMax }]" stroke-color="var(--ui-color-warning)" :stroke-width="1" />
                    <Scatter :points="[{ x: markedSample.timeMs, y: markedSample.mouseSpeed }]" :radius="3" fill-color="var(--ui-color-primary)" />
                    <Scatter v-if="clicks" :domain="clickDomain" :points="[{ x: markedSample.timeMs, y: markedSample.clickSpeed }]" :radius="3" fill-color="var(--ui-color-success)" />
                </template>
            </TransformGroup>
        </div>
        <template #content>
            <template v-if="hovered">
                <div>{{ (hovered.timeMs / 1000).toFixed(3) }} s</div>
                <div>{{ t('local.mouseSpeed') }}: {{ hovered.mouseSpeed.toFixed(3) }}</div>
                <div v-if="clicks">
                    {{ t('local.clickSpeed') }}: {{ hovered.clickSpeed.toFixed(3) }}
                </div>
            </template>
        </template>
    </ChartTooltip>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-plots/style.css';

import { Axis, formatTick, getNiceTicks, getPlotArea, Line, Scatter, TransformGroup } from '@putianyi888/vue3-plots';
import { useElementSize } from '@vueuse/core';
import { bisector } from 'd3-array';
import { computed, shallowRef, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import ChartTooltip from './ChartTooltip.vue';

import type { ReplayPosition } from '@/utils/minigame/replay';
import type { SpeedSample } from '@/utils/minigame/replayAnalysis';

const props = defineProps({
    samples: { type: Array as PropType<SpeedSample[]>, required: true },
    durationMs: { type: Number, required: true },
    clicks: { type: Boolean, default: false },
    markerMs: { type: Number as PropType<number | null>, default: null },
});
const emit = defineEmits<{ preview: [position: ReplayPosition | null] }>();
const plot = useTemplateRef<HTMLDivElement>('plot');
const { width } = useElementSize(plot);
const size = computed(() => ({ width: Math.max(1, width.value), height: 180 }));
const padding = computed(() => ({ top: 8, right: props.clicks ? 48 : 8, bottom: 24, left: props.clicks ? 48 : 8 }));
const domain = computed(() => ({ xMin: 0, xMax: Math.max(1, props.durationMs), yMin: 0, yMax: props.samples.reduce((maximum, sample) => Math.max(maximum, sample.mouseSpeed), 1) * 1.1 }));
const clickDomain = computed(() => ({ ...domain.value, yMax: props.samples.reduce((maximum, sample) => Math.max(maximum, sample.clickSpeed), 1) * 1.1 }));
const mousePoints = computed(() => props.samples.map((sample) => ({ x: sample.timeMs, y: sample.mouseSpeed })));
const clickPoints = computed(() => props.samples.map((sample) => ({ x: sample.timeMs, y: sample.clickSpeed })));
const xTicks = computed(() => getNiceTicks(0, domain.value.xMax, Math.max(2, Math.floor(width.value / 100))));
const hovered = shallowRef<SpeedSample | null>(null);
const pointer = shallowRef<PointerEvent | null>(null);
const sampleTime = bisector<SpeedSample, number>((sample) => sample.timeMs);
const markedSample = computed(() => (props.markerMs === null ? hovered.value : props.samples[sampleTime.center(props.samples, props.markerMs)]));
function leave() {
    hovered.value = null;
    pointer.value = null;
    emit('preview', null);
}
function hoverAt(event: PointerEvent) {
    const rect = plot.value?.getBoundingClientRect();
    const area = getPlotArea(size.value, padding.value);
    if (rect === undefined || event.clientX < rect.left + area.x || event.clientX > rect.left + area.x + area.width || event.clientY < rect.top + area.y || event.clientY > rect.top + area.y + area.height) {
        leave();
        return;
    }
    const ms = (event.clientX - rect.left - area.x) / area.width * domain.value.xMax;
    hovered.value = props.samples[sampleTime.center(props.samples, ms)] ?? null;
    pointer.value = hovered.value === null ? null : event;
    emit('preview', hovered.value === null ? null : { timeMs: hovered.value.timeMs });
}
const i18nMessages = {
    'zh-cn': { local: {
        mouseSpeed: '鼠标移速（格/秒）',
        clickSpeed: '点击速度（次/秒）',
    } },
    en: { local: {
        mouseSpeed: 'Mouse speed (cells/s)',
        clickSpeed: 'Click speed (clicks/s)',
    } },
    es: { local: {
        mouseSpeed: 'Velocidad del ratón (casillas/s)',
        clickSpeed: 'Velocidad de clic (clics/s)',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-analysis-plot {
    position: relative;
    height: 180px;
}

.minigame-speed-labels {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
}

.mouse-label {
    color: var(--ui-color-primary);
}

.click-label {
    color: var(--ui-color-success);
}
</style>
