<template>
    <div class="minigame-replay-analysis" data-cy="minigame-replay-analysis">
        <SpeedPlot :samples="samples" :duration-ms="replay.durationMs" :clicks="game === 'left-click'" :marker-ms="hoveredChord?.chordMs ?? null" @preview="emit('preview', $event)" />
        <ChartTooltip :pointer="pointer">
            <div class="text text-small">
                {{ t(game === 'left-click' ? 'local.clickDurations' : 'local.chordDurations') }}
            </div>
            <div ref="plot" class="minigame-analysis-plot" role="img" :aria-label="t(game === 'left-click' ? 'local.clickDurations' : 'local.chordDurations')" :data-cy="game === 'left-click' ? 'minigame-click-histogram' : 'minigame-chord-bars'" @pointermove="hoverBar" @pointerleave="leave">
                <TransformGroup :domain="domain" :size="size" :padding="padding">
                    <Bar ref="bars" :values="values" :baseline="0" :gap="game === 'left-click' ? 0.04 : 0.2" :fill="game === 'left-click' ? 'var(--ui-color-primary)' : 'var(--ui-color-success)'" />
                    <Bar v-if="game === 'flag-chord'" class="minigame-chord-flag-part" :values="flagParts" :baseline="0" fill="var(--ui-color-primary)" />
                    <Axis direction="horizontal" :ticks="xTicks" :position="0">
                        <template #tick="{ tick }">
                            {{ game === 'left-click' ? formatTick(tick) : Math.floor(tick) + 1 }}
                        </template>
                    </Axis>
                </TransformGroup>
            </div>
            <template #content>
                <template v-if="hoveredChord">
                    <div>{{ t('local.operation', { number: (hoveredIndex ?? 0) + 1 }) }}</div>
                    <div>{{ t('local.flagTime') }}: {{ (hoveredChord.flagMs / 1000).toFixed(3) }} s</div>
                    <div>{{ t('local.leftTime') }}: {{ (hoveredChord.leftMs / 1000).toFixed(3) }} s</div>
                    <div>{{ t('local.chordTime') }}: {{ (hoveredChord.chordMs / 1000).toFixed(3) }} s</div>
                    <div>{{ t('local.flagPart') }}: {{ hoveredChord.leftMs - hoveredChord.flagMs }} ms</div>
                    <div>{{ t('local.chordPart') }}: {{ hoveredChord.chordMs - hoveredChord.leftMs }} ms</div>
                    <div>{{ t('local.total') }}: {{ hoveredChord.chordMs - hoveredChord.flagMs }} ms</div>
                </template>
                <template v-else-if="hoveredBin">
                    <div>{{ hoveredBin.x0 }}–{{ hoveredBin.x1 }} ms</div>
                    <div>{{ t('local.count') }}: {{ hoveredBin.length }}</div>
                </template>
            </template>
        </ChartTooltip>
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-plots/style.css';

import { Axis, Bar, formatTick, getNiceTicks, TransformGroup } from '@putianyi888/vue3-plots';
import { useElementSize } from '@vueuse/core';
import { computed, ref, shallowRef, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import ChartTooltip from './ChartTooltip.vue';
import SpeedPlot from './SpeedPlot.vue';

import type { ReplayPosition, TrainingReplay } from '@/utils/minigame/replay';
import { clickDurationBins, replaySpeeds } from '@/utils/minigame/replayAnalysis';

const props = defineProps({ replay: { type: Object as PropType<TrainingReplay>, required: true }, game: { type: String as PropType<'left-click' | 'flag-chord'>, required: true } });
const emit = defineEmits<{ preview: [position: ReplayPosition | null] }>();
const samples = computed(() => replaySpeeds(props.replay));
const bins = computed(() => clickDurationBins(props.replay));
const values = computed(() => (props.game === 'left-click' ? bins.value.map((item) => item.length) : props.replay.chords.map((chord) => chord.chordMs - chord.flagMs)));
const flagParts = computed(() => props.replay.chords.map((chord) => chord.leftMs - chord.flagMs));
const plot = useTemplateRef<HTMLDivElement>('plot');
const bars = useTemplateRef<InstanceType<typeof Bar>>('bars');
const { width } = useElementSize(plot);
const size = computed(() => ({ width: Math.max(1, width.value), height: 180 }));
const padding = { top: 8, right: 8, bottom: 24, left: 8 };
const domain = computed(() => ({ xMin: 0, xMax: props.game === 'left-click' ? bins.value.at(-1)?.x1 ?? 1 : Math.max(1, values.value.length), yMin: 0, yMax: Math.max(1, ...values.value) * 1.1 }));
const xTicks = computed(() => (props.game === 'left-click' ? getNiceTicks(0, domain.value.xMax, Math.max(2, Math.floor(width.value / 80))) : values.value.map((_item, index) => index + 0.5).filter((_item, index) => index % Math.max(1, Math.ceil(values.value.length / Math.max(2, Math.floor(width.value / 40)))) === 0)));
const hoveredIndex = ref<number | null>(null);
const pointer = shallowRef<PointerEvent | null>(null);
const hoveredChord = computed(() => (props.game === 'flag-chord' && hoveredIndex.value !== null ? props.replay.chords[hoveredIndex.value] : null));
const hoveredBin = computed(() => (props.game === 'left-click' && hoveredIndex.value !== null ? bins.value[hoveredIndex.value] : null));
function leave() {
    hoveredIndex.value = null;
    pointer.value = null;
    emit('preview', null);
}
function hoverBar(event: PointerEvent) {
    const rect = plot.value?.getBoundingClientRect();
    if (rect === undefined) return;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = bars.value?.bars.find((bar) => x >= bar.x && x <= bar.x + bar.width && y >= bar.y && y <= bar.y + bar.height);
    if (hit === undefined) {
        leave();
        return;
    }
    hoveredIndex.value = hit.index;
    pointer.value = event;
    const chord = hoveredChord.value;
    if (chord !== null && chord !== undefined) emit('preview', { timeMs: chord.chordMs, eventIndex: chord.eventIndex });
}
const i18nMessages = {
    'zh-cn': { local: {
        clickDurations: '左键按下至弹起（毫秒，不含首次点击）',
        chordDurations: '成功标双耗时（毫秒）',
        operation: '第 {number} 次标双',
        flagTime: '最后一次插旗',
        leftTime: '左键按下',
        chordTime: '双键触发',
        flagPart: '插旗 → 左键',
        chordPart: '左键 → 双键',
        total: '总间隔',
        count: '点击数',
    } },
    en: { local: {
        clickDurations: 'Left press to release (ms, excluding the first click)',
        chordDurations: 'Successful flag-and-chord durations (ms)',
        operation: 'Flag-and-chord {number}',
        flagTime: 'Last flag',
        leftTime: 'Left press',
        chordTime: 'Chord trigger',
        flagPart: 'Flag → left press',
        chordPart: 'Left press → chord',
        total: 'Total interval',
        count: 'Clicks',
    } },
    es: { local: {
        clickDurations: 'Duración del clic izquierdo (ms, sin contar el primero)',
        chordDurations: 'Duración de las aperturas simultáneas con bandera correctas (ms)',
        operation: 'Bandera y apertura simultánea {number}',
        flagTime: 'Última bandera',
        leftTime: 'Pulsación del botón izquierdo',
        chordTime: 'Activación de la apertura simultánea',
        flagPart: 'Bandera → pulsación izquierda',
        chordPart: 'Pulsación izquierda → apertura simultánea',
        total: 'Intervalo total',
        count: 'Haces',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-replay-analysis {
    display: grid;
    gap: 0.75rem;
    width: 100%;
    max-width: 52rem;
    min-width: 0;
    margin-inline: auto;
}

.minigame-analysis-plot {
    position: relative;
    height: 180px;
}
</style>
