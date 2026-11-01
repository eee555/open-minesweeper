import { ref, shallowRef } from 'vue';
import type { ComponentOptions, ComponentPublicInstance } from 'vue';

import { defaultAnalyzerConfig } from '@/components/VideoAnalyzer/config';
import type { CounterEvent } from '@/components/VideoAnalyzer/counter';
import { useAnalyzerState } from '@/components/VideoAnalyzer/useAnalyzerState';
import type { AnalyzerState } from '@/components/VideoAnalyzer/useAnalyzerState';
import { usePlayback } from '@/components/VideoAnalyzer/usePlayback';
import { usePreparedAnalysis } from '@/components/VideoAnalyzer/usePreparedAnalysis';

export function createAnalyzerTestState(overrides: Partial<AnalyzerState> = {}): AnalyzerState {
    const config = overrides.config ?? ref(defaultAnalyzerConfig());
    const counterEvents = overrides.counterEvents ?? shallowRef<CounterEvent[]>([]);
    const playback = overrides.playback ?? usePlayback(1000);
    const analysis = usePreparedAnalysis(config, counterEvents, playback.durationMs);
    return {
        config,
        counterEvents,
        playback,
        ...analysis,
        probabilityColorScheme: ref({ colors: ['#000', '#fff'], thresholds: [50] }),
        exporting: ref(false),
        frame: shallowRef({ board: null, globalBoard: null, probabilityBoard: null, cursorPosition: null, mouseState: 0, currentEventIndex: null, nativeCellSize: null }),
        traceEvents: shallowRef([]),
        timeWindow: ref({ startMs: 0, endMs: playback.durationMs.value }),
        keyframeNavigation: null,
        loading: ref(false),
        errorMessage: ref(''),
        filename: ref('replay'),
        createExportVideo: () => { throw new Error('Test replay is not loaded'); },
        ...overrides,
    };
}

export function captureAnalyzerState(capture: (state: AnalyzerState) => void): ComponentOptions {
    return {
        mounted(this: ComponentPublicInstance) {
            const element: unknown = this.$el;
            if (element instanceof HTMLElement && element.classList.contains('video-analyzer-board')) capture(useAnalyzerState());
        },
    };
}
