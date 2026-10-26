<template>
    <span class="medal-graphic" :class="[`is-${metal}`, { 'is-framed': framed, 'is-pinned': pinned, 'is-badge': badge }]" :style="{ '--medal-size': `${size}px` }">
        <span class="medal-body">
            <img class="base" :src="shown" alt="" :width="size" :height="size" loading="lazy" decoding="async" @error="usePlaceholder">
            <span v-if="plate" class="plate" aria-hidden="true">{{ plate }}</span>
        </span>
    </span>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { PropType } from 'vue';

import { recolorMedalUrl } from '@/services/medalRecolor';
import { medalArtBadge, medalArtMetal, medalArtPlate, medalArtUrl } from '@/services/medalService';

const props = defineProps({
    series: { type: String, required: true },
    code: { type: String, required: true },
    stage: { type: Number as PropType<number | null>, default: null },
    size: { type: Number, required: true },
    framed: { type: Boolean, default: false },
    pinned: { type: Boolean, default: false },
});

const placeholder = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

const stage = computed(() => props.stage);
const metal = computed(() => medalArtMetal(props.series, props.code, stage.value));
const badge = computed(() => medalArtBadge(props.series));
const plate = computed(() => medalArtPlate(props.series, stage.value));
const src = computed(() => medalArtUrl(props.series, props.code, stage.value) ?? placeholder);
const shown = ref(placeholder);
let request = 0;

watch([src, metal], () => {
    const current = ++request;
    const address = src.value;
    const tone = metal.value;
    if (tone === 'e') {
        shown.value = address;
        return;
    }
    void recolorMedalUrl(address, tone).then((url) => {
        if (current === request) shown.value = url;
    }).catch(() => {
        if (current === request) shown.value = address;
    });
}, { immediate: true });

function usePlaceholder(event: Event) {
    const { target } = event;
    if (target instanceof HTMLImageElement && !target.src.startsWith('data:')) target.src = placeholder;
}
</script>

<style scoped lang="less">
.medal-graphic {
    position: relative;
    display: block;
    width: var(--medal-size);
    height: var(--medal-size);
    line-height: 0;
}

.medal-body {
    position: absolute;
    inset: 0;
    container-type: size;
}

.medal-graphic.is-b {
    --medal-fill: rgba(78, 36, 14, 0.9);
    --medal-ink: rgb(236, 176, 108);
}

.medal-graphic.is-i {
    --medal-fill: rgba(32, 40, 48, 0.9);
    --medal-ink: rgb(232, 238, 244);
}

.medal-graphic.is-e {
    --medal-fill: rgba(24, 18, 6, 0.9);
    --medal-ink: rgb(243, 212, 138);
}

.medal-graphic.is-framed {
    background: var(--ui-fill-color-blank);
}

.medal-graphic.is-framed::after {
    content: '';
    position: absolute;
    inset: 0;
    box-sizing: border-box;
    border: 1px solid var(--ui-border-color);
    pointer-events: none;
}

.medal-graphic.is-pinned::after {
    border: 3px solid var(--ui-color-primary);
}

.base {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
}

.plate {
    position: absolute;
    left: 50%;
    top: 80%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    height: calc(56 * 100cqw / 320);
    padding: 0 calc(10 * 100cqw / 320);
    border: calc(2 * 100cqw / 320) solid var(--medal-ink);
    border-radius: calc(8 * 100cqw / 320);
    background: var(--medal-fill);
    color: var(--medal-ink);
    font-family: Arial, 'Segoe UI', sans-serif;
    font-size: calc(38 * 100cqw / 320);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    white-space: nowrap;
    pointer-events: none;
    transform: translate(-50%, -50%);
}

.is-badge .plate {
    left: 40%;
    top: 73%;
}
</style>
