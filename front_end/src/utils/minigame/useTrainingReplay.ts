import { computed, shallowRef } from 'vue';
import type { ComputedRef, ShallowRef } from 'vue';

import { replayFrame } from './replay';
import type { AnyTrainingReplay, ReplayPosition, TrainingReplay, TrainingReplayFrame } from './replay';

import { usePlayback } from '@/components/VideoAnalyzer/usePlayback';
import type { PlaybackController } from '@/components/VideoAnalyzer/usePlayback';

export interface ReplayController<T, F> {
    data: ShallowRef<T | null>;
    preview: ShallowRef<ReplayPosition | null>;
    frame: ComputedRef<F | null>;
    playback: PlaybackController;
    hover: (position: ReplayPosition | null) => void;
    finish: (replay: T | null) => void;
    reset: () => void;
}

/** Share the playback clock and transient previews; each game supplies its frame decoder. */
export function useReplayController<T extends { durationMs: number }, F>(frameAt: (replay: T, position: ReplayPosition) => F): ReplayController<T, F> {
    const data: ShallowRef<T | null> = shallowRef(null);
    const preview = shallowRef<ReplayPosition | null>(null);
    const playback = usePlayback(() => data.value?.durationMs ?? 0);
    const frame = computed(() => (data.value === null ? null : frameAt(data.value, preview.value ?? { timeMs: playback.currentMs.value })));

    function hover(position: ReplayPosition | null) {
        if (position !== null && preview.value === null) playback.beginSeek();
        preview.value = position;
        if (position === null) playback.endSeek();
    }
    function finish(replay: T | null) {
        if (replay === null) return;
        hover(null);
        playback.pause();
        data.value = replay;
        playback.seek(replay.durationMs);
    }
    function reset() {
        hover(null);
        playback.pause();
        data.value = null;
    }
    return { data, preview, frame, playback, hover, finish, reset };
}

export function useTrainingReplay<T extends AnyTrainingReplay = TrainingReplay>(): ReplayController<T, TrainingReplayFrame> {
    return useReplayController<T, TrainingReplayFrame>(replayFrame);
}
