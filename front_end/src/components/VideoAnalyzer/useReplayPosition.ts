import type { VideoActionStateRecorder } from 'ms-toollib';
import { shallowRef, toValue, watch } from 'vue';
import type { MaybeRefOrGetter, ShallowRef } from 'vue';

import { readReplayCursor } from './replayCursor';
import type { CursorPosition } from './replayCursor';
import type { ReplayVideo } from './replayParser';

export { readReplayCursor } from './replayCursor';
export type { CursorPosition } from './replayCursor';

export function useReplayPosition(video: MaybeRefOrGetter<ReplayVideo | null>, currentMs: MaybeRefOrGetter<number>): { gameBoard: ShallowRef<number[][] | null>; probabilityBoard: ShallowRef<number[][] | null>; mouseState: ShallowRef<number>; currentEventIndex: ShallowRef<number | null>; cursorPosition: ShallowRef<CursorPosition | null>; selectKeyframe: (index: number) => void; clearKeyframe: () => void } {
    const gameBoard = shallowRef<number[][] | null>(null);
    const probabilityBoard = shallowRef<number[][] | null>(null);
    const currentEventIndex = shallowRef<number | null>(null);
    const cursorPosition = shallowRef<CursorPosition | null>(null);
    const mouseState = shallowRef(0);
    const keyframeIndex = shallowRef<number | null>(null);
    let timePosition: { replay: ReplayVideo; ms: number; eventIndex: number } | null = null;
    function clearKeyframe() {
        keyframeIndex.value = null;
    }
    watch([() => toValue(video), () => toValue(currentMs)], clearKeyframe, { flush: 'sync' });
    watch([() => toValue(video), () => toValue(currentMs), keyframeIndex], ([replay, ms, selectedIndex]) => {
        if (replay === null) {
            timePosition = null;
            gameBoard.value = null;
            probabilityBoard.value = null;
            currentEventIndex.value = null;
            cursorPosition.value = null;
            mouseState.value = 0;
            return;
        }
        // Infinity includes the final event even when its time offset rounds below the boundary.
        replay.current_time = ms >= replay.rtime_ms ? Infinity : ms / 1000;
        if (timePosition?.replay !== replay || timePosition.ms !== ms) timePosition = { replay, ms, eventIndex: replay.current_event_id };
        if (selectedIndex === null) {
            // Reassigning an unchanged time does not undo an event-index override.
            if (replay.current_event_id !== timePosition.eventIndex) replay.current_event_id = timePosition.eventIndex;
            gameBoard.value = replay.game_board as number[][];
            probabilityBoard.value = replay.game_board_poss as number[][];
        } else {
            // The event setter does not synchronize time in ms-toollib 1.5.19.
            replay.current_event_id = selectedIndex;
            const records = replay.events as VideoActionStateRecorder[];
            try {
                const prior = records[selectedIndex].prior_game_board;
                try {
                    gameBoard.value = prior.game_board as number[][];
                    probabilityBoard.value = prior.poss as number[][];
                } finally {
                    prior.free();
                }
            } finally {
                for (const record of records) record.free();
            }
        }
        currentEventIndex.value = replay.current_event_id;
        cursorPosition.value = readReplayCursor(replay);
        mouseState.value = replay.mouse_state;
    }, { immediate: true });
    return { gameBoard,
        probabilityBoard,
        currentEventIndex,
        cursorPosition,
        mouseState,
        selectKeyframe: (index) => {
            keyframeIndex.value = index;
        },
        clearKeyframe };
}
