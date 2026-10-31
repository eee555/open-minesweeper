<template>
    <TouchTraceLayer class="minigame-touch-trace" :events="events" :end-index="eventIndex + 1" :opacity="minigameReplayAppearance.opacity" :line-width="minigameReplayAppearance.lineWidth" :down-marker="downMarker" :active-marker="activeMarker" color="var(--ui-color-primary)" />
</template>

<script setup lang="ts">
import { TouchTrace as TouchTraceLayer } from '@putianyi888/vue3-minesweeper-board';
import type { TouchTraceEvent } from '@putianyi888/vue3-minesweeper-board';
import { computed } from 'vue';
import type { PropType } from 'vue';

import { minigameReplayAppearance } from '@/utils/minigame/replay';
import type { TouchTrainingReplay } from '@/utils/minigame/replay';

const props = defineProps({
    replay: { type: Object as PropType<TouchTrainingReplay>, required: true },
    eventIndex: { type: Number, required: true },
    transposed: { type: Boolean, default: false },
});
const marker = minigameReplayAppearance.markers.lc;
const downMarker = marker === false ? false : { size: marker?.size ?? 0.25 };
const activeMarker = downMarker === false ? false : { ...downMarker, stroke: 'var(--ui-bg-color)' };
// Convert once per recording/orientation, retaining the 1:1 playback index mapping.
const events = computed(() => props.replay.events.map((event): TouchTraceEvent => {
    if (event.touchId === undefined) throw new Error('Missing replay touch ID');
    return {
        id: event.touchId,
        row: props.transposed ? event.column : event.row,
        column: props.transposed ? event.row : event.column,
        action: event.cancelled ? 'cancel' : event.action === 'lc' ? 'down' : event.action === 'mv' ? 'move' : 'up',
    };
}));
</script>
