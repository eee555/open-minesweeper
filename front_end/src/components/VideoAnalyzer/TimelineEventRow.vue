<template>
    <section class="timeline-event-row" :aria-label="event.key">
        <span class="timeline-event-row__key">{{ event.key }}</span>
        <TimelinePlot v-model:window="timeWindow" v-model:hover-ms="hoverMs" class="timeline-event-row__plot" :playback="playback" :counters="counters" :event-definition="event" :event-data="data" @event-enter="(event, pointer) => emit('eventEnter', event, pointer)" @event-move="emit('eventMove', $event)" @event-leave="emit('eventLeave')" />
        <BaseButton class="timeline-event-row__settings" :title="t('local.settings')" :aria-label="t('local.settings')" @click="emit('edit')">
            <i class="pi pi-cog" aria-hidden="true" />
        </BaseButton>
    </section>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { PreparedCounter } from './counter';
import type { CustomEventDefinition, PreparedCustomEvent } from './customEvents';
import type { TimeWindow } from './timeline';
import TimelinePlot from './TimelinePlot.vue';
import type { HoveredCustomEvent } from './useEventTooltip';
import type { PlaybackController } from './usePlayback';

import BaseButton from '@/components/common/BaseButton.vue';

defineProps({
    event: { type: Object as PropType<CustomEventDefinition>, required: true },
    data: { type: Object as PropType<PreparedCustomEvent>, required: true },
    counters: { type: Object as PropType<Map<string, PreparedCounter>>, required: true },
    playback: { type: Object as PropType<PlaybackController>, required: true },
});
const emit = defineEmits<{ edit: []; eventEnter: [event: HoveredCustomEvent, pointer: PointerEvent]; eventMove: [pointer: PointerEvent]; eventLeave: [] }>();
const timeWindow = defineModel<TimeWindow>('window', { required: true });
const hoverMs = defineModel<number | null>('hoverMs', { default: null });
const i18nMessages = {
    'zh-cn': { local: { settings: '自定义事件设置' } },
    en: { local: { settings: 'Custom event settings' } },
    es: { local: { settings: 'Configuración de evento personalizado' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.timeline-event-row {
    display: grid;
    grid-template-columns: var(--timeline-name-width) var(--timeline-legend-width) minmax(0, 1fr) var(--timeline-controls-width);
    flex: none;
    height: 24px;
    min-width: 0;
    box-sizing: border-box;
}
.timeline-event-row__key {
    grid-column: 1 / 3;
    align-self: center;
    overflow: hidden;
    padding: 0 4px;
    white-space: nowrap;
    text-overflow: ellipsis;
    cursor: grab;
    touch-action: none;
    user-select: none;
}
.timeline-event-row__settings {
    align-self: center;
    justify-self: center;
    width: 24px;
    height: 24px;
    padding: 0;
}
</style>
