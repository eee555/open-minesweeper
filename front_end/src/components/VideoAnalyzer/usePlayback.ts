import { useRafFn } from '@vueuse/core';
import { computed, readonly, ref, toValue, watch } from 'vue';
import type { ComputedRef, MaybeRefOrGetter, Ref } from 'vue';

export type LoopMode = 'none' | 'range' | 'all';

export interface PlaybackController {
    currentMs: Readonly<Ref<number>>;
    durationMs: ComputedRef<number>;
    isPlaying: Readonly<Ref<boolean>>;
    playbackRate: Readonly<Ref<number>>;
    loopMode: Readonly<Ref<LoopMode>>;
    canPlay: ComputedRef<boolean>;
    rangeStartMs: Readonly<Ref<number>>;
    rangeEndMs: Readonly<Ref<number>>;
    play: () => void;
    pause: () => void;
    seek: (ms: number) => void;
    setPlaybackRate: (rate: number) => void;
    setLoopMode: (mode: LoopMode) => void;
    beginSeek: () => void;
    endSeek: () => void;
    setRangeStart: () => void;
    setRangeEnd: () => void;
}

export function usePlayback(duration: MaybeRefOrGetter<number> = 0): PlaybackController {
    const durationMs = computed(() => {
        const value = toValue(duration);
        return Number.isFinite(value) ? Math.max(0, value) : 0;
    });
    const currentMs = ref(0);
    const playbackRate = ref(1);
    const loopMode = ref<LoopMode>('none');
    const rangeStartMs = ref(0);
    const rangeEndMs = ref(durationMs.value);
    const canPlay = computed(() => durationMs.value > 0 && !(loopMode.value === 'range' && rangeStartMs.value === rangeEndMs.value));
    let isSeeking = false;
    let startedAt = 0;
    let startedFrom = 0;

    const { isActive: isPlaying, pause: stopClock, resume: startClock } = useRafFn(({ timestamp }) => {
        updateTime(timestamp);
    }, { immediate: false });

    function syncAnchor(now: number) {
        startedAt = now;
        startedFrom = currentMs.value;
    }

    function rangeTime(ms: number) {
        return ms < rangeStartMs.value || ms > rangeEndMs.value ? rangeStartMs.value : ms;
    }

    function updateTime(now: number) {
        if (isSeeking) return;
        const totalMs = durationMs.value;
        if (!canPlay.value) {
            if (totalMs <= 0) currentMs.value = 0;
            stopClock();
            return;
        }
        const nextMs = startedFrom + Math.max(0, now - startedAt) * playbackRate.value;
        if (loopMode.value === 'range') {
            currentMs.value = rangeTime(nextMs);
            if (currentMs.value !== nextMs) syncAnchor(now);
        } else if (loopMode.value === 'all') {
            currentMs.value = nextMs % totalMs;
            if (nextMs >= totalMs) syncAnchor(now);
        } else {
            currentMs.value = Math.min(totalMs, nextMs);
            if (nextMs >= totalMs) stopClock();
        }
    }

    function play() {
        if (isPlaying.value || !canPlay.value) return;
        if (loopMode.value === 'range') currentMs.value = rangeTime(currentMs.value);
        else if (currentMs.value >= durationMs.value) currentMs.value = 0;
        syncAnchor(performance.now());
        startClock();
    }

    function pause() {
        if (isPlaying.value) updateTime(performance.now());
        stopClock();
    }

    function seek(ms: number) {
        if (!Number.isFinite(ms)) throw new RangeError('Playback time must be finite');
        const boundedMs = Math.min(durationMs.value, Math.max(0, ms));
        currentMs.value = isPlaying.value && loopMode.value === 'range' ? rangeTime(boundedMs) : boundedMs;
        syncAnchor(performance.now());
    }

    function beginSeek() {
        if (isSeeking || durationMs.value <= 0) return;
        if (isPlaying.value) updateTime(performance.now());
        isSeeking = true;
    }

    function endSeek() {
        if (!isSeeking) return;
        isSeeking = false;
        syncAnchor(performance.now());
    }

    function setPlaybackRate(rate: number) {
        if (!Number.isFinite(rate) || rate <= 0) throw new RangeError('Playback rate must be finite and positive');
        const now = performance.now();
        // Account for elapsed time at the old rate before changing the anchor.
        if (isPlaying.value) updateTime(now);
        playbackRate.value = rate;
        syncAnchor(now);
    }

    function setLoopMode(mode: LoopMode) {
        if (isPlaying.value) return;
        loopMode.value = mode;
    }

    function setRangeStart() {
        if (isPlaying.value && loopMode.value === 'range') return;
        rangeStartMs.value = currentMs.value;
        if (rangeStartMs.value > rangeEndMs.value) rangeEndMs.value = durationMs.value;
    }

    function setRangeEnd() {
        if (isPlaying.value && loopMode.value === 'range') return;
        rangeEndMs.value = currentMs.value;
        if (rangeEndMs.value < rangeStartMs.value) rangeStartMs.value = 0;
    }

    watch(durationMs, () => {
        rangeStartMs.value = 0;
        rangeEndMs.value = durationMs.value;
        const now = performance.now();
        if (isPlaying.value) updateTime(now);
        currentMs.value = Math.min(currentMs.value, durationMs.value);
        if (!canPlay.value || (loopMode.value === 'none' && currentMs.value >= durationMs.value)) stopClock();
        syncAnchor(now);
    }, { flush: 'sync' });

    return {
        currentMs: readonly(currentMs),
        durationMs,
        isPlaying,
        playbackRate: readonly(playbackRate),
        loopMode: readonly(loopMode),
        canPlay,
        rangeStartMs: readonly(rangeStartMs),
        rangeEndMs: readonly(rangeEndMs),
        play,
        pause,
        seek,
        setPlaybackRate,
        setLoopMode,
        beginSeek,
        endSeek,
        setRangeStart,
        setRangeEnd,
    };
}
