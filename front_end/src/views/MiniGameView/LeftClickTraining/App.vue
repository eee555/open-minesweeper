<template>
    <section ref="playArea" class="training-page" :class="{ 'touch-fullscreen': isFullscreen }" :aria-label="t(gameType === 'multi-touch' ? 'local.touchTitle' : 'local.title')" :data-phase="phase" :data-replay="replayData !== null" data-cy="training-game">
        <div class="training-controls">
            <div class="checkbox-buttons" role="radiogroup" :aria-label="t('local.level')" data-cy="training-level">
                <label v-for="item in trainingLevels" :key="item.key" class="checkbox-button">
                    <input v-model="level" class="checkbox-button-input" type="radio" :name="levelGroupName" :value="item.key">
                    <span class="checkbox-button-content">{{ t(`local.level_${item.key}`) }}</span>
                </label>
            </div>
            <label>{{ t('local.density') }}
                <select v-model="density" data-cy="training-density">
                    <option v-for="item in trainingDensities" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
            </label>
            <div v-if="gameType === 'multi-touch' && level === 'e'" class="checkbox-buttons" role="radiogroup" :aria-label="t('local.orientation')" data-cy="training-orientation">
                <label v-for="direction in touchOrientations" :key="direction" class="checkbox-button">
                    <input v-model="minigameSettings.multiTouchOrientation" class="checkbox-button-input" type="radio" :name="orientationGroupName" :value="direction">
                    <span class="checkbox-button-content">{{ t(`local.${direction}`) }}</span>
                </label>
            </div>
            <label v-if="isFullscreen">{{ t('local.cellSize') }}
                <InputNumber v-model="minigameSettings.cellSize" :min="1" :max="Number.MAX_SAFE_INTEGER" integer step="1" inputmode="numeric" data-cy="training-cell-size" />
            </label>
            <BaseButton v-if="isFullscreen" class="square-button" :title="t('local.restart')" :aria-label="t('local.restart')" data-cy="training-restart" @click="restart">
                <i class="pi pi-refresh" aria-hidden="true" />
            </BaseButton>
            <BaseButton v-if="gameType === 'multi-touch'" class="square-button" :disabled="!isSupported" :title="t(isFullscreen ? 'local.exitFullscreen' : 'local.fullscreen')" :aria-label="t(isFullscreen ? 'local.exitFullscreen' : 'local.fullscreen')" :aria-pressed="isFullscreen" data-cy="training-fullscreen" @click="toggleFullscreen">
                <i class="pi" :class="isFullscreen ? 'pi-window-minimize' : 'pi-expand'" aria-hidden="true" />
            </BaseButton>
            <a v-if="!offline && !isFullscreen" class="base-button base-button--default base-button--size-default training-download" :href="offlineDownloadUrl" :download="offlineDownloadFilename" data-cy="training-download">{{ t('local.download') }}</a>
        </div>
        <MiniGameFrame :restart-label="t('local.restart')" :borderless="isFullscreen" :restart-on-counter="!isFullscreen" @restart="restart">
            <template #remaining>
                <div role="group" :aria-label="t('local.remaining')" :title="t('local.remaining')">
                    <Counter :value="replay.frame.value?.remaining ?? remaining" :fixed="0" :digits="3" :size="cellSize" data-cy="training-remaining" />
                </div>
            </template>
            <template #time>
                <div role="group" :aria-label="t('local.time')" :title="t('local.time')">
                    <Counter :value="(replay.frame.value?.timeMs ?? elapsed) / 1000" :fixed="3" :digits="3" :size="cellSize" data-cy="training-time" />
                </div>
            </template>
            <MiniGameBoard
                :key="round" :board="replay.frame.value?.board ?? board" :transposed="transposed" :size="cellSize" :foreground-opacity="minigameSettings.leftClickMineOpacity" :mine-pressed="minigameSettings.leftClickMinePressed" :disabled="phase === 'won' || phase === 'lost'"
                :input="gameType === 'multi-touch' ? 'touch' : 'mouse'" :record-mouse="gameType === 'left-click' && replay.data.value === null" :record-touch="gameType === 'multi-touch' && replay.data.value === null"
                :cursor-position="gameType === 'left-click' ? replay.frame.value?.cursor : undefined" :replay-press="replay.frame.value?.pressed ?? null"
                :label="t(gameType === 'multi-touch' ? 'local.touchBoardLabel' : 'local.boardLabel')" @action="onAction" @record="onMouseRecord" @touch-record="onTouchRecord"
            >
                <template #overlay>
                    <template v-if="replay.data.value && replay.frame.value">
                        <TouchTrace v-if="replay.data.value.game === 'multi-touch'" :replay="replay.data.value" :event-index="replay.frame.value.eventIndex" :size="cellSize" :transposed="transposed" />
                        <ReplayTrace v-else :replay="replay.data.value" :event-index="replay.frame.value.eventIndex" />
                    </template>
                </template>
            </MiniGameBoard>
        </MiniGameFrame>
        <slot v-if="!isFullscreen" name="resultActions" />
        <template v-if="replay.data.value && replay.frame.value">
            <ReplayControls :playback="replay.playback" :position-ms="replay.frame.value.timeMs" />
            <ReplayAnalysis v-if="replay.data.value.game !== 'multi-touch'" :replay="replay.data.value" game="left-click" @preview="replay.hover" />
        </template>
        <p v-if="fullscreenFailed" role="alert" class="text text-small">
            {{ t('local.fullscreenFailed') }}
        </p>
        <p v-if="!isFullscreen" class="text text-small">
            {{ t(gameType === 'multi-touch' ? 'local.touchRules' : 'local.rules') }}
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/components/MiniGame/training.css';

import { Counter } from '@putianyi888/vue3-minesweeper-board';
import { useFullscreen, useRafFn } from '@vueuse/core';
import { computed, ref, shallowRef, useId, useTemplateRef, watch } from 'vue';
import type { PropType, VNode } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import InputNumber from '@/components/common/InputNumber.vue';
import MiniGameBoard from '@/components/MiniGame/Board.vue';
import MiniGameFrame from '@/components/MiniGame/Frame.vue';
import ReplayAnalysis from '@/components/MiniGame/ReplayAnalysis.vue';
import ReplayControls from '@/components/MiniGame/ReplayControls.vue';
import ReplayTrace from '@/components/MiniGame/ReplayTrace.vue';
import TouchTrace from '@/components/MiniGame/TouchTrace.vue';
import type { ClassicMouseAction } from '@/utils/classicMouse';
import { offlineDownloadFilename, offlineDownloadUrl } from '@/utils/minigame/games';
import { saveMinigameResult } from '@/utils/minigame/history';
import { leftClickModes, LeftClickTraining, multiTouchModes, trainingDensities, trainingLevels } from '@/utils/minigame/leftClickTraining';
import { TrainingReplayRecorder } from '@/utils/minigame/replay';
import type { AnyTrainingReplay, TrainingMouseInput, TrainingRecording } from '@/utils/minigame/replay';
import { minigameSettings } from '@/utils/minigame/settings';
import type { TouchRecording, TrainingTouchInput } from '@/utils/minigame/touchRecording';
import { TouchReplayRecorder } from '@/utils/minigame/touchReplay';
import { useTrainingReplay } from '@/utils/minigame/useTrainingReplay';

// Mouse and touch share the game rules and layout; input and replay streams stay separate.
const props = defineProps({
    offline: { type: Boolean, default: false },
    gameType: { type: String as PropType<'left-click' | 'multi-touch'>, default: 'left-click' },
    replayData: { type: Object as PropType<Extract<AnyTrainingReplay, { game: 'left-click' | 'multi-touch' }> | null>, default: null },
});
const emit = defineEmits<{ completed: [rankingKey: string, scoreMs: number, replay: TrainingRecording | TouchRecording]; reset: [] }>();
defineSlots<{ resultActions?: () => VNode[] }>();
const level = ref<typeof trainingLevels[number]['key']>(props.replayData?.mode.key ?? 'b');
const levelGroupName = useId();
const touchOrientations = ['horizontal', 'vertical'] as const;
const orientationGroupName = useId();
const transposed = computed(() => props.gameType === 'multi-touch' && level.value === 'e' && minigameSettings.value.multiTouchOrientation === 'vertical');
const density = ref<typeof trainingDensities[number]['value']>(props.replayData?.mode.density ?? 50);
const mode = computed(() => {
    const selected = (props.gameType === 'multi-touch' ? multiTouchModes : leftClickModes).find((item) => item.key === level.value && item.density === density.value);
    if (selected === undefined) throw new Error('Unknown left-click training mode');
    return selected;
});
const playArea = useTemplateRef('playArea');
const { isFullscreen, isSupported, toggle } = useFullscreen(playArea, { autoExit: true });
const cellSize = computed(() => minigameSettings.value.cellSize);
const fullscreenFailed = ref(false);
async function toggleFullscreen() {
    fullscreenFailed.value = false;
    try {
        await toggle();
    } catch {
        fullscreenFailed.value = true;
    }
}
let game = new LeftClickTraining(mode.value, undefined, props.replayData?.initialBoard);
const board = shallowRef(game.board);
const phase = ref(game.phase);
const remaining = ref(game.remainingSafe);
const elapsed = ref(0);
const round = ref(0);
function createRecorder() {
    return props.gameType === 'multi-touch' ? new TouchReplayRecorder(game.mode, game.board) : new TrainingReplayRecorder({ game: 'left-click', mode: game.mode }, game.board);
}
let recorder = createRecorder();
const replay = useTrainingReplay<AnyTrainingReplay>();

const { pause, resume } = useRafFn(() => {
    elapsed.value = game.elapsedMs(performance.now());
}, { immediate: false });

function restart() {
    pause();
    replay.reset();
    game = new LeftClickTraining(mode.value);
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remainingSafe;
    elapsed.value = 0;
    recorder = createRecorder();
    round.value++;
    emit('reset');
}

function onAction(action: ClassicMouseAction, row: number, column: number, now: number) {
    if (action !== 'left') return;
    if (!game.trigger(row, column, now)) return;
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remainingSafe;
    elapsed.value = game.elapsedMs(now);
    const recording = recorder.update(now, phase.value, elapsed.value);
    replay.finish(recording);
    if (game.phase === 'won' && recording !== null) {
        if (recording.game === 'multi-touch') void saveMinigameResult({ game: 'multi-touch', mode: game.mode, scoreMs: elapsed.value, replay: recording.recording });
        else void saveMinigameResult({ game: 'left-click', mode: game.mode, scoreMs: elapsed.value, replay: recording.recording });
        emit('completed', game.mode.rankingKey, elapsed.value, recording.recording);
    }
    if (game.phase === 'playing') resume();
    else pause();
}

function onMouseRecord(input: TrainingMouseInput) {
    if (recorder instanceof TrainingReplayRecorder) recorder.capture(input);
}

function onTouchRecord(input: TrainingTouchInput) {
    if (recorder instanceof TouchReplayRecorder) recorder.capture(input);
}

watch(mode, restart);
watch(() => props.replayData, (data, previous) => {
    if (data === null) {
        if (previous && replay.data.value === previous) restart();
        return;
    }
    pause();
    const final = data.snapshots.at(-1);
    board.value = final?.board ?? data.initialBoard;
    remaining.value = final?.remaining ?? 0;
    elapsed.value = data.durationMs;
    phase.value = 'won';
    replay.finish(data);
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        title: '左键训练',
        touchTitle: '多指训练',
        touchBoardLabel: '多指训练棋盘，触摸没有雷的凸起格子',
        touchRules: '仅接受触屏，每根手指独立操作。按下即打开当前安全格，首次按下开始计时；滑动和抬起不开格，触雷即失败。单指滑动可滚动页面，多指按住时不滚动。允许单指完成，雷的不透明度可在小游戏设置中调整。',
        orientation: '棋盘方向',
        cellSize: '格子大小',
        horizontal: '横向',
        vertical: '纵向',
        fullscreen: '全屏',
        exitFullscreen: '退出全屏',
        fullscreenFailed: '无法进入全屏，请使用浏览器允许全屏的方式打开页面。',
        level: '级别',
        level_b: '初级',
        level_i: '中级',
        level_e: '高级',
        density: '雷密度',
        restart: '新一局',
        download: '下载离线版',
        time: '用时（秒）',
        remaining: '剩余点击数',
        boardLabel: '左键训练棋盘，点击没有雷的凸起格子',
        rules: '仅接受鼠标。雷的不透明度可在小游戏设置中调整。每次左键弹起只完成当前一个安全格，不自动展开；点到雷即失败。右键和双键不执行操作。',
    } },
    en: { local: {
        title: 'Left-click training',
        touchTitle: 'Multi-touch training',
        touchBoardLabel: 'Multi-touch training board. Touch raised cells without mines.',
        touchRules: 'Touchscreen only; each finger acts independently. Touch down opens one safe cell and starts timing on the first touch; moving and lifting do not open cells. Touching a mine ends the game. Drag with one finger to scroll; holding multiple fingers stops scrolling. One finger is allowed. Adjust mine opacity in minigame settings.',
        orientation: 'Board orientation',
        cellSize: 'Cell size',
        horizontal: 'Horizontal',
        vertical: 'Vertical',
        fullscreen: 'Fullscreen',
        exitFullscreen: 'Exit fullscreen',
        fullscreenFailed: 'Cannot enter fullscreen. Open this page in a browser that permits fullscreen.',
        level: 'Level',
        level_b: 'Beginner',
        level_i: 'Intermediate',
        level_e: 'Expert',
        density: 'Mine density',
        restart: 'New game',
        download: 'Download offline',
        time: 'Time (seconds)',
        remaining: 'Clicks left',
        boardLabel: 'Left-click training board. Click raised cells without mines.',
        rules: 'Mouse only. Adjust mine opacity in minigame settings. Each left-button release opens just one safe cell; hitting a mine ends the game. Right clicks and chords have no effect.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.touch-fullscreen {
    box-sizing: border-box;
    width: 100vw;
    height: 100dvh;
    padding: 0;
    gap: 0;
    grid-template-rows: auto minmax(0, 1fr);
    grid-auto-rows: auto;
    overflow: hidden;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
}

.touch-fullscreen > .training-scroll {
    min-height: 0;
    height: 100%;
    overscroll-behavior: contain;
}
</style>
