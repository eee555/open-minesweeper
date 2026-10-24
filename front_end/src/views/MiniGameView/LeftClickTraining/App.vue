<template>
    <section class="training-page" :aria-label="t('local.title')" :data-phase="phase" data-cy="training-game">
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
            <a v-if="!offline" class="base-button base-button--default base-button--size-default training-download" :href="offlineDownloadUrl" :download="offlineDownloadFilename" data-cy="training-download">{{ t('local.download') }}</a>
        </div>
        <MiniGameFrame :restart-label="t('local.restart')" @restart="restart">
            <template #remaining>
                <div role="group" :aria-label="t('local.remaining')" :title="t('local.remaining')">
                    <Counter :value="replay.frame.value?.remaining ?? remaining" :fixed="0" :digits="3" :size="minigameSettings.cellSize" data-cy="training-remaining" />
                </div>
            </template>
            <template #time>
                <div role="group" :aria-label="t('local.time')" :title="t('local.time')">
                    <Counter :value="(replay.frame.value?.timeMs ?? elapsed) / 1000" :fixed="3" :digits="3" :size="minigameSettings.cellSize" data-cy="training-time" />
                </div>
            </template>
            <MiniGameBoard
                :key="round" :board="replay.frame.value?.board ?? board" :size="minigameSettings.cellSize" :foreground-opacity="minigameSettings.leftClickMineOpacity" :disabled="phase === 'won' || phase === 'lost'"
                :record-mouse="replay.data.value === null" :cursor-position="replay.frame.value?.cursor" :replay-press="replay.frame.value?.pressed ?? null"
                :label="t('local.boardLabel')" @action="onAction" @record="recorder.capture($event)"
            >
                <template #overlay>
                    <ReplayTrace v-if="replay.data.value && replay.frame.value" :replay="replay.data.value" :event-index="replay.frame.value.eventIndex" />
                </template>
            </MiniGameBoard>
        </MiniGameFrame>
        <slot name="result-actions" />
        <template v-if="replay.data.value && replay.frame.value">
            <ReplayControls :playback="replay.playback" :position-ms="replay.frame.value.timeMs" />
            <ReplayAnalysis :replay="replay.data.value" game="left-click" @preview="replay.hover" />
        </template>
        <p class="text text-small">
            {{ t('local.rules') }}
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/components/MiniGame/training.css';

import { Counter } from '@putianyi888/vue3-minesweeper-board';
import { useRafFn } from '@vueuse/core';
import { computed, ref, shallowRef, useId, watch } from 'vue';
import type { VNode } from 'vue';
import { useI18n } from 'vue-i18n';

import MiniGameBoard from '@/components/MiniGame/Board.vue';
import MiniGameFrame from '@/components/MiniGame/Frame.vue';
import ReplayAnalysis from '@/components/MiniGame/ReplayAnalysis.vue';
import ReplayControls from '@/components/MiniGame/ReplayControls.vue';
import ReplayTrace from '@/components/MiniGame/ReplayTrace.vue';
import type { ClassicMouseAction } from '@/utils/classicMouse';
import { offlineDownloadFilename, offlineDownloadUrl } from '@/utils/minigame/games';
import { saveMinigameResult } from '@/utils/minigame/history';
import { leftClickModes, LeftClickTraining, trainingDensities, trainingLevels } from '@/utils/minigame/leftClickTraining';
import { TrainingReplayRecorder } from '@/utils/minigame/replay';
import type { TrainingRecording } from '@/utils/minigame/replay';
import { minigameSettings } from '@/utils/minigame/settings';
import { useTrainingReplay } from '@/utils/minigame/useTrainingReplay';

defineProps({ offline: { type: Boolean, default: false } });
const emit = defineEmits<{ completed: [rankingKey: string, scoreMs: number, replay: TrainingRecording]; reset: [] }>();
defineSlots<{ 'result-actions'?: () => VNode[] }>();
const level = ref<typeof trainingLevels[number]['key']>('b');
const levelGroupName = useId();
const density = ref<typeof trainingDensities[number]['value']>(50);
const mode = computed(() => {
    const selected = leftClickModes.find((item) => item.key === level.value && item.density === density.value);
    if (selected === undefined) throw new Error('Unknown left-click training mode');
    return selected;
});
let game = new LeftClickTraining(mode.value);
const board = shallowRef(game.board);
const phase = ref(game.phase);
const remaining = ref(game.remainingSafe);
const elapsed = ref(0);
const round = ref(0);
let recorder = new TrainingReplayRecorder({ game: 'left-click', mode: game.mode }, board.value);
const replay = useTrainingReplay();

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
    recorder = new TrainingReplayRecorder({ game: 'left-click', mode: game.mode }, board.value);
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
        void saveMinigameResult({ game: 'left-click', mode: game.mode, scoreMs: elapsed.value, replay: recording.recording });
        emit('completed', game.mode.rankingKey, elapsed.value, recording.recording);
    }
    if (game.phase === 'playing') resume();
    else pause();
}

watch(mode, restart);

const i18nMessages = {
    'zh-cn': { local: {
        title: '左键训练',
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
        rules: '雷的不透明度可在小游戏设置中调整。每次左键弹起只完成当前一个安全格，不自动展开；点到雷即失败。右键和双键不执行操作。',
    } },
    en: { local: {
        title: 'Left-click training',
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
        rules: 'Adjust mine opacity in minigame settings. Each left-button release opens just one safe cell; hitting a mine ends the game. Right clicks and chords have no effect.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

