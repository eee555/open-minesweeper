<template>
    <div class="minigame-replay-controls" data-cy="minigame-replay-controls">
        <BaseButton class="square-button" size="small" :disabled="!playback.canPlay.value" :title="playback.isPlaying.value ? t('button.pause') : t('button.play')" :aria-label="playback.isPlaying.value ? t('button.pause') : t('button.play')" :aria-pressed="playback.isPlaying.value" data-cy="minigame-replay-play" @click="playback.isPlaying.value ? playback.pause() : playback.play()">
            <i class="pi" :class="playback.isPlaying.value ? 'pi-pause' : 'pi-play'" aria-hidden="true" />
        </BaseButton>
        <input type="range" min="0" :max="Math.max(1, playback.durationMs.value)" step="1" :value="positionMs" :disabled="!playback.canPlay.value" :aria-label="t('local.position')" data-cy="minigame-replay-position" @pointerdown="beginSeek" @input="seek" @change="endSeek">
        <output>{{ (positionMs / 1000).toFixed(3) }} / {{ (playback.durationMs.value / 1000).toFixed(3) }} s</output>
    </div>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';

import { useEventListener } from '@vueuse/core';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import type { PlaybackController } from '@/components/VideoAnalyzer/usePlayback';

const props = defineProps({ playback: { type: Object as PropType<PlaybackController>, required: true }, positionMs: { type: Number, required: true } });
let seeking = false;
function beginSeek(event: PointerEvent) {
    if (event.button !== 0) return;
    seeking = true;
    props.playback.beginSeek();
}
function seek(event: Event) {
    if (event.target instanceof HTMLInputElement) props.playback.seek(event.target.valueAsNumber);
}
function endSeek() {
    if (seeking) props.playback.endSeek();
    seeking = false;
    if (props.playback.currentMs.value >= props.playback.durationMs.value) props.playback.pause();
}
useEventListener(window, 'pointerup', endSeek);
useEventListener(window, 'pointercancel', endSeek);
useEventListener(window, 'blur', endSeek);

const i18nMessages = {
    'zh-cn': { local: {
        position: '回放进度',
    } },
    en: { local: {
        position: 'Replay position',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.minigame-replay-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    max-width: 52rem;
    min-width: 0;
    margin-inline: auto;
}

input {
    flex: 1 1 10rem;
    min-width: 0;
    margin: 0;
    accent-color: var(--ui-color-primary);
}

output {
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
}
</style>
