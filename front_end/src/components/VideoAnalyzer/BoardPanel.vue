<template>
    <section class="video-analyzer-board" :aria-label="t('local.board')">
        <div class="video-analyzer-board__content" :aria-busy="loading">
            <p v-if="loading" class="text video-analyzer-board__loading" role="status">
                {{ t('local.loading') }}
            </p>
            <div v-else-if="errorMessage" class="text video-analyzer-board__error" role="alert">
                <p>{{ t('local.loadFailed') }}</p>
                <p>{{ errorMessage }}</p>
            </div>
            <template v-else-if="board !== null">
                <div class="video-analyzer-board__viewport" :class="{ 'video-analyzer-board__viewport--auto': cellSizeMode === 'auto' }">
                    <MinesweeperBoard class="video-analyzer-board__main" :board="board" :size="boardSize">
                        <template #background>
                            <BoardBackground ref="backgroundLayer" class="video-analyzer-board__background" />
                        </template>
                        <template #foreground="{ size }">
                            <div class="video-analyzer-board__stack">
                                <BoardForeground v-if="globalBoard !== null" class="video-analyzer-board__global" :class="{ 'video-analyzer-board__global--hidden': !globalVisible }" :style="{ opacity: globalOpacity }" :board="globalBoard" />
                                <BoardForeground class="video-analyzer-board__opened" />
                                <BoardProbability v-if="probabilityBoard !== null" class="video-analyzer-board__probability" :class="{ 'video-analyzer-board__probability--hidden': !probabilityVisible }" :style="{ opacity: probabilityOpacity }" :board="probabilityBoard" :color="probabilityColor" />
                                <MouseTrace v-if="traceVisible" class="video-analyzer-board__trace" :style="{ opacity: traceOpacity }" v-bind="traceAppearanceProps" :events="traceEvents" :start-index="traceRange.startIndex" :end-index="traceRange.endIndex" :opacity="traceMaskOpacity" />
                                <BoardEventLayer v-if="eventLayer.visible" class="video-analyzer-board__events" :definitions="customEvents" :prepared="preparedEvents" :mouse-events="traceEvents" :settings="eventLayer" :current-ms="playback.currentMs.value" :current-event-index="currentEventIndex" :cell-size="size" :rows="board.length" :columns="board[0]?.length ?? 0" />
                                <BoardCursorLayer v-if="cursorVisible" ref="cursorLayer" class="video-analyzer-board__cursor" :position="cursorPosition" :cell-size="size" :shape="cursorShape" :size="cursorSize" />
                            </div>
                        </template>
                    </MinesweeperBoard>
                </div>
            </template>
            <div class="video-analyzer-board__controls">
                <div v-if="!loading && !errorMessage && board !== null" class="video-analyzer-board__layers">
                    <BoardLayerControl v-if="globalBoard !== null" v-model="globalVisible" v-model:opacity="globalOpacity" class="video-analyzer-board__global-control" :label="t('local.global')">
                        <template #toggle>
                            <BaseButton class="video-analyzer-board__global-toggle" size="small" :type="globalVisible ? 'primary' : 'default'" :aria-label="t('local.global')" :title="t('local.global')" :aria-pressed="globalVisible" @click="globalVisible = !globalVisible">
                                <i class="pi pi-globe" aria-hidden="true" />
                            </BaseButton>
                        </template>
                    </BoardLayerControl>
                    <BoardLayerControl v-if="probabilityBoard !== null" v-model="probabilityVisible" v-model:opacity="probabilityOpacity" class="video-analyzer-board__probability-control" :label="t('local.probability')">
                        <template #toggle>
                            <BaseButton class="video-analyzer-board__probability-toggle" size="small" :type="probabilityVisible ? 'primary' : 'default'" :aria-label="t('local.probability')" :title="t('local.probability')" :aria-pressed="probabilityVisible" @click="probabilityVisible = !probabilityVisible">
                                <i class="pi pi-percentage" aria-hidden="true" />
                            </BaseButton>
                        </template>
                        <template #settings>
                            <ColorSchemeSetting v-model="probabilityColorSettings" class="video-analyzer-board__probability-colors" :min="0" :max="100" />
                        </template>
                    </BoardLayerControl>
                    <BoardLayerControl v-model="traceVisible" v-model:opacity="traceOpacity" class="video-analyzer-board__trace-control" :label="t('local.mouseTrace')">
                        <template #toggle>
                            <BaseButton class="video-analyzer-board__trace-toggle" size="small" :type="traceVisible ? 'primary' : 'default'" :aria-label="t('local.mouseTrace')" :title="t('local.mouseTrace')" :aria-pressed="traceVisible" @click="traceVisible = !traceVisible">
                                <i class="pi pi-share-alt" aria-hidden="true" />
                            </BaseButton>
                        </template>
                        <template #settings>
                            <label class="video-analyzer-board__trace-setting">
                                <span>{{ t('local.tailLength') }}</span>
                                <input v-model.number="traceTailSlider" class="video-analyzer-board__trace-tail" type="range" min="0" max="1" step="any">
                                <output>{{ traceTailSeconds === Infinity ? t('local.infinite') : `${Number(traceTailSeconds.toPrecision(4))} s` }}</output>
                            </label>
                            <label class="video-analyzer-board__trace-setting">
                                <span>{{ t('local.maskOpacity') }}</span>
                                <input v-model.number="traceMaskOpacity" class="video-analyzer-board__trace-mask" type="range" min="0" max="1" step="0.01">
                                <output>{{ Math.round(traceMaskOpacity * 100) }}%</output>
                            </label>
                            <MouseTraceSettings v-model="traceAppearance" />
                        </template>
                    </BoardLayerControl>
                    <BoardSettingsControl class="video-analyzer-board__event-control" :label="t('local.events')">
                        <template #toggle>
                            <BaseButton class="video-analyzer-board__event-toggle" size="small" :type="eventLayer.visible ? 'primary' : 'default'" :aria-label="t('local.events')" :title="t('local.events')" :aria-pressed="eventLayer.visible" @click="eventLayer.visible = !eventLayer.visible">
                                <i class="pi pi-bolt" aria-hidden="true" />
                            </BaseButton>
                        </template>
                        <template #settings>
                            <BoardEventSettings v-model="eventLayer" :definitions="customEvents" />
                        </template>
                    </BoardSettingsControl>
                    <BoardSettingsControl class="video-analyzer-board__cursor-control" :label="t('local.cursor')">
                        <template #toggle>
                            <BaseButton class="video-analyzer-board__cursor-toggle" size="small" :type="cursorVisible ? 'primary' : 'default'" :aria-label="t('local.cursor')" :title="t('local.cursor')" :aria-pressed="cursorVisible" @click="cursorVisible = !cursorVisible">
                                <i class="pi pi-arrow-up-left" aria-hidden="true" />
                            </BaseButton>
                        </template>
                        <template #settings>
                            <label class="checkbox checkbox--small">
                                <input v-model="cursorVisible" class="checkbox-input video-analyzer-board__cursor-visible" type="checkbox">
                                <span>{{ t('local.showCursor') }}</span>
                            </label>
                            <div class="video-analyzer-board__cursor-setting">
                                <span>{{ t('common.prop.shape') }}</span>
                                <div class="button-group button-group--joined video-analyzer-board__cursor-shapes" role="group" :aria-label="t('common.prop.shape')">
                                    <BaseButton v-for="shape in cursorShapes" :key="shape.value" class="square-button video-analyzer-board__cursor-shape" :class="`video-analyzer-board__cursor-shape--${shape.value}`" size="small" :type="cursorShape === shape.value ? 'primary' : 'default'" :aria-pressed="cursorShape === shape.value" :aria-label="t(`local.cursor-${shape.value}`)" :title="t(`local.cursor-${shape.value}`)" @click="cursorShape = shape.value">
                                        <i class="pi" :class="shape.icon" aria-hidden="true" />
                                    </BaseButton>
                                </div>
                            </div>
                            <label class="video-analyzer-board__cursor-size-setting">
                                <span>{{ t('local.cursorSize') }}</span>
                                <input v-model.number="cursorSize" class="video-analyzer-board__cursor-size" type="range" min="4" max="40" step="1">
                                <output>{{ cursorSize }}px</output>
                            </label>
                        </template>
                    </BoardSettingsControl>
                </div>
                <div class="video-analyzer-board__settings">
                    <slot name="settings" />
                    <BoardSizeControls v-if="!loading && !errorMessage && board !== null" v-model="cellSizeMode" v-model:fixed-size="fixedCellSize" v-model:scale="cellScale" class="video-analyzer-board__size-controls" />
                </div>
            </div>
        </div>
        <ProgressBar :playback="playback" :keyframe-navigation="keyframeNavigation">
            <template #export>
                <VideoExportControls v-model:settings="exportSettings" v-model:exporting="exporting" v-model:pinned-size="pinnedSize" :cell-size="actualCellSize" :create-renderer="createExportRenderer" :rows="board?.length ?? 0" :columns="board?.[0]?.length ?? 0" :playback="playback" :filename="filename" />
            </template>
        </ProgressBar>
    </section>
</template>

<script setup lang="ts">
import './panels.css';
import '@putianyi888/vue3-minesweeper-board/style.css';
import { BoardBackground, BoardForeground, BoardProbability, MinesweeperBoard, MouseTrace } from '@putianyi888/vue3-minesweeper-board';
import type { LayerRenderHandle } from '@putianyi888/vue3-minesweeper-board';
import { computed, reactive, ref, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BoardCursorLayer from './BoardCursorLayer.vue';
import BoardEventLayer from './BoardEventLayer.vue';
import { defaultBoardEventSettings } from './boardEvents';
import type { BoardEventSettings as EventLayerSettings } from './boardEvents';
import BoardEventSettings from './BoardEventSettings.vue';
import { createBoardFrameRenderer } from './boardExportFrame';
import type { BoardFrameRenderer, ExportCursor } from './boardExportFrame';
import BoardLayerControl from './BoardLayerControl.vue';
import BoardSettingsControl from './BoardSettingsControl.vue';
import BoardSizeControls from './BoardSizeControls.vue';
import type { CellSizeMode, CursorShape } from './config';
import { defaultAnalyzerConfig } from './config';
import type { CustomEventDefinition, PreparedCustomEvent } from './customEvents';
import type { ExportBoardSettings } from './exportReplayState';
import { createExportStateReader } from './exportReplayState';
import type { KeyframeNavigation } from './keyframes';
import { defaultMouseTraceAppearance, mouseTraceAppearanceProps, mouseTraceRange, sliderToTailSeconds, tailSecondsToSlider } from './mouseTrace';
import type { MouseTraceAppearance, ReplayMouseTraceEvent } from './mouseTrace';
import MouseTraceSettings from './MouseTraceSettings.vue';
import ProgressBar from './ProgressBar.vue';
import type { ReplayVideo } from './replayParser';
import type { PlaybackController } from './usePlayback';
import type { CursorPosition } from './useReplayPosition';
import type { VideoExportSettings } from './videoExport';
import VideoExportControls from './VideoExportControls.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import ColorSchemeSetting from '@/components/visualization/ColorSchemeSetting.vue';
import { PiecewiseColorScheme } from '@/utils/colors';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';

const props = defineProps({
    board: { type: Array as PropType<number[][] | null>, default: null },
    globalBoard: { type: Array as PropType<number[][] | null>, default: null },
    probabilityBoard: { type: Array as PropType<number[][] | null>, default: null },
    playback: { type: Object as PropType<PlaybackController>, required: true },
    keyframeNavigation: { type: Object as PropType<KeyframeNavigation | null>, default: null },
    loading: { type: Boolean, required: true },
    errorMessage: { type: String, default: '' },
    traceEvents: { type: Array as PropType<ReplayMouseTraceEvent[]>, default: () => [] },
    customEvents: { type: Array as PropType<CustomEventDefinition[]>, default: () => [] },
    preparedEvents: { type: Object as PropType<Map<string, PreparedCustomEvent>>, default: () => new Map() },
    currentEventIndex: { type: Number as PropType<number | null>, default: null },
    nativeCellSize: { type: Number as PropType<number | null>, default: null },
    cursorPosition: { type: Object as PropType<CursorPosition | null>, default: null },
    filename: { type: String, default: 'replay' },
    createExportVideo: { type: Function as PropType<() => ReplayVideo>, default: null },
});
defineSlots<{ settings?: () => unknown }>();

const exporting = defineModel('exporting', { type: Boolean, default: false });
const exportSettings = defineModel<VideoExportSettings>('exportSettings', { default: () => reactive(defaultAnalyzerConfig().videoExport) });
const probabilityColorSettings = defineModel<PiecewiseColorSchemeInterface>('probabilityColorScheme', { required: true });
const pinnedSize = ref<number | null>(null);
const backgroundLayer = useTemplateRef<LayerRenderHandle>('backgroundLayer');
const cursorLayer = useTemplateRef<{ snapshot: (position?: CursorPosition | null, size?: number) => ExportCursor | null }>('cursorLayer');
const actualCellSize = computed(() => backgroundLayer.value?.cellSize ?? null);
const cellSizeMode = defineModel<CellSizeMode>('cellSizeMode', { default: 'auto' });
const fixedCellSize = defineModel('fixedCellSize', { type: Number, default: 32 });
const cellScale = defineModel('cellScale', { type: Number, default: 1 });
const boardSize = computed(() => {
    if (pinnedSize.value !== null) return pinnedSize.value;
    if (cellSizeMode.value === 'fixed') return fixedCellSize.value;
    if (cellSizeMode.value === 'relative' && props.nativeCellSize !== null) return props.nativeCellSize * cellScale.value;
    return 'auto';
});
const globalVisible = defineModel('globalVisible', { type: Boolean, default: false });
const probabilityVisible = defineModel('probabilityVisible', { type: Boolean, default: true });
const globalOpacity = defineModel('globalOpacity', { type: Number, default: 1 });
const probabilityOpacity = defineModel('probabilityOpacity', { type: Number, default: 1 });
const traceVisible = defineModel('traceVisible', { type: Boolean, default: false });
const traceOpacity = defineModel('traceOpacity', { type: Number, default: 1 });
const traceTailSeconds = defineModel('traceTailSeconds', { type: Number, default: 1 });
const traceMaskOpacity = defineModel('traceMaskOpacity', { type: Number, default: 0.5 });
const traceAppearance = defineModel<MouseTraceAppearance>('traceAppearance', { default: () => reactive(defaultMouseTraceAppearance()) });
const cursorVisible = defineModel('cursorVisible', { type: Boolean, default: true });
const cursorShape = defineModel<CursorShape>('cursorShape', { default: 'dot' });
const cursorSize = defineModel('cursorSize', { type: Number, default: 32 });
const eventLayer = defineModel<EventLayerSettings>('eventLayer', { default: defaultBoardEventSettings });
const cursorShapes: { value: CursorShape; icon: string }[] = [
    { value: 'dot', icon: 'pi-circle-fill' }, { value: 'windows', icon: 'pi-arrow-up-left' },
    { value: 'ring', icon: 'pi-circle' }, { value: 'crosshair', icon: 'pi-plus' },
];
const traceAppearanceProps = computed(() => mouseTraceAppearanceProps(traceAppearance.value));
const traceTailSlider = computed({
    get: () => tailSecondsToSlider(traceTailSeconds.value),
    set: (value: number) => {
        traceTailSeconds.value = sliderToTailSeconds(value);
    },
});
const traceRange = computed(() => mouseTraceRange(props.traceEvents, props.playback.currentMs.value, traceTailSeconds.value, props.playback.isPlaying.value || exporting.value ? props.currentEventIndex : null));
const probabilityColorScheme = computed(() => PiecewiseColorScheme.createFromTheme(probabilityColorSettings.value));
const probabilityColor = computed(() => {
    const scheme = probabilityColorScheme.value;
    return (value: number) => scheme.getColor(value * 100);
});

function createExportRenderer(size: number, signal: AbortSignal): BoardFrameRenderer {
    signal.throwIfAborted();
    const cursor = cursorVisible.value ? cursorLayer.value?.snapshot({ rowIndex: 0, columnIndex: 0 }, size) ?? null : null;
    const settings: ExportBoardSettings = {
        size,
        globalVisible: globalVisible.value,
        probabilityVisible: probabilityVisible.value,
        traceVisible: traceVisible.value,
        globalOpacity: globalOpacity.value,
        probabilityOpacity: probabilityOpacity.value,
        traceOpacity: traceOpacity.value,
        traceTailSeconds: traceTailSeconds.value,
        trace: JSON.parse(JSON.stringify({ ...traceAppearanceProps.value, opacity: traceMaskOpacity.value })) as ExportBoardSettings['trace'],
        probabilityColors: { colors: [...probabilityColorSettings.value.colors], thresholds: [...probabilityColorSettings.value.thresholds] },
        cursor: cursor === null ? null : { size: cursor.size, anchor: { x: -cursor.x / cursor.size, y: -cursor.y / cursor.size } },
    };
    if (props.createExportVideo === null) throw new Error('Replay is not loaded');
    const replay = props.createExportVideo();
    try {
        const read = createExportStateReader(replay, settings, props.traceEvents);
        return createBoardFrameRenderer((ms) => {
            const state = read(ms);
            return { ...state, cursor: state.cursor !== null && cursor !== null ? { ...state.cursor, svg: cursor.svg } : null };
        }, signal, () => {
            replay.free();
        });
    } catch (error) {
        replay.free();
        throw error;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        board: '棋盘',
        loading: '正在加载录像…',
        loadFailed: '录像加载失败',
        global: '全局',
        probability: '概率',
        mouseTrace: '鼠标轨迹',
        events: '自定义事件',
        tailLength: '拖尾长度 (s)',
        maskOpacity: '遮罩不透明度',
        infinite: '无限',
        cursor: '光标',
        showCursor: '显示光标',
        cursorSize: 'SVG 大小',
        'cursor-dot': '圆点',
        'cursor-windows': 'Windows 默认光标',
        'cursor-ring': '圆环',
        'cursor-crosshair': '十字',
    } },
    en: { local: {
        board: 'Board',
        loading: 'Loading replay…',
        loadFailed: 'Failed to load replay',
        global: 'Global',
        probability: 'Probability',
        mouseTrace: 'Mouse trace',
        events: 'Custom events',
        tailLength: 'Tail length (s)',
        maskOpacity: 'Mask opacity',
        infinite: 'Infinite',
        cursor: 'Cursor',
        showCursor: 'Show cursor',
        cursorSize: 'SVG size',
        'cursor-dot': 'Dot',
        'cursor-windows': 'Windows default cursor',
        'cursor-ring': 'Ring',
        'cursor-crosshair': 'Crosshair',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-analyzer-board {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
}

.video-analyzer-board__content {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-height: 0;
    min-width: 0;
    padding: 8px;
    overflow: hidden;
    background: var(--ui-bg-color);
}

.video-analyzer-board__viewport {
    display: flex;
    flex: 1;
    align-self: stretch;
    align-items: safe center;
    justify-content: safe center;
    min-height: 0;
    min-width: 0;
    overflow: auto;
}

.video-analyzer-board__main {
    flex: none;
}

.video-analyzer-board__viewport--auto {
    overflow: hidden;
}

.video-analyzer-board__stack {
    position: relative;
    display: grid;
}

.video-analyzer-board__opened,
.video-analyzer-board__global,
.video-analyzer-board__probability,
.video-analyzer-board__trace {
    grid-area: 1 / 1;
}

.video-analyzer-board__opened {
    z-index: 1;
}

.video-analyzer-board__probability {
    z-index: 2;
}

.video-analyzer-board__trace {
    z-index: 3;
}

.video-analyzer-board__global--hidden,
.video-analyzer-board__probability--hidden {
    visibility: hidden;
}

.video-analyzer-board__controls {
    display: flex;
    flex: none;
    flex-direction: column;
    align-self: stretch;
    justify-content: space-between;
    gap: 8px;
    overflow-y: auto;
}

.video-analyzer-board__layers {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0;
}

.video-analyzer-board__settings {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    flex: none;
    gap: 4px;
    margin-top: auto;
}

.video-analyzer-board__probability-colors :deep(.color-scheme-setting__actions) {
    gap: 0;
}

.video-analyzer-board__global-toggle,
.video-analyzer-board__probability-toggle,
.video-analyzer-board__trace-toggle,
.video-analyzer-board__event-toggle,
.video-analyzer-board__cursor-toggle {
    width: 28px;
    height: 28px;
    padding: 0;
    margin: 0;
    flex-shrink: 0;
}

.video-analyzer-board__trace-setting,
.video-analyzer-board__cursor-size-setting {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 7ch;
    align-items: center;
    gap: 6px;
    font-variant-numeric: tabular-nums;
}

.video-analyzer-board__trace-setting input,
.video-analyzer-board__cursor-size-setting input {
    width: 100%;
    min-width: 0;
    margin: 0;
    accent-color: var(--ui-color-primary);
}

.video-analyzer-board__trace-setting output,
.video-analyzer-board__cursor-size-setting output {
    text-align: right;
    overflow-wrap: anywhere;
}

.video-analyzer-board__cursor-setting {
    display: flex;
    align-items: center;
    gap: 8px;
}

.video-analyzer-board__error {
    max-height: 100%;
    overflow: auto;
    overflow-wrap: anywhere;
    color: var(--el-color-danger);
}
</style>
