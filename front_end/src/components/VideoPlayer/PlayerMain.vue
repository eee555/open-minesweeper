<template>
    <div class="player-main" :class="outerBorderClass">
        <div class="player-main__counter-bar" :class="innerBorderClass">
            <Counter :value="video.mine_num - video.flag" :digits="3" :size="18" />
            <span class="player-main__counter-spacer" />
            <Counter :value="currentMs / 1000" :fixed="3" :digits="3" :size="18" />
        </div>
        <div :class="innerBorderClass">
            <MinesweeperBoard :board="video.game_board" :size="size" :cursor-position="cursorPosition">
                <template #background>
                    <BoardBackground :board="backgroundBoard" />
                </template>
                <template v-if="showProbability" #default>
                    <BoardProbability :board="probabilityBoard" :color="probabilityColor" />
                </template>
            </MinesweeperBoard>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-minesweeper-board/style.css';

import { BoardBackground, BoardProbability, Counter, innerBorderClass, MinesweeperBoard, outerBorderClass } from '@putianyi888/vue3-minesweeper-board';
import type { PropType } from 'vue';
import { computed } from 'vue';

import { PiecewiseColorScheme } from '@/utils/colors';
import type { AnyVideo } from '@/utils/fileIO';
import { replayPressedBackground } from '@/utils/replayBoardPress';

interface CursorPosition {
    rowIndex: number;
    columnIndex: number;
}

const props = defineProps({
    video: { type: Object as PropType<AnyVideo>, required: true },
    currentMs: { type: Number, required: true },
    cursorPosition: { type: Object as PropType<CursorPosition>, default: undefined },
    showProbability: { type: Boolean, default: true },
    size: { type: Number, default: 24 },
    probabilityColorScheme: {
        type: PiecewiseColorScheme,
        default: () => new PiecewiseColorScheme([], []),
    },
});

const backgroundBoard = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-meaningless-void-operator
    void props.currentMs;
    return replayPressedBackground(props.video.game_board as number[][], props.video.mouse_state, props.cursorPosition);
});

const probabilityBoard = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-meaningless-void-operator
    void props.currentMs;
    return props.video.game_board_poss as number[][];
});

function probabilityColor(value: number) {
    return props.probabilityColorScheme.getColor(value * 100);
}
</script>

<style scoped>
.player-main {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
}

.player-main__counter-bar {
    display: flex;
    flex-direction: row;
    align-items: center;
    align-self: stretch;
    gap: 4px;
}

.player-main__counter-spacer {
    flex: 1 1 0;
    min-width: 0;
}
</style>
