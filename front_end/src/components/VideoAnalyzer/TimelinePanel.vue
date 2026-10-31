<template>
    <section ref="timeline" class="text text-small video-analyzer-timeline" :aria-label="t('local.timeline')" @pointerleave="hideTooltip" @scroll.capture="hideTooltip" @wheel="hideTooltip">
        <div class="video-analyzer-timeline__viewport">
            <header class="video-analyzer-timeline__header">
                <TimelinePlot v-model:window="timeWindow" v-model:hover-ms="hoverMs" class="video-analyzer-timeline__ruler" ruler :playback="playback" :counters="counters" />
                <div class="button-group button-group--joined video-analyzer-timeline__add-buttons">
                    <BaseButton class="video-analyzer-timeline__add-slot" :title="t('local.addSlot')" :aria-label="t('local.addSlot')" @click="addSlot">
                        <i class="pi pi-plus" aria-hidden="true" />
                    </BaseButton>
                    <BaseButton class="video-analyzer-timeline__add-event" :title="t('local.addEvent')" :aria-label="t('local.addEvent')" @click="editor = { originalKey: null, event: defaultCustomEvent() }">
                        <i class="pi pi-bolt" aria-hidden="true" />
                    </BaseButton>
                </div>
            </header>
            <VueDraggable v-model="customEvents" class="video-analyzer-timeline__events" handle=".timeline-event-row__key" ghost-class="video-analyzer-timeline__ghost" :animation="150" scroll @start="hideTooltip">
                <TimelineEventRow v-for="event in customEvents" :key="event.key" v-model:window="timeWindow" v-model:hover-ms="hoverMs" :event="event" :data="preparedEvents.get(event.key) ?? { pulses: [], spans: [] }" :counters="counters" :playback="playback" @edit="editor = { originalKey: event.key, event }" @event-enter="showTooltip" @event-move="moveTooltip" @event-leave="hideTooltip" />
            </VueDraggable>
            <VueDraggable v-model="sortableSlots" class="video-analyzer-timeline__slots" handle=".timeline-slot__name" ghost-class="video-analyzer-timeline__ghost" :animation="150" scroll>
                <TimelineSlot v-for="(slot, index) in sortableSlots" :key="index" v-model:window="timeWindow" v-model:hover-ms="hoverMs" :settings="slot.settings" :tracks="slot.tracks" :rows="rows" :counters="counters" :playback="playback" @update:settings="config.slotSettings[index] = $event" @add-track="addTimelineTrack(config, index, $event)" @remove-track="config.slots[index].splice($event, 1)" @remove-slot="removeSlot(index)" />
            </VueDraggable>
        </div>
        <div hidden>
            <div ref="tooltip" class="timeline-event-tooltip">
                <EventTooltipContent :event="hovered" />
            </div>
        </div>
        <CustomEventEditor v-if="editor" :event="editor.event" :creating="editor.originalKey === null" :existing-keys="customEvents.filter((event) => event.key !== editor?.originalKey).map((event) => event.key)" :events="events" :duration-ms="playback.durationMs.value" @save="saveEvent" @remove="removeEvent" @close="editor = null" />
    </section>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { VueDraggable } from 'vue-draggable-plus';
import { useI18n } from 'vue-i18n';

import { updateBoardEventKeys } from './boardEvents';
import type { CounterEvent, CounterRow, PreparedCounter } from './counter';
import CustomEventEditor from './CustomEventEditor.vue';
import { defaultCustomEvent, prepareCustomEvents } from './customEvents';
import type { CustomEventDefinition, PreparedCustomEvent } from './customEvents';
import EventTooltipContent from './EventTooltipContent.vue';
import { addTimelineTrack } from './timeline';
import type { TimelineConfig, TimeWindow } from './timeline';
import TimelineEventRow from './TimelineEventRow.vue';
import TimelinePlot from './TimelinePlot.vue';
import TimelineSlot from './TimelineSlot.vue';
import { useEventTooltip } from './useEventTooltip';
import type { PlaybackController } from './usePlayback';

import BaseButton from '@/components/common/BaseButton.vue';

const props = defineProps({
    rows: { type: Array as PropType<CounterRow[]>, required: true },
    counters: { type: Object as PropType<Map<string, PreparedCounter>>, required: true },
    playback: { type: Object as PropType<PlaybackController>, required: true },
    events: { type: Array as PropType<CounterEvent[]>, default: () => [] },
    preparedEvents: { type: Object as PropType<Map<string, PreparedCustomEvent> | null>, default: null },
});
const config = defineModel<TimelineConfig>({ required: true });
const customEvents = defineModel<CustomEventDefinition[]>('customEvents', { default: () => [] });
const boardEventKeys = defineModel<string[]>('boardEventKeys', { default: () => [] });
const timeWindow = defineModel<TimeWindow>('window', { required: true });
const hoverMs = ref<number | null>(null);
const editor = ref<{ originalKey: string | null; event: CustomEventDefinition } | null>(null);
const preparedEvents = computed(() => props.preparedEvents ?? prepareCustomEvents(customEvents.value, props.events, props.playback.durationMs.value));
const timeline = useTemplateRef<HTMLElement>('timeline');
const tooltip = useTemplateRef<HTMLDivElement>('tooltip');
const { hovered, showTooltip, moveTooltip, hideTooltip } = useEventTooltip(timeline, tooltip);
watch([preparedEvents, customEvents, editor, () => timeWindow.value.startMs, () => timeWindow.value.endMs], hideTooltip);
const sortableSlots = computed({
    get: () => config.value.slots.map((tracks, index) => ({ tracks, settings: config.value.slotSettings[index] })),
    set: (slots) => {
        config.value = { slots: slots.map((slot) => slot.tracks), slotSettings: slots.map((slot) => slot.settings) };
    },
});

function addSlot() {
    config.value.slots.push([]);
    config.value.slotSettings.push({ name: `Plot ${config.value.slots.length}`, height: 160 });
}

function removeSlot(index: number) {
    config.value.slots.splice(index, 1);
    config.value.slotSettings.splice(index, 1);
}

function saveEvent(event: CustomEventDefinition) {
    const index = customEvents.value.findIndex((item) => item.key === editor.value?.originalKey);
    if (index < 0) customEvents.value.push(event);
    else {
        boardEventKeys.value = updateBoardEventKeys(boardEventKeys.value, customEvents.value[index].key, event.key);
        customEvents.value.splice(index, 1, event);
    }
    editor.value = null;
}

function removeEvent() {
    const index = customEvents.value.findIndex((item) => item.key === editor.value?.originalKey);
    if (index >= 0) {
        boardEventKeys.value = updateBoardEventKeys(boardEventKeys.value, customEvents.value[index].key, null);
        customEvents.value.splice(index, 1);
    }
    editor.value = null;
}

const i18nMessages = {
    'zh-cn': { local: {
        timeline: '时间轴',
        addSlot: '添加 plot',
        addEvent: '添加自定义事件',
    } },
    en: { local: {
        timeline: 'Timeline',
        addSlot: 'Add plot',
        addEvent: 'Add custom event',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-analyzer-timeline {
    --timeline-name-width: 26px;
    --timeline-legend-width: 20px;
    --timeline-controls-width: 28px;
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    min-height: 0;
    color: var(--ui-text-color-regular);
    background: var(--ui-bg-color);
}
.video-analyzer-timeline__viewport {
    flex: 1;
    min-height: 0;
    overflow: auto;
    scrollbar-gutter: stable;
}
.video-analyzer-timeline__header {
    position: sticky;
    top: 0;
    z-index: 3;
    display: grid;
    grid-template-columns: var(--timeline-name-width) var(--timeline-legend-width) minmax(0, 1fr) var(--timeline-controls-width);
    height: 30px;
    border-bottom: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
}
.video-analyzer-timeline__ruler {
    grid-column: 3;
}
.video-analyzer-timeline__add-buttons {
    grid-column: 1 / 3;
    grid-row: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}
.video-analyzer-timeline__add-buttons > * {
    width: 22px;
    height: 22px;
    padding: 0;
    margin: 0;
    align-self: center;
    justify-self: center;
}
.video-analyzer-timeline__slots,
.video-analyzer-timeline__events {
    display: flex;
    flex-direction: column;
    min-height: 0;
}
.video-analyzer-timeline__events:not(:empty) + .video-analyzer-timeline__slots:not(:empty) {
    border-top: 1px solid var(--ui-border-color);
}
.video-analyzer-timeline__ghost {
    opacity: 0.35;
}
</style>
