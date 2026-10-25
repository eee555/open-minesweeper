import { computed, shallowRef } from 'vue';
import type { ComputedRef, ShallowRef } from 'vue';

import { replayFrame } from './replay';
import type { AnyTrainingReplay, ReplayPosition, TrainingReplay, TrainingReplayFrame } from './replay';

import { usePlayback } from '@/components/VideoAnalyzer/usePlayback';
import type { PlaybackController } from '@/components/VideoAnalyzer/usePlayback';

export interface TrainingReplayController<T extends AnyTrainingReplay = TrainingReplay> {
    data: ShallowRef<T | null>;
    preview: ShallowRef<ReplayPosition | null>;
    frame: ComputedRef<TrainingReplayFrame | null>;
    playback: PlaybackController;
    hover: (position: ReplayPosition | null) => void;
    finish: (replay: T | null) => void;
    reset: () => void;
}

/** All minigames share playback defaults and transient chart previews. */
export function useTrainingReplay<T extends AnyTrainingReplay = TrainingReplay>(): TrainingReplayController<T> {
    const data: ShallowRef<T | null> = shallowRef(null);
    const preview = shallowRef<ReplayPosition | null>(null);
    const playback = usePlayback(() => data.value?.durationMs ?? 0);
    const frame = computed(() => (data.value === null ? null : replayFrame(data.value, preview.value ?? { timeMs: playback.currentMs.value })));

    function hover(position: ReplayPosition | null) {
        if (position !== null && preview.value === null) playback.beginSeek();
        preview.value = position;
        if (position === null) playback.endSeek();
    }
    function finish(replay: T | null) {
        if (replay === null) return;
        data.value = replay;
        playback.pause();
        playback.seek(replay.durationMs);
    }
    function reset() {
        hover(null);
        playback.pause();
        data.value = null;
    }
    return { data, preview, frame, playback, hover, finish, reset };
}
