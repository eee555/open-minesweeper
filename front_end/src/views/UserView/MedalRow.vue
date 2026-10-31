<template>
    <article class="medal-row">
        <div class="row-summary">
            <MedalArt class="main-art" :series="item.series" :code="item.code" :stage="displayStage" :size="64" />
            <div class="summary-copy">
                <h3>{{ medalDisplayName(item.series, item.code, displayStage, locale) }}</h3>
                <p>{{ caption.meaning }}</p>
                <p>{{ t('local.current') }}: {{ earned ? stageLabel(item.stage) : t('local.locked') }}</p>
                <p>{{ nextStage !== undefined ? `${t('local.next')}: ${stageLabel(nextStage)}` : t('local.maximum') }}</p>
                <BaseButton @click="preview(displayStage)">
                    {{ t('local.details') }}
                </BaseButton>
                <BaseButton v-if="editing && earned" :disabled="disabled" @click="$emit('pick')">
                    {{ selected ? t('local.remove') : t('local.add') }}
                </BaseButton>
                <p v-if="flavor" class="flavor">
                    <em>{{ flavor }}</em>
                </p>
            </div>
        </div>
        <div class="track-area">
            <div class="track-controls">
                <BaseButton v-if="item.thresholds.length > 1" :aria-label="t('local.previous')" @click="scroll(-1)">
                    ←
                </BaseButton>
                <BaseButton v-if="item.thresholds.length > 1" :aria-label="t('local.forward')" @click="scroll(1)">
                    →
                </BaseButton>
            </div>
            <div ref="track" class="stage-track" tabindex="0" :aria-label="caption.title" @keydown.left.prevent="scroll(-1)" @keydown.right.prevent="scroll(1)">
                <button v-for="(stage, index) in item.thresholds" :key="stage" type="button" class="stage-node" :class="{ current: index === currentIndex, pending: index > currentIndex }" :aria-current="index === currentIndex ? 'step' : undefined" @click="preview(stage)">
                    <MedalArt :series="item.series" :code="item.code" :stage="stage" :size="40" />
                    <span v-if="!medalArtPlate(item.series, stage) && medalStageLabel(item.series, stage)" class="stage-label">{{ stageLabel(stage) }}</span>
                    <span class="stage-status">{{ status(index) }}</span>
                </button>
            </div>
        </div>
        <section v-if="previewStage !== null" class="medal-detail" :aria-label="t('local.details')">
            <div>
                <strong>{{ t('local.preview') }}: {{ previewCaption.title }}</strong>
                <p>{{ previewCaption.meaning }}</p>
                <p>{{ t('local.current') }}: {{ earned ? stageLabel(item.stage) : t('local.locked') }}</p>
                <template v-if="earned && previewStage === item.stage">
                    <p v-if="item.granted_at">
                        {{ t('local.granted') }}: {{ item.granted_at }}
                    </p>
                    <p v-if="item.video_id">
                        {{ t('local.video') }}: {{ item.video_id }}
                    </p>
                    <p v-if="item.tournament_id">
                        {{ t('local.tournament') }}: {{ item.tournament_id }}
                    </p>
                    <p v-if="item.current_value !== null && item.kind === 'n'">
                        {{ t('local.count') }}: {{ item.current_value }}
                    </p>
                </template>
                <p v-if="flavor" class="flavor">
                    <em>{{ flavor }}</em>
                </p>
            </div>
            <BaseButton @click="previewStage = null">
                {{ t('local.close') }}
            </BaseButton>
        </section>
    </article>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import MedalArt from './MedalArt.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import type { MedalItem } from '@/services/medalService';
import { medalArtPlate, medalCaption, medalDisplayName, medalStageLabel } from '@/services/medalService';

const props = defineProps({
    item: { type: Object as PropType<MedalItem>, required: true },
    editing: Boolean,
    selected: Boolean,
    disabled: Boolean,
});
defineEmits<{ pick: [] }>();
const track = useTemplateRef<HTMLDivElement>('track');
const previewStage = ref<number | null>(null);
const earned = computed(() => props.item.grant_id !== null && props.item.stage !== null);
const currentIndex = computed(() => (earned.value ? props.item.thresholds.indexOf(props.item.stage ?? -1) : -1));
const nextStage = computed(() => props.item.next_threshold ?? props.item.thresholds[currentIndex.value + 1]);
const displayStage = computed(() => props.item.stage ?? props.item.thresholds[0] ?? 1);
const caption = computed(() => medalCaption(props.item.series, props.item.code, displayStage.value, locale.value));
const flavor = computed(() => props.item.annotation || caption.value.flavor);
const previewCaption = computed(() => medalCaption(props.item.series, props.item.code, previewStage.value, locale.value));
function stageLabel(stage: number | null) {
    const label = medalStageLabel(props.item.series, stage);
    if (['s', 'sn'].includes(props.item.series)) return `3BV/s ${label}`;
    if (['m', 'mn'].includes(props.item.series)) return `STNB ${label}`;
    if (['pn', 'pf', 'tn', 'tf'].includes(props.item.series)) return `thrp ${label}`;
    return label || t('local.once');
}
function status(index: number) {
    if (index === currentIndex.value) return t('local.currentStage');
    if (index < currentIndex.value) return t('local.reached');
    return index === currentIndex.value + 1 ? t('local.next') : t('local.unreached');
}
function preview(stage: number) {
    previewStage.value = stage;
}
function scroll(direction: number) {
    track.value?.scrollBy({ left: direction * Math.max(100, track.value.clientWidth * 0.7), behavior: 'smooth' });
}
async function positionTrack() {
    await nextTick();
    const node = track.value?.children[Math.max(0, currentIndex.value)];
    if (track.value && node instanceof HTMLElement) track.value.scrollLeft = node.offsetLeft - track.value.offsetLeft;
}
onMounted(() => {
    void positionTrack();
});
watch(() => props.item.stage, () => {
    void positionTrack();
});
const i18nMessages = {
    'zh-cn': { local: {
        current: '当前已达',
        locked: '未获得',
        next: '下一目标',
        maximum: '已达最高档',
        details: '详情',
        add: '加入佩戴',
        remove: '取消佩戴',
        browse: '左右浏览全部档位',
        previous: '浏览前面的档位',
        forward: '浏览后面的档位',
        preview: '正在预览',
        granted: '获得时间',
        video: '关联录像 ID',
        tournament: '赛事 ID',
        count: '当前计数',
        close: '关闭详情',
        once: '达成',
        currentStage: '当前档',
        reached: '✓ 已达成',
        unreached: '未达成',
    } },
    en: { local: {
        current: 'Currently reached',
        locked: 'Not earned',
        next: 'Next target',
        maximum: 'Highest tier reached',
        details: 'Details',
        add: 'Add to pins',
        remove: 'Unpin',
        browse: 'Browse all tiers horizontally',
        previous: 'Previous tiers',
        forward: 'Next tiers',
        preview: 'Previewing',
        granted: 'Granted at',
        video: 'Replay ID',
        tournament: 'Tournament ID',
        count: 'Current count',
        close: 'Close details',
        once: 'Complete',
        currentStage: 'Current tier',
        reached: '✓ Reached',
        unreached: 'Not reached',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
const { locale } = useI18n({ useScope: 'global' });
</script>

<style scoped>
.medal-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 20px;
    padding: 16px 0;
    border-bottom: 1px solid var(--ui-border-color-light);
    min-width: 0;
}
.row-summary {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    flex: 1 1 280px;
    min-width: 0;
}
.summary-copy {
    min-width: 0;
    overflow-wrap: anywhere;
}
h3, p {
    margin: 0 0 6px;
}
h3 {
    font-size: var(--ui-font-size-base);
}
p, .stage-status, .track-controls {
    font-size: var(--ui-font-size-small);
    color: var(--ui-text-color-regular);
}
.track-area {
    flex: 2 1 360px;
    min-width: 0;
    max-width: 100%;
}
.track-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    min-height: 32px;
}
.stage-track {
    position: relative;
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 4px 2px 10px;
    scrollbar-width: thin;
}
.stage-node {
    display: flex;
    flex: 0 0 92px;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 8px 4px;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--ui-text-color-primary);
    font: inherit;
    cursor: pointer;
}
.stage-node :deep(.medal-graphic) {
    min-height: 61px;
}
.main-art {
    min-height: 85px;
}
.flavor {
    margin-top: 8px;
    color: var(--ui-text-color-secondary);
}
.stage-node.current {
    border-color: var(--ui-color-primary);
    background: var(--ui-fill-color-light);
}
.stage-node.pending :deep(.art-stage) {
    opacity: .55;
}
.stage-label {
    font-size: 14px;
    overflow-wrap: anywhere;
}
.medal-detail {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex: 1 1 100%;
    gap: 12px;
    padding: 12px;
    background: var(--ui-fill-color-light);
    overflow-wrap: anywhere;
    min-width: 0;
}
.medal-detail > .base-button {
    flex-shrink: 0;
}
.stage-node:focus-visible, .stage-track:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: -2px;
}
</style>
