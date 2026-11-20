<template>
    <div class="reaction-analysis" data-cy="reaction-analysis">
        <ReactionChart :values="totals" :parts="waits" :labels="samples.map((_sample, index) => String(index + 1))" :tooltips="tooltips" :highlighted="highlighted" :label="t('local.reactions')" data-cy="reaction-bars" @hover="emit('preview', $event === null ? null : samples[$event]?.upMs ?? null)" />
        <div class="reaction-histograms">
            <div v-for="histogram in histograms" :key="String(histogram.jump)" class="reaction-histogram" :data-cy="histogram.jump ? 'reaction-jump-histogram' : 'reaction-adjacent-histogram'">
                <p class="text text-small">
                    {{ t(histogram.jump ? 'local.jump' : 'local.adjacent') }}
                </p>
                <ReactionChart :values="histogram.values" :labels="histogram.labels" :tooltips="histogram.tooltips" :label="t(histogram.jump ? 'local.jump' : 'local.adjacent')" @hover="hoverHistogram(histogram.jump, $event)" />
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, shallowRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import ReactionChart from './ReactionChart.vue';

import type { ReactionSample } from '@/utils/minigame/reactionRecording';
import { durationBins } from '@/utils/minigame/replayAnalysis';

const props = defineProps({ samples: { type: Array as PropType<ReactionSample[]>, required: true } });
const emit = defineEmits<{ preview: [timeMs: number | null] }>();
const hoveredBin = shallowRef<{ jump: boolean; index: number } | null>(null);
const seconds = (ms: number) => (ms / 1000).toFixed(3);
const totals = computed(() => props.samples.map((sample) => sample.upMs - sample.previousUpMs));
const waits = computed(() => props.samples.map((sample) => sample.downMs - sample.previousUpMs));
const tooltips = computed(() => props.samples.map((sample, index) => [
    `${t('local.reactions')} ${index + 1}`,
    `${t('local.previousUp')}: ${sample.previousUpMs} ms`,
    `${t('local.down')}: ${sample.downMs} ms`,
    `${t('local.up')}: ${sample.upMs} ms`,
    `${t('local.wait')}: ${sample.downMs - sample.previousUpMs} ms`,
    `${t('local.hold')}: ${sample.upMs - sample.downMs} ms`,
    `${t('local.total')}: ${sample.upMs - sample.previousUpMs} ms`,
].join('\n')));
const histograms = computed(() => [false, true].map((jump) => {
    const values = props.samples.filter((sample) => sample.jump === jump).map((sample) => sample.upMs - sample.previousUpMs);
    const bins = durationBins(values);
    return { jump, bins, values: bins.map((item) => item.length), labels: bins.map((item) => seconds(item.x0 ?? 0)), tooltips: bins.map((item) => `${seconds(item.x0 ?? 0)}–${seconds(item.x1 ?? 0)} s: ${item.length}`) };
}));
const highlighted = computed(() => {
    const selection = hoveredBin.value;
    if (selection === null) return [];
    const bucket = histograms.value.find((histogram) => histogram.jump === selection.jump)?.bins[selection.index];
    if (bucket === undefined) return [];
    const durations = new Set(bucket);
    return props.samples.flatMap((sample, index) => (sample.jump === selection.jump && durations.has(totals.value[index]) ? [index] : []));
});
function hoverHistogram(jump: boolean, index: number | null) {
    hoveredBin.value = index === null ? null : { jump, index };
}
const i18nMessages = {
    'zh-cn': { local: {
        reactions: '反应用时',
        adjacent: '连续点击间隔（秒）',
        jump: '跳一格点击间隔（秒）',
        previousUp: '上一次松开',
        down: '本次按下',
        up: '本次松开',
        wait: '松开至按下',
        hold: '按下至松开',
        total: '总间隔',
    } },
    en: { local: {
        reactions: 'Reaction times',
        adjacent: 'Adjacent-click intervals (s)',
        jump: 'Skip-one-click intervals (s)',
        previousUp: 'Previous release',
        down: 'Current press',
        up: 'Current release',
        wait: 'Release to press',
        hold: 'Press to release',
        total: 'Total interval',
    } },
    es: { local: {
        reactions: 'Tiempos de reacción',
        adjacent: 'Intervalos entre clics consecutivos (s)',
        jump: 'Intervalos entre clics alternos (s)',
        previousUp: 'Liberación anterior',
        down: 'Pulsación actual',
        up: 'Liberación actual',
        wait: 'De soltar a pulsar',
        hold: 'De pulsar a soltar',
        total: 'Intervalo total',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.reaction-analysis {
    width: 100%;
    max-width: 52rem;
    min-width: 0;
    margin-inline: auto;
}

.reaction-histograms {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
}

.reaction-histogram {
    min-width: 0;
}
</style>
