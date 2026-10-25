<template>
    <div class="training-scroll">
        <div class="training-frame" :class="borderless ? 'training-frame--borderless' : outerBorderClass">
            <component :is="restartOnCounter ? 'button' : 'div'" :type="restartOnCounter ? 'button' : undefined" class="training-frame-counters" :class="[borderless ? undefined : innerBorderClass, { 'training-frame-counters--static': !restartOnCounter }]" :aria-label="restartOnCounter ? restartLabel : undefined" :title="restartOnCounter ? restartLabel : undefined" @click="restartOnCounter && emit('restart')">
                <slot name="remaining" />
                <slot name="time" />
            </component>
            <div :class="borderless ? undefined : innerBorderClass">
                <slot />
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-minesweeper-board/style.css';

import { innerBorderClass, outerBorderClass } from '@putianyi888/vue3-minesweeper-board';

import { useRestartHotkey } from '@/utils/minigame/settings';

defineProps({ restartLabel: { type: String, required: true }, borderless: { type: Boolean, default: false }, restartOnCounter: { type: Boolean, default: true } });
const emit = defineEmits<{ restart: [] }>();
useRestartHotkey(() => {
    emit('restart');
});

defineSlots<{
    remaining: () => unknown;
    time: () => unknown;
    default: () => unknown;
}>();
</script>

<style scoped>
.training-frame--borderless > .training-frame-counters {
    border: 0;
}

.training-frame-counters--static {
    cursor: default;
}
</style>
