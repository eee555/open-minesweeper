<template>
    <section class="training-page" :aria-label="t('local.title')" :data-phase="phase" :data-replay="replayData !== null" data-cy="flag-chord-game">
        <div class="training-controls">
            <div class="checkbox-buttons" role="radiogroup" :aria-label="t('local.level')" data-cy="flag-chord-level">
                <label v-for="item in flagChordModes" :key="item.key" class="checkbox-button">
                    <input v-model="level" class="checkbox-button-input" type="radio" :name="levelGroupName" :value="item.key">
                    <span class="checkbox-button-content">{{ t(`local.level_${item.key}`) }}</span>
                </label>
            </div>
            <a v-if="!offline" class="base-button base-button--default base-button--size-default training-download" :href="offlineDownloadUrl" :download="offlineDownloadFilename" data-cy="flag-chord-download">{{ t('local.download') }}</a>
        </div>
        <MiniGameFrame :restart-label="t('local.restart')" @restart="restart">
            <template #remaining>
                <div role="group" :aria-label="t('local.remaining')" :title="t('local.remaining')">
                    <Counter :value="replay.frame.value?.remaining ?? remaining" :fixed="0" :digits="3" :size="minigameSettings.cellSize" data-cy="flag-chord-remaining" />
                </div>
            </template>
            <template #time>
                <div role="group" :aria-label="t('local.time')" :title="t('local.time')">
                    <Counter :value="(replay.frame.value?.timeMs ?? elapsed) / 1000" :fixed="3" :digits="3" :size="minigameSettings.cellSize" data-cy="flag-chord-time" />
                </div>
            </template>
            <MiniGameBoard
                :key="round" :board="replay.frame.value?.board ?? board" :size="minigameSettings.cellSize" :disabled="phase === 'won' || phase === 'lost'"
                :record-mouse="replay.data.value === null" :cursor-position="replay.frame.value?.cursor" :replay-press="replay.frame.value?.pressed ?? null"
                :label="t('local.boardLabel')" @action="onAction" @record="recorder.capture($event)"
            >
                <template #overlay>
                    <ReplayTrace v-if="replay.data.value && replay.frame.value" :replay="replay.data.value" :event-index="replay.frame.value.eventIndex" />
                </template>
            </MiniGameBoard>
        </MiniGameFrame>
        <slot name="resultActions" />
        <template v-if="replay.data.value && replay.frame.value">
            <ReplayControls :playback="replay.playback" :position-ms="replay.frame.value.timeMs" />
            <ReplayAnalysis :replay="replay.data.value" game="flag-chord" @preview="replay.hover" />
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
import type { PropType, VNode } from 'vue';
import { useI18n } from 'vue-i18n';

import MiniGameBoard from '@/components/MiniGame/Board.vue';
import MiniGameFrame from '@/components/MiniGame/Frame.vue';
import ReplayAnalysis from '@/components/MiniGame/ReplayAnalysis.vue';
import ReplayControls from '@/components/MiniGame/ReplayControls.vue';
import ReplayTrace from '@/components/MiniGame/ReplayTrace.vue';
import type { ClassicMouseAction } from '@/utils/classicMouse';
import { flagChordModes, FlagChordTraining } from '@/utils/minigame/flagChordTraining';
import { offlineDownloadFilename, offlineDownloadUrl } from '@/utils/minigame/games';
import { saveMinigameResult } from '@/utils/minigame/history';
import { TrainingReplayRecorder } from '@/utils/minigame/replay';
import type { TrainingRecording, TrainingReplay } from '@/utils/minigame/replay';
import { minigameSettings } from '@/utils/minigame/settings';
import { useTrainingReplay } from '@/utils/minigame/useTrainingReplay';

const props = defineProps({ offline: { type: Boolean, default: false }, replayData: { type: Object as PropType<Extract<TrainingReplay, { game: 'flag-chord' }> | null>, default: null } });
const emit = defineEmits<{ completed: [rankingKey: string, scoreMs: number, replay: TrainingRecording]; reset: [] }>();
defineSlots<{ resultActions?: () => VNode[] }>();
const level = ref<typeof flagChordModes[number]['key']>(props.replayData?.mode.key ?? 'b');
const levelGroupName = useId();
const mode = computed(() => {
    const selected = flagChordModes.find((item) => item.key === level.value);
    if (selected === undefined) throw new Error('Unknown flag-and-chord training mode');
    return selected;
});
let game = new FlagChordTraining(mode.value, undefined, props.replayData?.initialBoard);
const board = shallowRef(game.board);
const phase = ref(game.phase);
const remaining = ref(game.remaining);
const elapsed = ref(0);
const round = ref(0);
let recorder = new TrainingReplayRecorder({ game: 'flag-chord', mode: game.mode }, board.value);
const replay = useTrainingReplay();
const { pause, resume } = useRafFn(() => {
    elapsed.value = game.elapsedMs(performance.now());
}, { immediate: false });

function restart() {
    pause();
    replay.reset();
    game = new FlagChordTraining(mode.value);
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remaining;
    elapsed.value = 0;
    recorder = new TrainingReplayRecorder({ game: 'flag-chord', mode: game.mode }, board.value);
    round.value++;
    emit('reset');
}

function onAction(action: ClassicMouseAction, row: number, column: number, now: number) {
    if (!game.act(action, row, column, now)) return;
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remaining;
    elapsed.value = game.elapsedMs(now);
    const recording = recorder.update(now, phase.value, elapsed.value);
    replay.finish(recording);
    if (game.phase === 'won' && recording !== null) {
        void saveMinigameResult({ game: 'flag-chord', mode: game.mode, scoreMs: elapsed.value, replay: recording.recording });
        emit('completed', `flag-chord-${game.mode.key}-v1`, elapsed.value, recording.recording);
    }
    if (game.phase === 'playing') resume();
    else pause();
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
        title: '标双训练',
        level: '级别',
        level_b: '初级',
        level_i: '中级',
        restart: '新一局',
        download: '下载离线版',
        time: '用时（秒）',
        remaining: '剩余题目',
        boardLabel: '标双训练棋盘，右键标雷后对数字进行左右双键操作',
        rules: '初级 4 题，中级 15 题，数字均为 1。雷始终可见，普通左键无效果。右键插旗或取消；双键在首次弹起时触发。周围恰好一面旗时判题：旗位错误则失败，正确则完成；其余双键无效果。',
    } },
    en: { local: {
        title: 'Flag-and-chord training',
        level: 'Level',
        level_b: 'Beginner',
        level_i: 'Intermediate',
        restart: 'New game',
        download: 'Download offline',
        time: 'Time (seconds)',
        remaining: 'Questions left',
        boardLabel: 'Flag-and-chord board. Right-click mines, then press both mouse buttons on each number.',
        rules: 'Beginner has 4 questions; Intermediate has 15. Every number is 1 and mines are visible. Single left clicks do nothing. Right-click to toggle flags; a chord triggers on the first button release. With exactly one adjacent flag, a correct flag completes the question and a wrong flag loses. Other chords do nothing.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
