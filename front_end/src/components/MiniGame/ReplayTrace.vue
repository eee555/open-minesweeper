<template>
    <MouseTrace class="minigame-replay-trace" :events="replay.events" :start-index="startIndex" :end-index="Math.max(startIndex, eventIndex + 1)" v-bind="minigameReplayAppearance" />
</template>

<script setup lang="ts">
import { MouseTrace } from '@putianyi888/vue3-minesweeper-board';
import { computed } from 'vue';
import type { PropType } from 'vue';

import { minigameReplayAppearance } from '@/utils/minigame/replay';
import type { TrainingReplay } from '@/utils/minigame/replay';

const props = defineProps({ replay: { type: Object as PropType<TrainingReplay>, required: true }, eventIndex: { type: Number, required: true } });
const startIndex = computed(() => {
    const index = props.replay.events.findIndex((event) => event.positionKnown);
    return index < 0 ? props.replay.events.length : index;
});
</script>

<style scoped>
.minigame-replay-trace {
    pointer-events: none;
}
</style>
