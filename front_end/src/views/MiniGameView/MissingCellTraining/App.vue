<template>
    <section class="training-page" :aria-label="t('local.title')" :data-phase="phase" :data-replay="replayData !== null" data-cy="missing-cell-game">
        <div class="training-controls">
            <div class="checkbox-buttons" role="radiogroup" :aria-label="t('local.level')" data-cy="missing-cell-level">
                <label v-for="item in missingCellModes" :key="item.key" class="checkbox-button">
                    <input v-model="level" class="checkbox-button-input" type="radio" :name="levelGroupName" :value="item.key">
                    <span class="checkbox-button-content">{{ t(`local.level_${item.key}`) }}</span>
                </label>
            </div>
            <a v-if="!offline" class="base-button base-button--default base-button--size-default training-download" :href="offlineDownloadUrl" :download="offlineDownloadFilename" data-cy="missing-cell-download">{{ t('local.download') }}</a>
        </div>
        <MiniGameFrame :restart-label="t('local.restart')" @restart="restart">
            <template #remaining>
                <div role="group" :aria-label="t('local.remaining')" :title="t('local.remaining')">
                    <Counter :value="previewRemaining" :fixed="0" :digits="3" :size="minigameSettings.cellSize" data-cy="missing-cell-remaining" />
                </div>
            </template>
            <template #time>
                <div role="group" :aria-label="t('local.time')" :title="t('local.time')">
                    <Counter :value="(preview?.timeMs ?? elapsed) / 1000" :fixed="3" :digits="3" :size="minigameSettings.cellSize" data-cy="missing-cell-time" />
                </div>
            </template>
            <MiniGameBoard
                :key="round" :board="preview?.board ?? board" :highlight="preview?.target ?? null" :size="minigameSettings.cellSize" :disabled="phase === 'won' || phase === 'lost'"
                :label="t('local.boardLabel')" @action="onAction"
            />
        </MiniGameFrame>
        <slot name="resultActions" />
        <TrainingResults v-if="phase === 'won'" :times-ms="roundTimes" @hover="hoveredRound = $event" />
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

import TrainingResults from './Results.vue';

import MiniGameBoard from '@/components/MiniGame/Board.vue';
import MiniGameFrame from '@/components/MiniGame/Frame.vue';
import type { ClassicMouseAction } from '@/utils/classicMouse';
import { offlineDownloadFilename, offlineDownloadUrl } from '@/utils/minigame/games';
import { saveMinigameResult } from '@/utils/minigame/history';
import { missingCellModes, missingCellRounds, MissingCellTraining, reviewMissingCellRound } from '@/utils/minigame/missingCellTraining';
import type { MissingCellRoundResult } from '@/utils/minigame/missingCellTraining';
import { encodeMissingCellRecording } from '@/utils/minigame/recording';
import type { MissingCellRecording } from '@/utils/minigame/recording';
import type { MissingCellReplay } from '@/utils/minigame/review';
import { minigameSettings } from '@/utils/minigame/settings';

const props = defineProps({ offline: { type: Boolean, default: false }, replayData: { type: Object as PropType<MissingCellReplay | null>, default: null } });
const emit = defineEmits<{ completed: [rankingKey: string, scoreMs: number, replay: MissingCellRecording]; reset: [] }>();
defineSlots<{ resultActions?: () => VNode[] }>();
const level = ref<typeof missingCellModes[number]['key']>(props.replayData?.mode.key ?? 'b');
const levelGroupName = useId();
const mode = computed(() => {
    const selected = missingCellModes.find((item) => item.key === level.value);
    if (selected === undefined) throw new Error('Unknown missing-cell training mode');
    return selected;
});
let game = new MissingCellTraining(mode.value);
const board = shallowRef(game.board);
const phase = ref(game.phase);
const remaining = ref(game.remaining);
const elapsed = ref(0);
const round = ref(0);
const roundResults = shallowRef<readonly MissingCellRoundResult[]>([]);
const roundTimes = computed(() => roundResults.value.map((result) => result.timeMs));
const hoveredRound = ref<number | null>(null);
const preview = computed(() => {
    const result = hoveredRound.value === null ? undefined : roundResults.value[hoveredRound.value];
    return result === undefined ? null : reviewMissingCellRound(result);
});
const previewRemaining = computed(() => (preview.value === null || hoveredRound.value === null ? remaining.value : missingCellRounds - hoveredRound.value));
const { pause, resume } = useRafFn(() => {
    elapsed.value = game.elapsedMs(performance.now());
}, { immediate: false });

function restart() {
    pause();
    game = new MissingCellTraining(mode.value);
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remaining;
    elapsed.value = 0;
    round.value++;
    roundResults.value = [];
    hoveredRound.value = null;
    emit('reset');
}

function onAction(action: ClassicMouseAction, row: number, column: number) {
    if (action !== 'left') return;
    const now = performance.now();
    if (!game.trigger(row, column, now)) return;
    board.value = game.board;
    phase.value = game.phase;
    remaining.value = game.remaining;
    elapsed.value = game.elapsedMs(now);
    roundResults.value = game.roundResults;
    if (game.phase === 'won') {
        const recording = encodeMissingCellRecording(game.mode, roundResults.value);
        void saveMinigameResult({ game: 'missing-cell', mode: game.mode, scoreMs: elapsed.value, ...recording });
        emit('completed', `missing-cell-${game.mode.key}-v1`, elapsed.value, recording);
    }
    if (game.phase === 'playing') resume();
    else pause();
}

watch(mode, restart);
watch(() => props.replayData, (data, previous) => {
    if (data === null) {
        if (roundResults.value === previous?.rounds) restart();
        return;
    }
    const final = data.rounds.at(-1);
    if (final === undefined) return;
    pause();
    roundResults.value = data.rounds;
    hoveredRound.value = null;
    board.value = reviewMissingCellRound(final, true).board;
    remaining.value = 0;
    elapsed.value = data.durationMs;
    phase.value = 'won';
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        title: '漏雷训练',
        level: '级别',
        level_b: '初级',
        level_i: '中级',
        level_e: '高级',
        restart: '新一轮',
        download: '下载离线版',
        time: '用时（秒）',
        remaining: '剩余题目',
        boardLabel: '漏雷训练棋盘，找出唯一未打开的安全格',
        rules: '每局所有安全格均已打开，唯独漏开一格。目标周围不会有 0，目标本身可能是 0。雷保持隐藏，可见数字足以唯一确定目标。点击雷则整轮失败；右键、双键及已打开格无效果。连续完成 10 局，期间计时不停；切换级别会重开。',
    } },
    en: { local: {
        title: 'Missing cell training',
        level: 'Level',
        level_b: 'Beginner',
        level_i: 'Intermediate',
        level_e: 'Expert',
        restart: 'New run',
        download: 'Download offline',
        time: 'Time (seconds)',
        remaining: 'Boards left',
        boardLabel: 'Missing cell board. Find the only unopened safe cell.',
        rules: 'Every safe cell except one is open. The target has no adjacent zero cells but may itself be zero. Mines stay hidden, and the visible clues uniquely identify the target. Hitting a mine ends the run; right clicks, chords and clicks on open cells do nothing. Complete 10 boards with one continuous timer. Changing level starts a new run.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
