<template>
    <span class="medal-graphic" :class="{ 'is-framed': framed, 'is-pinned': pinned, 'is-locked': stage === null }" :style="{ '--medal-size': `${size}px` }" role="img" :aria-label="accessibleName" :data-score-tier="tier">
        <span class="art-stage">
            <span class="medal-body" :style="bodyStyle">
                <svg class="base" viewBox="0 0 320 320" :width="size" :height="size" aria-hidden="true" focusable="false">
                    <defs v-if="fixedBadge && color">
                        <mask :id="maskId" maskUnits="userSpaceOnUse" x="0" y="0" width="320" height="320">
                            <rect x="0" y="0" width="320" height="320" fill="white" />
                            <circle :cx="fixedBadge.cx" :cy="fixedBadge.cy" :r="fixedBadge.r" fill="black" />
                        </mask>
                        <clipPath :id="clipId">
                            <circle :cx="fixedBadge.cx" :cy="fixedBadge.cy" :r="fixedBadge.r" />
                        </clipPath>
                    </defs>
                    <image :href="shown" width="320" height="320" :filter="filter" :mask="fixedBadge && color ? `url(#${maskId})` : undefined" @error="usePlaceholder" />
                    <image v-if="fixedBadge && color" class="fixed-badge" :href="src" width="320" height="320" :clip-path="`url(#${clipId})`" @error="usePlaceholder" />
                </svg>
            </span>
            <img v-if="difficulty" class="difficulty" :src="difficultySrc" alt="" :width="size * .32" :height="size * .32" loading="lazy" decoding="async">
            <span v-if="cornerPlate && plate" class="corner-plate" aria-hidden="true"><span>{{ plate }}</span></span>
        </span>
        <span v-if="!cornerPlate" class="plate" aria-hidden="true">{{ plate }}</span>
    </span>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { medalAppearance, medalBodyPlacement, medalFixedBadge, medalScoreTier } from '@/services/medalAppearance';
import { medalPaletteColor } from '@/services/medalPalette';
import { medalPalette } from '@/services/medalPaletteStore';
import { recolorMedalUrl } from '@/services/medalRecolor';
import { medalArtMetal, medalArtPlate, medalArtUrl, medalCaption } from '@/services/medalService';
import { acquireMedalToneFilter } from '@/services/medalToneFilter';
import { MedalSeries } from '@/utils/medal_const';

const props = defineProps({
    series: { type: String, required: true },
    code: { type: String, required: true },
    stage: { type: Number as PropType<number | null>, default: null },
    size: { type: Number, required: true },
    framed: { type: Boolean, default: false },
    pinned: { type: Boolean, default: false },
    cornerPlate: { type: Boolean, default: false },
});
const { locale } = useI18n({ useScope: 'global' });
const id = useId();
const maskId = `${id}-body-mask`;
const clipId = `${id}-fixed-badge`;
const placeholder = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
const appearance = computed(() => medalAppearance(props.series, props.code));
const difficulty = computed(() => appearance.value?.difficulty);
const tier = computed(() => (appearance.value ? medalScoreTier(props.code, props.stage) : undefined));
const color = computed(() => (appearance.value && props.stage !== null
    ? medalPaletteColor(medalPalette.value, tier.value, props.code, props.stage) ?? '#7A7E87'
    : undefined));
const fixedBadge = computed(() => medalFixedBadge(props.series));
const plate = computed(() => medalArtPlate(props.series, props.stage));
const src = computed(() => medalArtUrl(props.series, props.code, props.stage) ?? placeholder);
const shown = ref(placeholder);
const filter = ref<string>();
const bodyStyle = computed(() => {
    const layout = appearance.value ? medalBodyPlacement(props.series) : { left: 0, top: 0, size: 100 };
    return { left: `${layout.left}%`, top: `${layout.top}%`, width: `${layout.size}%`, height: `${layout.size}%` };
});
const difficultySrc = computed(() => `${import.meta.env.BASE_URL}assets/medals/difficulty/${difficulty.value}.webp?v=1`);
const accessibleName = computed(() => {
    const { title } = medalCaption(props.series, props.code, props.stage, locale.value);
    return tier.value !== undefined ? `${title} · ${locale.value.startsWith('zh') ? '色档' : 'Color tier'} ${tier.value}` : title;
});

watch(color, (value, _, onCleanup) => {
    if (value === undefined) {
        filter.value = undefined; return;
    }
    const resource = acquireMedalToneFilter(value);
    filter.value = resource.filter;
    onCleanup(resource.release);
}, { immediate: true });
let request = 0;
watch([src, () => props.series, () => props.stage], () => {
    const current = ++request;
    const address = src.value;
    // Shareholder metal expresses tenure, not game difficulty.
    const metal = medalArtMetal(props.series, props.code, props.stage);
    if (props.series !== MedalSeries.SHAREHOLDER || metal === 'e') {
        shown.value = address; return;
    }
    void recolorMedalUrl(address, metal).then((url) => {
        if (current === request) shown.value = url;
    }).catch(() => {
        if (current === request) shown.value = address;
    });
}, { immediate: true });

function usePlaceholder(event: Event) {
    if (event.target instanceof SVGImageElement) event.target.setAttribute('href', placeholder);
}
</script>

<style scoped lang="less">
.medal-graphic {
    position: relative;
    display: block;
    width: var(--medal-size);
    line-height: 0;
    flex-shrink: 0;
}
.art-stage {
    position: relative;
    display: block;
    width: var(--medal-size);
    height: var(--medal-size);
}
.medal-body {
    position: absolute;
}
.base {
    display: block;
    width: 100%;
    height: 100%;
    overflow: visible;
}
.difficulty {
    position: absolute;
    left: 2%;
    top: 0;
    width: 32%;
    height: 32%;
    object-fit: contain;
    pointer-events: none;
}
.plate, .corner-plate {
    color: var(--ui-text-color-primary);
    font-family: Arial, 'Segoe UI', sans-serif;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    pointer-events: none;
}
.corner-plate {
    position: absolute;
    left: calc(100% - 6px);
    bottom: -2px;
    font-size: 11px;
    line-height: 14px;
}
.is-locked {
    opacity: .45;
}
.is-framed {
    background: var(--ui-fill-color-blank);
}
.is-framed::after {
    content: '';
    position: absolute;
    inset: 0;
    box-sizing: border-box;
    border: 1px solid var(--ui-border-color);
    pointer-events: none;
}
.is-pinned::after {
    border: 3px solid var(--ui-color-primary);
}
.plate {
    display: block;
    min-height: 21px;
    padding: 1px 2px 2px;
    box-sizing: border-box;
    font-size: 14px;
    line-height: 18px;
    text-align: center;
}
</style>
