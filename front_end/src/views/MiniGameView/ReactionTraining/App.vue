<template>
    <section class="training-page" :data-phase="phase" :data-replay="replayData !== null" data-cy="reaction-training">
        <div class="training-controls">
            <div class="checkbox-buttons" role="radiogroup" :aria-label="t('prop.level')">
                <label v-for="item in levels" :key="item.key" class="checkbox-button">
                    <input v-model="level" type="radio" class="checkbox-button-input" :name="levelId" :value="item.key">
                    <span class="checkbox-button-content">{{ t(`level.${item.key}`) }} · {{ item.target }}</span>
                </label>
            </div>
            <label>{{ t('local.probability') }}
                <select v-model.number="probability" data-cy="reaction-probability"><option :value="0.25">25%</option><option :value="0.5">50%</option></select>
            </label>
        </div>
        <MiniGameFrame :restart-label="t('button.newGame')" @restart="restart">
            <template #remaining>
                <Counter :value="frame?.remaining ?? target - reactions" :fixed="0" :digits="3" :size="cellSize" :title="t('local.remaining')" data-cy="reaction-remaining" />
            </template>
            <template #time>
                <Counter :value="(frame?.timeMs ?? elapsed) / 1000" :fixed="3" :digits="3" :size="cellSize" :title="t('timeSeconds')" data-cy="reaction-time" />
            </template>
            <MiniGameBoard :key="round" :board="frame?.board ?? board" :size="cellSize" :disabled="phase === 'won' || phase === 'lost'" :record-mouse="replay === null" :replay-press="frame?.pressed ?? null" :label="t('minigame.reaction')" @record="recorder.capture($event)" @action="onAction" />
        </MiniGameFrame>
        <slot name="resultActions" />
        <template v-if="replay && frame">
            <ReplayControls :playback="playback" :position-ms="frame.timeMs" />
            <ReactionAnalysis :samples="replay.samples" @preview="hover($event === null ? null : { timeMs: $event })" />
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
import ReactionAnalysis from '@/components/MiniGame/ReactionAnalysis.vue';
import ReplayControls from '@/components/MiniGame/ReplayControls.vue';
import type { ClassicMouseAction } from '@/utils/classicMouse';
import { saveMinigameResult } from '@/utils/minigame/history';
import { reactionFrame, ReactionRecorder, rebuildReactionReplay } from '@/utils/minigame/reactionRecording';
import type { ReactionFrame, ReactionRecording, ReactionReplay } from '@/utils/minigame/reactionRecording';
import { reactionLevels as levels, reactionModes } from '@/utils/minigame/reactionTraining';
import { minigameSettings } from '@/utils/minigame/settings';
import { useReplayController } from '@/utils/minigame/useTrainingReplay';

const props = defineProps({ replayData: { type: Object as PropType<ReactionReplay | null>, default: null } });
const emit = defineEmits<{ completed: [rankingKey: string, scoreMs: number, recording: ReactionRecording]; reset: []; rankingChange: [key: string] }>();
defineSlots<{ resultActions?: () => VNode[] }>();
const levelId = useId();
const level = ref<typeof levels[number]['key']>(props.replayData?.mode.key ?? 'b');
const probability = ref((props.replayData?.mode.probability ?? 25) / 100);
const mode = computed(() => reactionModes.find((item) => item.key === level.value && item.probability === probability.value * 100) ?? reactionModes[0]);
const target = computed(() => mode.value.target);
const cellSize = computed(() => minigameSettings.value.cellSize);
let recorder = new ReactionRecorder(mode.value);
let { game } = recorder;
const board = shallowRef(game.board);
const phase = ref(game.phase);
const reactions = ref(0);
const elapsed = ref(0);
const round = ref(0);
const { data: replay, frame, playback, hover, finish: finishReplay, reset: resetReplay } = useReplayController<ReactionReplay, ReactionFrame>((data, position) => reactionFrame(data, position.timeMs));
const { pause, resume } = useRafFn(() => {
    elapsed.value = game.elapsedMs(performance.now());
}, { immediate: false });

function restart() {
    pause();
    resetReplay();
    recorder = new ReactionRecorder(mode.value);
    ({ game } = recorder);
    board.value = game.board;
    phase.value = game.phase;
    reactions.value = 0;
    elapsed.value = 0;
    round.value++;
    emit('reset');
}
function onAction(action: ClassicMouseAction, row: number, column: number, now: number) {
    if (action !== 'left' || replay.value !== null) return;
    const advanced = recorder.trigger(row, column, now);
    board.value = game.board;
    phase.value = game.phase;
    reactions.value = game.reactions;
    elapsed.value = game.elapsedMs(now);
    if (phase.value === 'playing') resume();
    else pause();
    if (advanced && phase.value === 'won') {
        const recording = recorder.finish();
        finishReplay(rebuildReactionReplay(mode.value, recording, elapsed.value));
        void saveMinigameResult({ game: 'reaction', mode: mode.value, scoreMs: elapsed.value, replay: recording });
        emit('completed', mode.value.rankingKey, elapsed.value, recording);
    }
}
watch(mode, (_mode, previous) => {
    if (previous !== undefined && !(props.replayData !== null && replay.value === props.replayData && props.replayData.mode.rankingKey === mode.value.rankingKey)) restart();
    emit('rankingChange', mode.value.rankingKey);
}, { immediate: true });
watch(() => props.replayData, (data, previous) => {
    if (data === null) {
        if (previous && replay.value === previous) restart();
        return;
    }
    pause();
    level.value = data.mode.key;
    probability.value = data.mode.probability / 100;
    finishReplay(data);
    phase.value = 'won';
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        probability: '下一格为雷的概率',
        remaining: '剩余反应次数',
        rules: '从任一端松开开始，随后只能沿该方向依数字前进，确定下一格为雷时跳过一格。重复点击已打开的格子或下方旗子无效果；点击已跳过的雷或其他错误位置即失败。每行首点不计反应次数，整场从首次松开连续计时，换行不停表。成功局自动保存本地历史，点击计数器重开。',
    } },
    en: { local: {
        probability: 'Next-cell mine probability',
        remaining: 'Reactions left',
        rules: 'Release at either end to start, then follow the numbers in that direction, skipping only a known mine. Clicking opened cells or the flag row has no effect; clicking a skipped mine or another wrong position loses. The first click of each line does not count as a reaction. Timing starts on the first release and continues across lines. Successful games save local history. Click the counters to restart.',
    } },
    es: { local: {
        probability: 'Probabilidad de que la casilla siguiente sea una mina',
        remaining: 'Reacciones restantes',
        rules: 'Suelta en cualquiera de los extremos para comenzar, luego sigue los números en esa dirección, saltando solo una mina conocida. Hacer clic en casillas abiertas o en la fila de banderas no tiene efecto; hacer clic en una mina saltada o en otra posición incorrecta pierde. El primer clic de cada línea no cuenta como reacción. El cronómetro comienza con la primera liberación y continúa entre líneas. Los juegos exitosos guardan el historial local. Haz clic en los contadores para reiniciar.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.training-page[data-phase='lost'] :deep(.training-frame) {
    outline: 2px solid var(--ui-color-danger);
}

.training-page[data-phase='won'] :deep(.training-frame) {
    outline: 2px solid var(--ui-color-success);
}
</style>
