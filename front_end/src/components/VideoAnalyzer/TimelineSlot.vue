<template>
    <section ref="slotElement" class="timeline-slot" :style="{ height: `${settings.height}px` }" :aria-label="settings.name">
        <div class="timeline-slot__resize-top" />
        <span class="timeline-slot__name" :title="settings.name">{{ settings.name }}</span>
        <div class="timeline-slot__legend">
            <Tippy v-for="(track, index) in tracks" :key="index" class="timeline-slot__legend-item" interactive trigger="click" placement="right" :append-to="appendToBody" :duration="0">
                <BaseButton class="timeline-slot__legend-button" :class="{ 'timeline-slot__legend-button--missing': !counters.has(track.key) }" :style="{ backgroundColor: track.color, color: legendTextColor(track.color) }" :title="counters.has(track.key) ? track.key : `${track.key}: ${t('local.missingKey')}`">
                    {{ track.key }}
                </BaseButton>
                <template #content="{ hide }">
                    <BaseButton class="timeline-slot__remove-track" @click="hide(); emit('removeTrack', index)">
                        <i class="pi pi-trash" aria-hidden="true" />{{ t('local.removeTrack') }}
                    </BaseButton>
                </template>
            </Tippy>
        </div>
        <TimelinePlot v-model:window="timeWindow" v-model:hover-ms="hoverMs" class="timeline-slot__plot" :playback="playback" :counters="counters" :tracks="tracks" />
        <div class="button-group button-group--joined timeline-slot__controls">
            <Tippy interactive trigger="click" placement="left" :append-to="appendToBody" :duration="0">
                <BaseButton class="timeline-slot__add-track" :title="t('local.addTrack')" :aria-label="t('local.addTrack')" :disabled="rows.length === 0">
                    <i class="pi pi-plus" aria-hidden="true" />
                </BaseButton>
                <template #content="{ hide }">
                    <select class="timeline-slot__track-select" :aria-label="t('local.addTrack')" value="" @change="chooseTrack($event); hide()">
                        <option value="" disabled>
                            {{ t('local.addTrack') }}
                        </option>
                        <option v-for="row in rows" :key="row.key" :value="row.key">
                            {{ row.key }}
                        </option>
                    </select>
                </template>
            </Tippy>
            <BaseButton class="timeline-slot__rename" :title="t('local.rename')" :aria-label="t('local.rename')" @click="nameDraft = settings.name; dialog = 'rename'">
                <i class="pi pi-pencil" aria-hidden="true" />
            </BaseButton>
            <BaseButton class="timeline-slot__delete" :title="t('local.deleteSlot')" :aria-label="t('local.deleteSlot')" @click="dialog = 'deleteSlot'">
                <i class="pi pi-trash" aria-hidden="true" />
            </BaseButton>
        </div>
        <div class="timeline-slot__resize-bottom" />
        <ElDialog v-if="dialog" model-value :title="t(`local.${dialog}`)" width="min(360px, calc(100vw - 24px))" append-to-body @update:model-value="dialog = null">
            <form v-if="dialog === 'rename'" @submit.prevent="confirmDialog">
                <input v-model="nameDraft" class="timeline-slot__name-input" :aria-label="t('local.rename')">
            </form>
            <p v-else>
                {{ t('local.confirmDelete', { name: settings.name }) }}
            </p>
            <template #footer>
                <div class="button-group button-group--joined timeline-slot__dialog-actions">
                    <BaseButton class="timeline-slot__cancel" @click="dialog = null">
                        {{ t('button.cancel') }}
                    </BaseButton>
                    <BaseButton class="timeline-slot__confirm" type="primary" @click="confirmDialog">
                        {{ t('button.confirm') }}
                    </BaseButton>
                </div>
            </template>
        </ElDialog>
    </section>
</template>

<script setup lang="ts">
import type { ResizeEvent } from '@interactjs/types';
import { ElDialog } from 'element-plus';
import interact from 'interactjs';
import tinycolor from 'tinycolor2';
import { ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import type { CounterRow, PreparedCounter } from './counter';
import { minimumSlotHeight } from './timeline';
import type { TimelineSlotSettings, TimelineTrack, TimeWindow } from './timeline';
import TimelinePlot from './TimelinePlot.vue';
import type { PlaybackController } from './usePlayback';

import BaseButton from '@/components/common/BaseButton.vue';

defineProps({
    tracks: { type: Array as PropType<TimelineTrack[]>, required: true },
    rows: { type: Array as PropType<CounterRow[]>, required: true },
    counters: { type: Object as PropType<Map<string, PreparedCounter>>, required: true },
    playback: { type: Object as PropType<PlaybackController>, required: true },
});
const emit = defineEmits<{ addTrack: [key: string]; removeTrack: [index: number]; removeSlot: [] }>();
const settings = defineModel<TimelineSlotSettings>('settings', { required: true });
const timeWindow = defineModel<TimeWindow>('window', { required: true });
const hoverMs = defineModel<number | null>('hoverMs', { default: null });
const slotElement = useTemplateRef('slotElement');
const dialog = ref<'rename' | 'deleteSlot' | null>(null);
const nameDraft = ref('');
const appendToBody = () => document.body;

function legendTextColor(color: string) {
    return tinycolor(color).isDark() ? '#fff' : '#111';
}

function chooseTrack(event: Event) {
    const select = event.target as HTMLSelectElement;
    emit('addTrack', select.value);
    select.value = '';
}

function confirmDialog() {
    if (dialog.value === 'rename') settings.value = { ...settings.value, name: nameDraft.value };
    else emit('removeSlot');
    dialog.value = null;
}

watch(slotElement, (element, _old, onCleanup) => {
    if (element === null) return;
    const target = interact(element).resizable({
        edges: { top: '.timeline-slot__resize-top', bottom: '.timeline-slot__resize-bottom' },
        modifiers: [interact.modifiers.restrictSize({ min: { width: 0, height: minimumSlotHeight } })],
        listeners: { move: (event: ResizeEvent) => {
            settings.value = { ...settings.value, height: Math.max(minimumSlotHeight, event.rect.height) };
        } },
    });
    onCleanup(() => {
        target.unset();
    });
}, { flush: 'post', immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        addTrack: '添加轨道',
        removeTrack: '移除轨道',
        missingKey: '计数器 key 已失效',
        rename: '修改 plot 名称',
        deleteSlot: '删除 plot',
        confirmDelete: '确认删除 {name} 及其所有轨道？',
    } },
    en: { local: {
        addTrack: 'Add track',
        removeTrack: 'Remove track',
        missingKey: 'Counter key no longer exists',
        rename: 'Rename plot',
        deleteSlot: 'Delete plot',
        confirmDelete: 'Delete {name} and all its tracks?',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.timeline-slot {
    position: relative;
    display: grid;
    grid-template-columns: var(--timeline-name-width) var(--timeline-legend-width) minmax(0, 1fr) var(--timeline-controls-width);
    flex: none;
    min-height: 80px;
    min-width: 0;
    border-bottom: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
    box-sizing: border-box;
}
.timeline-slot__name {
    writing-mode: vertical-rl;
    overflow: hidden;
    padding: 8px 2px;
    white-space: nowrap;
    text-overflow: ellipsis;
    cursor: grab;
    user-select: none;
    touch-action: none;
}
.timeline-slot__legend {
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding: 4px 0;
}
.timeline-slot__legend-item {
    display: flex;
    flex: 1 1 0;
    min-height: 0;
}
.timeline-slot__legend-button {
    flex: 1;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    padding: 2px;
    margin: 0;
    border: 0;
    border-radius: 0;
    writing-mode: vertical-rl;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 11px;
}
.timeline-slot__legend-button--missing {
    text-decoration: line-through;
}
.timeline-slot__controls {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 6px;
}
.timeline-slot__controls button {
    width: 24px;
    height: 22px;
    padding: 0;
    margin: 0;
}
.timeline-slot__dialog-actions {
    justify-content: flex-end;
}
.timeline-slot__resize-top,
.timeline-slot__resize-bottom {
    position: absolute;
    z-index: 2;
    left: 0;
    right: 0;
    height: 4px;
    cursor: ns-resize;
    touch-action: none;
    user-select: none;
}
.timeline-slot__resize-top {
    top: 0;
}
.timeline-slot__resize-bottom {
    bottom: 0;
}
.timeline-slot__resize-top:hover,
.timeline-slot__resize-bottom:hover {
    background: var(--ui-color-primary);
    opacity: 0.5;
}
.timeline-slot__name-input,
.timeline-slot__track-select {
    box-sizing: border-box;
    width: 100%;
    max-width: min(280px, calc(100vw - 24px));
    padding: 4px;
    border: 1px solid var(--ui-border-color);
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}
</style>
