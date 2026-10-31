<template>
    <div v-show="pins.length" class="pins" :class="{ compact }" :tabindex="compact ? 0 : undefined">
        <div v-for="pin in pins" :key="pin.grant_id ?? pin.code" :title="medalCaption(pin.series, pin.code, pin.stage, locale).title" class="pin" :class="{ 'pin-ring': showRing(pin) }">
            <MedalArt v-if="pin.stage != null" :series="pin.series" :code="pin.code" :stage="pin.stage" :size="compact ? 32 : 48" />
            <span class="series">{{ seriesLabel(pin.series) }}</span>
            <span v-if="!medalArtPlate(pin.series, pin.stage)" class="stage">{{ stageLabel(pin) }}</span>
            <span v-if="showRing(pin)" class="count">{{ pin.current_value }}</span>
        </div>
    </div>
</template>

<script setup lang="ts">
import { onActivated, onDeactivated, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import MedalArt from './MedalArt.vue';

import type { MedalItem } from '@/services/medalService';
import { fetchPlayerMedals, medalArtPlate, medalCaption, medalSeriesLabel, medalStageLabel, subscribePlayerMedals } from '@/services/medalService';
import { MedalDirection, MedalKind } from '@/utils/medal_const';

const props = defineProps({
    userId: { type: Number, required: true },
    compact: { type: Boolean, default: false },
});

const { locale } = useI18n({ useScope: 'global' });
const route = useRoute();
const pins = ref<MedalItem[]>([]);
const viewing = ref(true);

function seriesLabel(series: string) {
    return medalSeriesLabel(series, locale.value);
}

function stageLabel(pin: MedalItem) {
    return medalStageLabel(pin.series, pin.stage);
}

function showRing(pin: MedalItem) {
    return pin.kind === MedalKind.COUNT && pin.direction === MedalDirection.ASC && pin.next_threshold === null && pin.stage !== null && pin.current_value !== null && pin.current_value > pin.stage;
}

watch(() => [props.userId, viewing.value], (_, __, onCleanup) => {
    pins.value = [];
    if (!viewing.value || !props.userId) return;
    // Removing the old subscription guards both late successes and late failures.
    onCleanup(subscribePlayerMedals(props.userId, (summary) => {
        pins.value = summary.pins;
    }, () => {
        pins.value = [];
    }));
}, { immediate: true });
watch(() => route.name, () => {
    if (viewing.value && props.userId) void fetchPlayerMedals(props.userId).catch(() => undefined);
});
onActivated(() => {
    viewing.value = true;
});
onDeactivated(() => {
    viewing.value = false;
});
</script>

<style scoped lang="less">
.pins {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    width: 100%;
    margin-top: 8px;
}

.pin {
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    width: calc(50% - 2px);
    min-height: 36px;
    padding: 2px 4px;
    border: 1px solid var(--ui-border-color);
    border-radius: 4px;
}

.pin-ring {
    box-shadow: 0 0 0 2px var(--ui-color-primary);
}

.series,
.stage {
    max-width: 100%;
    overflow: hidden;
    line-height: 1.2;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.series {
    color: var(--ui-text-color-secondary);
    font-size: var(--ui-font-size-extra-small);
}

.stage {
    min-height: 1.2em;
    color: var(--ui-text-color-primary);
    font-size: var(--ui-font-size-small);
}

.count {
    position: absolute;
    top: -6px;
    right: -4px;
    color: var(--ui-color-primary);
    font-size: var(--ui-font-size-extra-small);
    line-height: 1;
}
.pins.compact {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    height: 64px;
    min-width: 0;
    scrollbar-width: thin;
    margin-top: 0;
    align-items: flex-start;
}
.compact .pin {
    flex: 0 0 56px;
    width: 56px;
    padding: 0;
    border: 0;
}
.compact .series,
.compact .stage {
    display: none;
}
.compact:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: -2px;
}
</style>
