import { inject, provide } from 'vue';
import type { InjectionKey, Ref } from 'vue';

import type { BoardFrame } from './board';
import type { AnalyzerConfig } from './config';
import type { CounterEvent, PreparedCounter } from './counter';
import type { PreparedCustomEvent } from './customEvents';
import type { KeyframeNavigation } from './keyframes';
import type { ReplayMouseTraceEvent } from './mouseTrace';
import type { ReplayVideo } from './replayParser';
import type { TimeWindow } from './timeline';
import type { PlaybackController } from './usePlayback';

import type { PiecewiseColorSchemeInterface } from '@/utils/colors';

export interface AnalyzerState {
    config: Ref<AnalyzerConfig>;
    probabilityColorScheme: Ref<PiecewiseColorSchemeInterface>;
    exporting: Ref<boolean>;
    frame: Readonly<Ref<BoardFrame>>;
    playback: PlaybackController;
    keyframeNavigation: KeyframeNavigation | null;
    counterEvents: Readonly<Ref<CounterEvent[]>>;
    preparedCounters: Readonly<Ref<Map<string, PreparedCounter>>>;
    preparedEvents: Readonly<Ref<Map<string, PreparedCustomEvent>>>;
    traceEvents: Readonly<Ref<ReplayMouseTraceEvent[]>>;
    timeWindow: Ref<TimeWindow>;
    loading: Readonly<Ref<boolean>>;
    errorMessage: Readonly<Ref<string>>;
    filename: Readonly<Ref<string>>;
    createExportVideo: () => ReplayVideo;
}

const analyzerStateKey: InjectionKey<AnalyzerState> = Symbol('AnalyzerState');

export function provideAnalyzerState(state: AnalyzerState): void {
    provide(analyzerStateKey, state);
}

export function useAnalyzerState(): AnalyzerState {
    const state = inject(analyzerStateKey);
    if (state === undefined) throw new Error('Analyzer state must be provided by a VideoAnalyzer instance');
    return state;
}
