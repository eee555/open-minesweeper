<template>
    <svg class="minigame-touch-trace" :width="columns * size" :height="rows * size" :viewBox="`0 0 ${columns} ${rows}`" aria-hidden="true">
        <g :transform="transposed ? 'matrix(0 1 1 0 0 0)' : undefined">
            <g v-for="trace in traces" :key="trace.id">
                <polyline :points="trace.events.map((event) => `${event.column},${event.row}`).join(' ')" fill="none" :stroke-width="minigameReplayAppearance.lineWidth" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" />
                <circle v-for="(event, index) in trace.events.filter((item) => item.action === 'lc')" :key="index" :cx="event.column" :cy="event.row" :r="markerRadius" fill="currentColor" opacity="0.6" />
            </g>
            <circle v-for="contact in contacts" :key="contact.id" :cx="contact.column" :cy="contact.row" :r="markerRadius" fill="currentColor" stroke="var(--ui-bg-color)" stroke-width="0.035" data-cy="minigame-replay-contact" />
        </g>
    </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';

import { minigameReplayAppearance } from '@/utils/minigame/replay';
import type { AnyTrainingReplay } from '@/utils/minigame/replay';

const props = defineProps({
    replay: { type: Object as PropType<AnyTrainingReplay>, required: true },
    eventIndex: { type: Number, required: true },
    size: { type: Number, required: true },
    transposed: { type: Boolean, default: false },
});
const rows = computed(() => (props.transposed ? props.replay.mode.columns : props.replay.mode.rows));
const columns = computed(() => (props.transposed ? props.replay.mode.rows : props.replay.mode.columns));
const contacts = computed(() => props.replay.events[props.eventIndex]?.contacts ?? []);
const marker = minigameReplayAppearance.markers.lc;
const markerRadius = (marker === false ? 0 : marker?.size ?? 0.25) / 2;
// One SVG for all contacts avoids allocating a board-sized canvas for every tap.
const traces = computed(() => {
    const grouped = new Map<number, AnyTrainingReplay['events']>();
    for (let index = 0; index <= props.eventIndex; index++) {
        const event = props.replay.events[index];
        if (event?.touchId === undefined) continue;
        let events = grouped.get(event.touchId);
        if (events === undefined) {
            events = [];
            grouped.set(event.touchId, events);
        }
        events.push(event);
    }
    return [...grouped].map(([id, events]) => ({ id, events }));
});
</script>

<style scoped>
.minigame-touch-trace {
    pointer-events: none;
    color: var(--ui-color-primary);
    overflow: hidden;
}
</style>
