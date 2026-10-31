<template>
    <BaseButton class="square-button video-export__open" size="small" :disabled="cellSize === null || playback.durationMs.value <= 0" :title="t('local.export')" :aria-label="t('local.export')" @click="open">
        <i class="pi pi-video" aria-hidden="true" />
    </BaseButton>
    <Teleport to="body">
        <dialog ref="dialog" class="video-export" :aria-label="t('local.export')" @cancel.prevent="cancel">
            <template v-if="exporting">
                <h2 class="text text-medium">
                    {{ t(preparing ? 'local.preparing' : 'local.exporting') }}
                </h2>
                <progress class="video-export__progress" :value="progress" max="1" />
                <output aria-live="polite">{{ Math.round(progress * 100) }}%</output>
                <BaseButton class="video-export__cancel" :disabled="cancelling" @click="cancel">
                    <i class="pi pi-times" aria-hidden="true" />{{ t('button.cancel') }}
                </BaseButton>
            </template>
            <form v-else class="video-export__form" @submit.prevent="start">
                <h2 class="text text-medium">
                    {{ t('local.export') }}
                </h2>
                <label><span>{{ t('local.scope') }}</span><select v-model="scope" class="base-input video-export__scope"><option value="all">{{ t('local.all') }}</option><option value="range" :disabled="playback.rangeEndMs.value <= playback.rangeStartMs.value">{{ t('local.range') }}</option></select></label>
                <label><span>{{ t('prop.format') }}</span><select v-model="settings.format" class="base-input video-export__format"><option v-for="format in videoFormats" :key="format" :value="format">{{ format.toUpperCase() }}</option></select></label>
                <label><span>{{ t('local.fps') }}</span><input v-model.number="settings.fps" class="base-input video-export__fps" type="number" min="1" max="120" step="1" required></label>
                <label><span>{{ t('local.quality') }}</span><select v-model="settings.quality" class="base-input video-export__quality"><option v-for="quality in videoQualities" :key="quality" :value="quality">{{ t(`local.${quality}`) }}</option></select></label>
                <label v-for="edge in edges" :key="edge"><span>{{ t(`local.${edge}`) }}</span><input v-model.number="crop[edge]" class="base-input" :class="`video-export__${edge}`" type="number" min="0" :max="edge === 'top' || edge === 'bottom' ? rows - 1 : columns - 1" step="1" required></label>
                <output class="video-export__summary">{{ playback.playbackRate.value }}x · {{ dimensions }}</output>
                <p v-if="errorMessage" class="contains text-danger" role="alert">
                    {{ errorMessage }}
                </p>
                <div class="button-group button-group--joined video-export__actions">
                    <BaseButton class="video-export__close" @click="cancel">
                        {{ t('button.cancel') }}
                    </BaseButton>
                    <BaseButton class="video-export__start" type="primary" native-type="submit" :disabled="scope === 'range' && playback.rangeEndMs.value <= playback.rangeStartMs.value">
                        <i class="pi pi-download" aria-hidden="true" />{{ t('local.export') }}
                    </BaseButton>
                </div>
            </form>
        </dialog>
    </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { BoardFrameRenderer } from './boardExportFrame';
import { defaultAnalyzerConfig } from './config';
import type { PlaybackController } from './usePlayback';
import { cropPixels, exportBoardVideo, exportTiming, videoFormats, videoQualities } from './videoExport';
import type { BoardCrop, VideoExportSettings } from './videoExport';

import BaseButton from '@/components/common/BaseButton.vue';
import { baseErrorNotification } from '@/components/Notifications';
import { downloadBlob } from '@/utils/fileIO';

const props = defineProps({
    cellSize: { type: Number as PropType<number | null>, default: null },
    createRenderer: { type: Function as PropType<(size: number, signal: AbortSignal) => BoardFrameRenderer | Promise<BoardFrameRenderer>>, required: true },
    rows: { type: Number, required: true },
    columns: { type: Number, required: true },
    playback: { type: Object as PropType<PlaybackController>, required: true },
    filename: { type: String, default: 'replay' },
});
const exporting = defineModel('exporting', { type: Boolean, default: false });
const pinnedSize = defineModel<number | null>('pinnedSize', { default: null });
const dialog = useTemplateRef('dialog');
const settings = defineModel<VideoExportSettings>('settings', { default: () => reactive(defaultAnalyzerConfig().videoExport) });
const scope = ref<'all' | 'range'>('all');
const crop = ref<BoardCrop>({ top: 0, bottom: 0, left: 0, right: 0 });
const edges = ['top', 'bottom', 'left', 'right'] as const;
const progress = ref(0);
const preparing = ref(false);
const errorMessage = ref('');
const cancelling = ref(false);
let controller: AbortController | undefined;
let disposed = false;
const dimensions = computed(() => {
    try {
        const pixels = cropPixels(crop.value, props.rows, props.columns, props.cellSize ?? 0);
        return `${pixels.width} × ${pixels.height}px`;
    } catch {
        return '—';
    }
});

function open() {
    crop.value = { top: 0, bottom: props.rows - 1, left: 0, right: props.columns - 1 };
    scope.value = 'all';
    errorMessage.value = '';
    dialog.value?.showModal();
}

function cancel() {
    if (exporting.value) {
        cancelling.value = true;
        controller?.abort();
    } else dialog.value?.close();
}

async function start() {
    if (exporting.value || props.cellSize === null) return;
    const size = props.cellSize;
    const { playback } = props;
    const startMs = scope.value === 'all' ? 0 : playback.rangeStartMs.value;
    const endMs = scope.value === 'all' ? playback.durationMs.value : playback.rangeEndMs.value;
    const rate = playback.playbackRate.value;
    let region;
    try {
        region = cropPixels(crop.value, props.rows, props.columns, size);
        exportTiming(startMs, endMs, rate, settings.value.fps);
    } catch (error) {
        errorMessage.value = String(error);
        return;
    }
    const options = { ...settings.value };
    errorMessage.value = '';
    const wasPlaying = playback.isPlaying.value;
    playback.pause();
    playback.endSeek();
    pinnedSize.value = size;
    exporting.value = true;
    preparing.value = true;
    progress.value = 0;
    cancelling.value = false;
    controller = new AbortController();
    const { signal } = controller;
    const canvas = document.createElement('canvas');
    canvas.width = region.width;
    canvas.height = region.height;
    let renderer: BoardFrameRenderer | undefined;
    try {
        const context = canvas.getContext('2d');
        if (context === null) throw new Error('Cannot create video canvas');
        await nextTick();
        const boardRenderer = await props.createRenderer(size, signal);
        renderer = boardRenderer;
        preparing.value = false;
        const blob = await exportBoardVideo({ ...options,
            canvas,
            startMs,
            endMs,
            rate,
            signal,
            render: (ms) => boardRenderer.render(context, region, ms),
            onProgress: (completed, total) => {
                progress.value = completed / total;
            } });
        signal.throwIfAborted();
        downloadBlob(blob, `${props.filename}-${startMs}-${endMs}.${options.format}`);
    } catch (error) {
        if (!signal.aborted) {
            errorMessage.value = String(error);
            baseErrorNotification(t('local.failed'), errorMessage.value);
        }
    } finally {
        renderer?.close();
        canvas.width = canvas.height = 0;
        controller = undefined;
        exporting.value = false;
        preparing.value = false;
        pinnedSize.value = null;
        cancelling.value = false;
        if (!disposed) {
            if (wasPlaying) playback.play();
            if (!errorMessage.value) dialog.value?.close();
        }
    }
}

onBeforeUnmount(() => {
    disposed = true;
    controller?.abort();
    dialog.value?.close();
});

const i18nMessages = {
    'zh-cn': { local: {
        export: '导出视频',
        exporting: '正在导出视频',
        preparing: '正在准备视频',
        failed: '视频导出失败',
        scope: '时间范围',
        all: '全部录像',
        range: '选定区间',
        fps: '帧率',
        quality: '质量',
        top: 'top',
        bottom: 'bottom',
        left: 'left',
        right: 'right',
        low: '低',
        medium: '中',
        high: '高',
        'very-high': '很高',
    } },
    en: { local: {
        export: 'Export video',
        exporting: 'Exporting video',
        preparing: 'Preparing video',
        failed: 'Video export failed',
        scope: 'Time range',
        all: 'Whole replay',
        range: 'Selected range',
        fps: 'Frame rate',
        quality: 'Quality',
        top: 'top',
        bottom: 'bottom',
        left: 'left',
        right: 'right',
        low: 'Low',
        medium: 'Medium',
        high: 'High',
        'very-high': 'Very high',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-export {
    width: min(380px, calc(100vw - 32px));
    max-height: calc(100vh - 32px);
    box-sizing: border-box;
    padding: 12px;
    overflow: auto;
    border: 1px solid var(--ui-border-color);
    color: var(--ui-text-color-regular);
    background: var(--ui-bg-color);
}

.video-export::backdrop {
    background: rgb(0 0 0 / 40%);
}

.video-export__form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.video-export__form label {
    display: grid;
    grid-template-columns: 7em minmax(0, 1fr);
    align-items: center;
    gap: 8px;
}

.video-export__form input,
.video-export__form select {
    width: 100%;
    min-width: 0;
}

.video-export__progress {
    display: block;
    width: 100%;
    margin: 12px 0;
}

.video-export__actions {
    display: flex;
    justify-content: flex-end;
}
</style>
