<template>
    <div ref="containerRef" class="video-analyzer-view" role="region" :aria-label="title || t('local.analysis')">
        <div class="video-analyzer-view__workspace">
            <section v-if="infoOnTop && slots.info" class="text text-small video-analyzer-info" :aria-label="t('local.info')">
                <slot name="info" />
            </section>
            <ElSplitter :key="activeLayout" layout="vertical" class="video-analyzer-view__splitter" @resize-end="(_index, sizes) => savePanelSizes('outer', sizes)">
                <template v-if="isStacked">
                    <ElSplitterPanel v-for="(panel, index) in orderedPanels" :key="panel.id" :size="`${panelSizes.outer[index]}%`" min="15%">
                        <BoardPanel v-if="panel.id === 'board'" v-model:exporting="exporting" v-model:export-settings="analyzerConfig.videoExport" v-model:probability-color-scheme="probabilityColorScheme" v-model:event-layer="analyzerConfig.eventLayer" v-model:cell-size-mode="cellSizeMode" v-model:fixed-cell-size="fixedCellSize" v-model:cell-scale="cellScale" v-model:global-visible="globalVisible" v-model:probability-visible="probabilityVisible" v-model:global-opacity="globalOpacity" v-model:probability-opacity="probabilityOpacity" v-model:trace-visible="traceVisible" v-model:trace-opacity="traceOpacity" v-model:trace-tail-seconds="traceTailSeconds" v-model:trace-mask-opacity="traceMaskOpacity" v-model:trace-appearance="traceAppearance" v-model:cursor-visible="cursorVisible" v-model:cursor-shape="cursorShape" v-model:cursor-size="cursorSize" :custom-events="analyzerConfig.customEvents" :prepared-events="preparedEvents" :create-export-video="createExportVideo" :filename="filename || source?.filename || 'replay'" :cursor-position="cursorPosition" :native-cell-size="nativeCellSize" :trace-events="traceEvents" :current-event-index="currentEventIndex" :board="gameBoard" :global-board="globalBoard" :probability-board="probabilityBoard" :playback="playback" :keyframe-navigation="keyframeNavigation" :loading="loading" :error-message="errorMessage">
                            <template #settings>
                                <AnalyzerLayoutControl v-model="selectedLayout" />
                            </template>
                        </BoardPanel>
                        <div v-else class="video-analyzer-view__counter-group">
                            <section v-if="!infoOnTop && slots.info" class="text text-small video-analyzer-info" :aria-label="t('local.info')">
                                <slot name="info" />
                            </section>
                            <CounterPanel v-model="analyzerConfig.counter" :events="counterEvents" :counters="preparedCounters" :slot-names="slotNames" :duration-ms="durationMs" :current-ms="playback.currentMs.value" @send-to-slot="sendToSlot" />
                        </div>
                    </ElSplitterPanel>
                </template>
                <ElSplitterPanel v-else :size="`${panelSizes.outer[0]}%`" min="30%">
                    <ElSplitter class="video-analyzer-view__upper-splitter" @resize-end="(_index, sizes) => savePanelSizes('upper', sizes)">
                        <ElSplitterPanel v-for="(panel, index) in orderedPanels" :key="panel.id" :size="`${panelSizes.upper[index]}%`" min="15%">
                            <BoardPanel v-if="panel.id === 'board'" v-model:exporting="exporting" v-model:export-settings="analyzerConfig.videoExport" v-model:probability-color-scheme="probabilityColorScheme" v-model:event-layer="analyzerConfig.eventLayer" v-model:cell-size-mode="cellSizeMode" v-model:fixed-cell-size="fixedCellSize" v-model:cell-scale="cellScale" v-model:global-visible="globalVisible" v-model:probability-visible="probabilityVisible" v-model:global-opacity="globalOpacity" v-model:probability-opacity="probabilityOpacity" v-model:trace-visible="traceVisible" v-model:trace-opacity="traceOpacity" v-model:trace-tail-seconds="traceTailSeconds" v-model:trace-mask-opacity="traceMaskOpacity" v-model:trace-appearance="traceAppearance" v-model:cursor-visible="cursorVisible" v-model:cursor-shape="cursorShape" v-model:cursor-size="cursorSize" :custom-events="analyzerConfig.customEvents" :prepared-events="preparedEvents" :create-export-video="createExportVideo" :filename="filename || source?.filename || 'replay'" :cursor-position="cursorPosition" :native-cell-size="nativeCellSize" :trace-events="traceEvents" :current-event-index="currentEventIndex" :board="gameBoard" :global-board="globalBoard" :probability-board="probabilityBoard" :playback="playback" :keyframe-navigation="keyframeNavigation" :loading="loading" :error-message="errorMessage">
                                <template #settings>
                                    <AnalyzerLayoutControl v-model="selectedLayout" />
                                </template>
                            </BoardPanel>
                            <div v-else class="video-analyzer-view__counter-group">
                                <section v-if="!infoOnTop && slots.info" class="text text-small video-analyzer-info" :aria-label="t('local.info')">
                                    <slot name="info" />
                                </section>
                                <CounterPanel v-model="analyzerConfig.counter" :events="counterEvents" :counters="preparedCounters" :slot-names="slotNames" :duration-ms="durationMs" :current-ms="playback.currentMs.value" @send-to-slot="sendToSlot" />
                            </div>
                        </ElSplitterPanel>
                    </ElSplitter>
                </ElSplitterPanel>
                <ElSplitterPanel :size="`${panelSizes.outer[isStacked ? 2 : 1]}%`" min="15%">
                    <TimelinePanel v-model="analyzerConfig.timeline" v-model:custom-events="analyzerConfig.customEvents" v-model:board-event-keys="analyzerConfig.eventLayer.keys" v-model:window="timeWindow" :prepared-events="preparedEvents" :events="counterEvents" :rows="analyzerConfig.counter.rows" :counters="preparedCounters" :playback="playback" />
                </ElSplitterPanel>
            </ElSplitter>
        </div>
    </div>
</template>

<script setup lang="ts">
import { toRefs, useElementSize } from '@vueuse/core';
import { ElSplitter, ElSplitterPanel } from 'element-plus';
import { computed, reactive, ref, useTemplateRef, watch } from 'vue';
import type { PropType, VNode } from 'vue';
import { useI18n } from 'vue-i18n';

import AnalyzerLayoutControl from './AnalyzerLayoutControl.vue';
import BoardPanel from './BoardPanel.vue';
import { defaultAnalyzerConfig } from './config';
import type { AnalyzerConfig, AnalyzerLayout } from './config';
import { readCounterEvents } from './counter';
import CounterPanel from './CounterPanel.vue';
import { adjacentKeyframe } from './keyframes';
import { readMouseTrace } from './mouseTrace';
import type { ReplaySource } from './replayParser';
import { addTimelineTrack } from './timeline';
import type { TimeWindow } from './timeline';
import TimelinePanel from './TimelinePanel.vue';
import { usePlayback } from './usePlayback';
import { usePreparedAnalysis } from './usePreparedAnalysis';
import { useReplayPosition } from './useReplayPosition';
import { useReplaySource } from './useReplaySource';

import { baseErrorNotification } from '@/components/Notifications';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';

const props = defineProps({
    source: { type: Object as PropType<ReplaySource | null>, default: null },
    loading: { type: Boolean, default: false },
    errorMessage: { type: String, default: '' },
    title: { type: String, default: '' },
    filename: { type: String, default: '' },
});
const slots = defineSlots<{ info?: () => VNode[] }>();
const analyzerConfig = defineModel<AnalyzerConfig>('config', { default: defaultAnalyzerConfig, get: (value) => reactive(value), set: (value) => reactive(value) });
const probabilityColorScheme = defineModel<PiecewiseColorSchemeInterface>('probabilityColorScheme', { required: true });
const exporting = defineModel('exporting', { type: Boolean, default: false });
const replay = useReplaySource(() => props.source);
const { video, durationMs, globalBoard, createExportVideo } = replay;
const errorMessage = computed(() => props.errorMessage || replay.errorMessage.value);
const clock = usePlayback(durationMs);
const { gameBoard, probabilityBoard, currentEventIndex, cursorPosition, selectKeyframe, clearKeyframe } = useReplayPosition(video, clock.currentMs);
const playback = { ...clock,
    seek: (ms: number) => {
        clearKeyframe(); clock.seek(ms);
    } };
watch(() => analyzerConfig.value.playbackRate, (rate) => {
    playback.setPlaybackRate(rate);
}, { immediate: true });
watch(() => analyzerConfig.value.loopMode, (mode) => {
    playback.setLoopMode(mode);
    if (playback.loopMode.value !== mode) analyzerConfig.value.loopMode = playback.loopMode.value;
}, { immediate: true });
watch(playback.playbackRate, (rate) => {
    analyzerConfig.value.playbackRate = rate;
}, { flush: 'sync' });
watch(playback.loopMode, (mode) => {
    analyzerConfig.value.loopMode = mode;
}, { flush: 'sync' });
const traceEvents = computed(() => (video.value === null ? [] : readMouseTrace(video.value)));
const counterEvents = computed(() => (video.value === null ? [] : readCounterEvents(video.value)));
const { preparedCounters, preparedEvents } = usePreparedAnalysis(analyzerConfig, counterEvents, durationMs);
const slotNames = computed(() => analyzerConfig.value.timeline.slotSettings.map((slot) => slot.name));
const timeWindow = ref<TimeWindow>({ startMs: 0, endMs: 0 });
watch(durationMs, (duration) => {
    timeWindow.value = { startMs: 0, endMs: duration };
}, { immediate: true });

function sendToSlot(target: { key: string; slotIndex: number }) {
    addTimelineTrack(analyzerConfig.value.timeline, target.slotIndex, target.key);
}
const keyframes = computed(() => counterEvents.value.filter((event) => event.button));
const keyframeNavigation = { previous: () => {
    stepKeyframe(-1);
},
next: () => {
    stepKeyframe(1);
} };
const nativeCellSize = computed(() => video.value?.pix_size ?? null);
const { selectedLayout, cellSizeMode, fixedCellSize, cellScale, globalVisible, probabilityVisible, globalOpacity, probabilityOpacity, traceVisible, traceOpacity, traceMaskOpacity, traceAppearance, cursorVisible, cursorShape, cursorSize } = toRefs<AnalyzerConfig>(analyzerConfig, { replaceRef: false });
const traceTailSeconds = computed({
    get: () => (analyzerConfig.value.traceTailSeconds === 'infinite' ? Infinity : analyzerConfig.value.traceTailSeconds),
    set: (value: number) => {
        analyzerConfig.value.traceTailSeconds = value === Infinity ? 'infinite' : value;
    },
});
watch(() => props.source, () => {
    playback.pause();
    playback.endSeek();
    playback.seek(0);
    playback.setRangeStart();
    playback.seek(durationMs.value);
    playback.setRangeEnd();
    playback.seek(0);
    timeWindow.value = { startMs: 0, endMs: durationMs.value };
});

const containerRef = useTemplateRef('containerRef');
const { width } = useElementSize(containerRef);
const activeLayout = computed<AnalyzerLayout>((previous) => (exporting.value && previous !== undefined ? previous : selectedLayout.value === 'auto' ? width.value < 720 ? 'board-top' : 'counter-left' : selectedLayout.value));
const isStacked = computed(() => activeLayout.value === 'counter-top' || activeLayout.value === 'board-top');
const infoOnTop = computed<boolean>((previous) => (exporting.value && previous !== undefined ? previous : width.value < 720));
const boardPanel = { id: 'board' };
const counterPanel = { id: 'counter' };
const orderedPanels = computed(() => (activeLayout.value === 'counter-right' || activeLayout.value === 'board-top' ? [boardPanel, counterPanel] : [counterPanel, boardPanel]));
const panelSizes = computed(() => analyzerConfig.value.panelSizes[activeLayout.value]);

function savePanelSizes(group: 'outer' | 'upper', sizes: number[]) {
    const total = sizes.reduce((sum, size) => sum + size, 0);
    if (total > 0) panelSizes.value[group] = sizes.map((size) => size / total * 100);
}

function stepKeyframe(direction: -1 | 1) {
    const frame = adjacentKeyframe(keyframes.value, currentEventIndex.value, direction);
    if (frame === undefined) {
        baseErrorNotification(t('msg.actionFail'), t(direction === -1 ? 'local.noPreviousKeyframe' : 'local.noNextKeyframe'));
        return;
    }
    playback.seek(frame.timeMs);
    const boundedMs = Math.max(0, Math.min(playback.durationMs.value, frame.timeMs));
    if (playback.currentMs.value === boundedMs) selectKeyframe(frame.eventIndex);
}

const i18nMessages = {
    'zh-cn': { local: {
        analysis: '录像分析',
        info: '录像信息',
        noPreviousKeyframe: '没有上一个关键帧',
        noNextKeyframe: '没有下一个关键帧',
    } },
    en: { local: {
        analysis: 'Replay analysis',
        info: 'Replay information',
        noPreviousKeyframe: 'No previous keyframe',
        noNextKeyframe: 'No next keyframe',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-analyzer-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 480px;
    min-width: 0;
}

.video-analyzer-view__workspace {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
    border: 1px solid var(--ui-border-color);
}

.video-analyzer-view__splitter {
    flex: 1;
    min-height: 0;
    min-width: 0;
}

.video-analyzer-view__upper-splitter {
    height: 100%;
    min-height: 0;
    min-width: 0;
}

.video-analyzer-view__counter-group {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    min-width: 0;
}

.video-analyzer-view__counter-group :deep(.video-analyzer-counter) {
    flex: 1;
    height: auto;
}

.video-analyzer-info {
    flex: none;
    min-width: 0;
    padding: 6px;
    overflow-wrap: anywhere;
    border-bottom: 1px solid var(--ui-border-color);
    color: var(--ui-text-color-primary);
    background: var(--ui-bg-color);
}

.video-analyzer-info h2 {
    margin: 0;
}
</style>
