<template>
    <div class="analyzer-progress-bar">
        <div class="analyzer-progress-bar__seek">
            <div class="analyzer-progress-bar__track">
                <input
                    class="analyzer-progress-bar__slider" type="range" min="0" :max="durationMs" step="any"
                    :value="currentMs" :disabled="!hasDuration" :aria-label="t('local.position')" :aria-valuetext="timeText"
                    @pointerdown="beginSeek" @input="seekFromInput" @change="playback.endSeek()"
                >
                <div class="analyzer-progress-bar__markers" aria-hidden="true">
                    <span v-if="hasDuration && rangeStartMs !== 0" class="analyzer-progress-bar__marker analyzer-progress-bar__marker--start" :style="{ left: `${rangeStartMs / durationMs * 100}%` }" />
                    <span v-if="hasDuration && rangeEndMs !== durationMs" class="analyzer-progress-bar__marker analyzer-progress-bar__marker--end" :style="{ left: `${rangeEndMs / durationMs * 100}%` }" />
                </div>
            </div>
            <output class="analyzer-progress-bar__time" :title="timeText">{{ timeText }}</output>
        </div>
        <div class="analyzer-progress-bar__controls">
            <div class="analyzer-progress-bar__navigation button-group button-group--joined" role="group" :aria-label="t('local.navigation')">
                <BaseButton class="analyzer-progress-bar__start square-button" size="small" :disabled="!hasDuration" :title="t('local.start')" :aria-label="t('local.start')" @click="playback.seek(0)">
                    <i class="pi pi-step-backward" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__previous-keyframe square-button" size="small" :disabled="!hasDuration || !keyframeNavigation" :title="t('local.previousKeyframe')" :aria-label="t('local.previousKeyframe')" @click="keyframeNavigation?.previous()">
                    <i class="pi pi-angle-left" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__play square-button" size="small" :disabled="!playback.canPlay.value" :title="isPlaying ? t('common.button.pause') : t('common.button.play')" :aria-label="isPlaying ? t('common.button.pause') : t('common.button.play')" @click="isPlaying ? playback.pause() : playback.play()">
                    <i class="pi" :class="[isPlaying ? 'pi-pause' : 'pi-play']" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__next-keyframe square-button" size="small" :disabled="!hasDuration || !keyframeNavigation" :title="t('local.nextKeyframe')" :aria-label="t('local.nextKeyframe')" @click="keyframeNavigation?.next()">
                    <i class="pi pi-angle-right" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__end square-button" size="small" :disabled="!hasDuration" :title="t('local.end')" :aria-label="t('local.end')" @click="playback.seek(durationMs)">
                    <i class="pi pi-step-forward" aria-hidden="true" />
                </BaseButton>
            </div>
            <div class="analyzer-progress-bar__range button-group button-group--joined" role="group" :aria-label="t('local.range')">
                <BaseButton class="analyzer-progress-bar__range-start square-button" size="small" :disabled="rangeDisabled" :title="t('local.setRangeStart')" :aria-label="t('local.setRangeStart')" @click="playback.setRangeStart()">
                    <i class="pi pi-arrow-down-left" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__range-end square-button" size="small" :disabled="rangeDisabled" :title="t('local.setRangeEnd')" :aria-label="t('local.setRangeEnd')" @click="playback.setRangeEnd()">
                    <i class="pi pi-arrow-down-right" aria-hidden="true" />
                </BaseButton>
            </div>
            <div class="analyzer-progress-bar__speed button-group button-group--joined">
                <BaseButton class="analyzer-progress-bar__slower square-button" size="small" :disabled="slowerRate === undefined" :title="t('local.slower')" :aria-label="t('local.slower')" @click="changeRate(slowerRate)">
                    <i class="pi pi-minus" aria-hidden="true" />
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__normal" size="small" :title="t('local.normal')" :aria-label="t('local.normal')" @click="playback.setPlaybackRate(1)">
                    <i class="pi pi-refresh" aria-hidden="true" />
                    {{ playbackRate }}x
                </BaseButton>
                <BaseButton class="analyzer-progress-bar__faster square-button" size="small" :disabled="fasterRate === undefined" :title="t('local.faster')" :aria-label="t('local.faster')" @click="changeRate(fasterRate)">
                    <i class="pi pi-plus" aria-hidden="true" />
                </BaseButton>
            </div>
            <div class="analyzer-progress-bar__loop button-group button-group--joined" role="group" :aria-label="t('local.loopMode')">
                <BaseButton v-for="mode in loopModes" :key="mode.value" class="square-button" :class="`analyzer-progress-bar__loop-${mode.value}`" size="small" :type="loopMode === mode.value ? 'primary' : 'default'" :disabled="isPlaying" :aria-pressed="loopMode === mode.value" :title="t(mode.label)" :aria-label="t(mode.label)" @click="playback.setLoopMode(mode.value)">
                    <i class="pi" :class="mode.icon" aria-hidden="true" />
                </BaseButton>
            </div>
            <slot name="export" />
            <output class="analyzer-progress-bar__range-time" :title="rangeText" :aria-label="t('local.range')">{{ rangeText }}</output>
        </div>
    </div>
</template>

<script setup lang="ts">
import { useEventListener } from '@vueuse/core';
import { computed, onBeforeUnmount } from 'vue';
import type { PropType, VNode } from 'vue';
import { useI18n } from 'vue-i18n';

import type { KeyframeNavigation } from './keyframes';
import { playbackRates } from './usePlayback';
import type { LoopMode, PlaybackController } from './usePlayback';

import BaseButton from '@/components/common/BaseButton.vue';

const props = defineProps({
    playback: { type: Object as PropType<PlaybackController>, required: true },
    keyframeNavigation: { type: Object as PropType<KeyframeNavigation | null>, default: null },
});
defineSlots<{ export?: () => VNode[] }>();
const currentMs = computed(() => props.playback.currentMs.value);
const durationMs = computed(() => props.playback.durationMs.value);
const isPlaying = computed(() => props.playback.isPlaying.value);
const playbackRate = computed(() => props.playback.playbackRate.value);
const loopMode = computed(() => props.playback.loopMode.value);
const rangeStartMs = computed(() => props.playback.rangeStartMs.value);
const rangeEndMs = computed(() => props.playback.rangeEndMs.value);
const hasDuration = computed(() => durationMs.value > 0);
const rangeDisabled = computed(() => !hasDuration.value || (isPlaying.value && loopMode.value === 'range'));
const loopModes: { value: LoopMode; label: string; icon: string }[] = [
    { value: 'none', label: 'local.noLoop', icon: 'pi-ban' },
    { value: 'range', label: 'local.loopRange', icon: 'pi-arrows-h' },
    { value: 'all', label: 'local.loopAll', icon: 'pi-replay' },
];
const timeText = computed(() => `${(currentMs.value / 1000).toFixed(3)} / ${(durationMs.value / 1000).toFixed(3)} s`);
const rangeText = computed(() => `[${(rangeStartMs.value / 1000).toFixed(3)}, ${(rangeEndMs.value / 1000).toFixed(3)}] s`);
const slowerRate = computed(() => [...playbackRates].reverse().find((rate) => rate < playbackRate.value));
const fasterRate = computed(() => playbackRates.find((rate) => rate > playbackRate.value));

function beginSeek(event: PointerEvent) {
    if (event.button === 0) props.playback.beginSeek();
}

function seekFromInput(event: Event) {
    props.playback.seek((event.target as HTMLInputElement).valueAsNumber);
}

function changeRate(rate: number | undefined) {
    if (rate !== undefined) props.playback.setPlaybackRate(rate);
}

useEventListener('pointerup', () => {
    props.playback.endSeek();
});
useEventListener('pointercancel', () => {
    props.playback.endSeek();
});
useEventListener('blur', () => {
    props.playback.endSeek();
});
onBeforeUnmount(() => {
    props.playback.endSeek();
});

const i18nMessages = {
    'zh-cn': { local: {
        navigation: '播放定位',
        start: '跳到开头',
        end: '跳到结尾',
        previousKeyframe: '上一个关键帧',
        nextKeyframe: '下一个关键帧',
        position: '播放进度',
        slower: '减速',
        faster: '加速',
        normal: '恢复原速',
        loopMode: '循环模式',
        noLoop: '不循环',
        loopRange: '区间循环',
        loopAll: '全部循环',
        range: '选定区间',
        setRangeStart: '设为区间开头',
        setRangeEnd: '设为区间结尾',
    } },
    en: { local: {
        navigation: 'Playback navigation',
        start: 'Go to start',
        end: 'Go to end',
        previousKeyframe: 'Previous keyframe',
        nextKeyframe: 'Next keyframe',
        position: 'Playback position',
        slower: 'Slower',
        faster: 'Faster',
        normal: 'Normal speed',
        loopMode: 'Loop mode',
        noLoop: 'No loop',
        loopRange: 'Loop range',
        loopAll: 'Loop all',
        range: 'Selected range',
        setRangeStart: 'Set range start',
        setRangeEnd: 'Set range end',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.analyzer-progress-bar {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px 8px;
    border-top: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
}

.analyzer-progress-bar__seek,
.analyzer-progress-bar__controls {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
}

.analyzer-progress-bar__navigation,
.analyzer-progress-bar__range,
.analyzer-progress-bar__speed,
.analyzer-progress-bar__loop {
    align-items: center;
    min-width: 0;
}

.analyzer-progress-bar__controls {
    flex-wrap: wrap;
}

.analyzer-progress-bar__track {
    --thumb-size: 12px;
    position: relative;
    flex: 1;
    min-width: 0;
    height: 20px;
}

.analyzer-progress-bar__slider {
    appearance: none;
    display: block;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    background: transparent;
}

.analyzer-progress-bar__slider::-webkit-slider-runnable-track {
    height: 4px;
    border-radius: 2px;
    background: var(--ui-border-color);
}

.analyzer-progress-bar__slider::-moz-range-track {
    height: 4px;
    border-radius: 2px;
    background: var(--ui-border-color);
}

.analyzer-progress-bar__slider::-webkit-slider-thumb {
    appearance: none;
    width: var(--thumb-size);
    height: var(--thumb-size);
    margin-top: -4px;
    border: 0;
    border-radius: 50%;
    background: var(--ui-color-primary);
}

.analyzer-progress-bar__slider::-moz-range-thumb {
    width: var(--thumb-size);
    height: var(--thumb-size);
    border: 0;
    border-radius: 50%;
    background: var(--ui-color-primary);
}

.analyzer-progress-bar__slider:disabled {
    opacity: 0.5;
}

.analyzer-progress-bar__markers {
    position: absolute;
    inset: 0 calc(var(--thumb-size) / 2);
    pointer-events: none;
}

.analyzer-progress-bar__marker {
    position: absolute;
    width: 2px;
    height: 50%;
    transform: translateX(-50%);
}

.analyzer-progress-bar__marker--start {
    top: 0;
    background: var(--ui-color-primary);
}

.analyzer-progress-bar__marker--end {
    bottom: 0;
    background: var(--ui-color-warning);
}

.analyzer-progress-bar__time {
    flex: 0 1 22ch;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.analyzer-progress-bar__range {
    flex: 0 1 auto;
}

.analyzer-progress-bar__range-time {
    flex: 0 1 22ch;
    margin-left: auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.analyzer-progress-bar__normal {
    width: 72px;
    font-variant-numeric: tabular-nums;
}
</style>
