<template>
    <div class="progress-bar">
        <button type="button" class="base-button square-button" :title="t('local.restart')" :aria-label="t('local.restart')" @click="restart">
            <i class="pi pi-replay" aria-hidden="true" />
        </button>
        <button
            type="button"
            class="base-button square-button"
            :title="isPlaying ? t('button.pause') : t('button.play')"
            :aria-label="isPlaying ? t('button.pause') : t('button.play')"
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
        <div class="button-group button-group--joined progress-bar__rate-controls">
            <button type="button" class="base-button progress-bar__slower square-button" :disabled="playbackRate <= minRate" :title="t('local.slower')" :aria-label="t('local.slower')" @click="adjustRate(-rateStep)">
                <i class="pi pi-minus" aria-hidden="true" />
            </button>
            <InputNumber class="progress-bar__speed" :model-value="playbackRate" :min="minRate" :max="maxRate" :step="rateStep" :title="t('local.speed')" :aria-label="t('local.speed')" @update:model-value="changeRate" />
            <button type="button" class="base-button progress-bar__faster square-button" :disabled="playbackRate >= maxRate" :title="t('local.faster')" :aria-label="t('local.faster')" @click="adjustRate(rateStep)">
                <i class="pi pi-plus" aria-hidden="true" />
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-slider.css';
import '@/styles/button.css';
import 'primeicons/primeicons.css';

import { ElSlider } from 'element-plus';
import { onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import InputNumber from '@/components/common/InputNumber.vue';

const props = defineProps({
    durationMs: { type: Number, required: true },
    step: { type: Number, default: 10 },
});

const i18nMessages = {
    'zh-cn': { local: {
        restart: '重新开始',
        speed: '播放速度',
        slower: '减速',
        faster: '加速',
        step: '前进 0.1 秒',
    } },
    en: { local: {
        restart: 'Restart',
        speed: 'Playback speed',
        slower: 'Slower',
        faster: 'Faster',
        step: 'Step 0.1 seconds',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const currentMs = defineModel<number>({ required: true });
const isPlaying = ref(false);
const playbackRate = ref(1);
const minRate = 0.5;
const maxRate = 4;
const rateStep = 0.1;

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

function changeRate(rate: number) {
    const now = performance.now();
    const advancing = isPlaying.value && !isSeeking;
    const nextMs = advancing ? clampTime(startedFrom + (now - startedAt) * playbackRate.value, props.durationMs) : currentMs.value;
    playbackRate.value = rate;
    startedAt = now;
    startedFrom = nextMs;
    if (advancing) {
        currentMs.value = nextMs;
        if (nextMs >= props.durationMs) stopPlayback();
    }
}

function adjustRate(delta: number) {
    const rate = Number((playbackRate.value + delta).toFixed(12));
    changeRate(Math.min(maxRate, Math.max(minRate, rate)));
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

.progress-bar__rate-controls {
    flex-shrink: 0;
    align-items: center;
}

.progress-bar__speed {
    width: calc(4ch + 10px);
    flex-shrink: 0;
    padding-inline: 4px;
    text-align: center;
    font-variant-numeric: tabular-nums;
}
</style>
