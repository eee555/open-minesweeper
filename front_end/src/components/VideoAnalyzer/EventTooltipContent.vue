<template>
    <div class="card card-small event-tooltip text text-small">
        <template v-if="event">
            <strong>{{ event.key }}</strong>
            <template v-if="event.type === 'pulse'">
                <output class="event-tooltip__time">{{ t('local.time') }}: {{ seconds(event.pulse.timeMs) }} s</output>
                <output v-if="event.pulse.value !== undefined" class="event-tooltip__value">{{ t('prop.value') }}: {{ event.pulse.value }}</output>
            </template>
            <template v-else>
                <output class="event-tooltip__start">{{ t('local.start') }}: {{ seconds(event.span.startMs) }} s</output>
                <output class="event-tooltip__end">{{ t('local.end') }}: {{ seconds(event.span.endMs) }} s</output>
                <output class="event-tooltip__duration">{{ t('local.duration') }}: {{ seconds(event.span.endMs - event.span.startMs) }} s</output>
            </template>
        </template>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { HoveredCustomEvent } from './useEventTooltip';

defineProps({ event: { type: Object as PropType<HoveredCustomEvent | null>, default: null } });
const seconds = (ms: number) => (ms / 1000).toFixed(3);
const i18nMessages = {
    'zh-cn': { local: {
        time: '时间',
        start: '开始',
        end: '结束',
        duration: '持续时间',
    } },
    en: { local: {
        time: 'Time',
        start: 'Start',
        end: 'End',
        duration: 'Duration',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.event-tooltip {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-width: min(360px, calc(100vw - 16px));
    overflow-wrap: anywhere;
    white-space: pre-wrap;
    font-variant-numeric: tabular-nums;
}
</style>
