<template>
    <div class="progress-bar">
        <button type="button" class="base-button square-button" :title="t('local.restart')" :aria-label="t('local.restart')" @click="restart">
            <i class="pi pi-replay" aria-hidden="true" />
        </button>
        <button
            type="button"
            class="base-button square-button"
            :title="isPlaying ? t('common.button.pause') : t('common.button.play')"
            :aria-label="isPlaying ? t('common.button.pause') : t('common.button.play')"
            @click="togglePlay"
        >
            <i v-if="isPlaying" class="pi pi-pause" aria-hidden="true" />
            <i v-else class="pi pi-play" aria-hidden="true" />
        </button>
        <button type="button" class="base-button progress-bar__step" :title="t('local.step')" :aria-label="t('local.step')" @click="stepForward">
            +0.1s
        </button>
        <ElSlider
            v-model="currentMs" class="progress-bar__slider" :min="0" :max="durationMs"
            :step="step" :format-tooltip="formatSeconds" @pointerdown.capture="beginSeek" @change="finishSeek"
        />
        <ElSelect v-model="playbackRate" class="progress-bar__speed" :title="t('local.speed')">
            <ElOption v-for="rate in playbackRates" :key="rate" :value="rate" :label="`${rate}x`" />
        </ElSelect>
    </div>
</template>

<script setup lang="ts">
import '@/styles/button.css';
import 'primeicons/primeicons.css';

import { ElOption, ElSelect, ElSlider } from 'element-plus';
import { onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
    durationMs: { type: Number, required: true },
    step: { type: Number, default: 10 },
});

const i18nMessages = {
    'zh-cn': { local: {
        restart: '重新开始',
        speed: '播放速度',
        step: '前进 0.1 秒',
    } },
    en: { local: {
        restart: 'Restart',
        speed: 'Playback speed',
        step: 'Step 0.1 seconds',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const playbackRates = [0.5, 1, 1.5, 2, 4];

const currentMs = defineModel<number>({ required: true });
const isPlaying = ref(false);
const playbackRate = ref(1);

let animationFrameId = 0;
let startedAt = 0;
let startedFrom = 0;
let isSeeking = false;

watch(() => props.durationMs, (durationMs) => {
    currentMs.value = clampTime(currentMs.value, durationMs);
    if (currentMs.value >= durationMs) stopPlayback();
});

function formatSeconds(value: number) {
    return `${(value / 1000).toFixed(2)}s`;
}

function togglePlay() {
    if (isPlaying.value) {
        stopPlayback();
    } else {
        startPlayback();
    }
}

function startPlayback() {
    if (props.durationMs <= 0) return;
    syncPlaybackAnchor();
    if (startedFrom >= props.durationMs) {
        startedFrom = 0;
        currentMs.value = 0;
    }
    isPlaying.value = true;
    animationFrameId = requestAnimationFrame(tick);
}

function stopPlayback() {
    isPlaying.value = false;
    if (animationFrameId !== 0) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = 0;
    }
}

function tick(now: number) {
    if (!isPlaying.value) return;

    if (!isSeeking) {
        const nextMs = clampTime(startedFrom + (now - startedAt) * playbackRate.value, props.durationMs);
        currentMs.value = nextMs;
        if (nextMs >= props.durationMs) {
            stopPlayback();
            return;
        }
    }
    animationFrameId = requestAnimationFrame(tick);
}

function beginSeek(event: PointerEvent) {
    if (event.button === 0 && event.target instanceof Element && event.target.closest('.el-slider__runway')) {
        isSeeking = true;
    }
}

function finishSeek(value: number | number[]) {
    if (typeof value !== 'number') return;
    isSeeking = false;
    syncPlaybackAnchor(value);
    if (value >= props.durationMs) stopPlayback();
}

function restart() {
    stopPlayback();
    currentMs.value = 0;
}

function stepForward() {
    stopPlayback();
    currentMs.value = clampTime(currentMs.value + 100, props.durationMs);
}

function syncPlaybackAnchor(value = currentMs.value) {
    startedAt = performance.now();
    startedFrom = value;
}

function clampTime(value: number, durationMs: number) {
    return Math.min(Math.max(0, value), Math.max(0, durationMs));
}

onBeforeUnmount(() => {
    stopPlayback();
});
</script>

<style scoped>
.progress-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
}

.progress-bar > .base-button {
    margin: 0;
}

.progress-bar__slider {
    flex: 1 1 260px;
    min-width: 160px;
}

.progress-bar__speed {
    width: 86px;
}
</style>
