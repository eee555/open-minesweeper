import { nextTick, ref, shallowRef, toValue } from 'vue';
import type { MaybeRefOrGetter, Ref } from 'vue';

import { AnalysisCancelled, createProgressReporter, initialAnalysisProgress, yieldToBrowser } from './analysisProgress';
import type { AnalysisProgressSnapshot, AnalysisStepKey, ProgressReport } from './analysisProgress';
import type { AnalyzerConfig } from './config';
import { readCounterEventsAsync, prepareCountersAsync } from './counter';
import type { CounterEvent, PreparedCounter } from './counter';
import { prepareCustomEventsAsync } from './customEvents';
import type { PreparedCustomEvent } from './customEvents';
import type { ReplayMouseTraceEvent } from './mouseTrace';
import { readMouseTraceAsync } from './replayMouseTrace';
import type { ReplayVideo } from './replayParser';

export interface AnalysisDataState {
    traceEvents: Ref<ReplayMouseTraceEvent[]>;
    counterEvents: Ref<CounterEvent[]>;
    preparedCounters: Ref<Map<string, PreparedCounter>>;
    preparedEvents: Ref<Map<string, PreparedCustomEvent>>;
    progress: Ref<AnalysisProgressSnapshot>;
    progressVisible: Ref<boolean>;
    errorMessage: Ref<string>;
    load: (video: ReplayVideo) => Promise<void>;
    refreshPrepared: () => Promise<void>;
    cancel: () => void;
    clear: () => void;
}

export function useAnalysisData(config: MaybeRefOrGetter<AnalyzerConfig>, durationMs: MaybeRefOrGetter<number>): AnalysisDataState {
    const traceEvents = shallowRef<ReplayMouseTraceEvent[]>([]);
    const counterEvents = shallowRef<CounterEvent[]>([]);
    const preparedCounters = shallowRef<Map<string, PreparedCounter>>(new Map());
    const preparedEvents = shallowRef<Map<string, PreparedCustomEvent>>(new Map());
    const progress = shallowRef<AnalysisProgressSnapshot>(initialAnalysisProgress());
    const progressVisible = ref(false);
    const errorMessage = ref('');
    let runId = 0;

    function reporterFor(token: number): ProgressReport {
        return createProgressReporter(progress, () => token !== runId);
    }

    async function runStep<T>(token: number, key: AnalysisStepKey, step: number, steps: number, total: number, work: (report: ProgressReport) => Promise<T>): Promise<T> {
        progress.value = { ...progress.value,
            key,
            step,
            steps,
            done: 0,
            total: Math.max(total, 1),
            percent: Math.max(progress.value.percent, Math.round((step - 1) / steps * 100)) };
        await nextTick();
        await yieldToBrowser();
        if (token !== runId) throw new AnalysisCancelled();
        const result = await work(reporterFor(token));
        if (token !== runId) throw new AnalysisCancelled();
        return result;
    }

    async function runPrepared(token: number, firstStep: number, steps: number): Promise<void> {
        const rows = toValue(config).counter.rows;
        const definitions = toValue(config).customEvents;
        const events = counterEvents.value;
        const duration = toValue(durationMs);
        const counters = await runStep(token, 'counters', firstStep, steps, rows.length, (report) => prepareCountersAsync(rows, events, duration, report));
        if (token !== runId) return;
        preparedCounters.value = counters;
        const custom = await runStep(token, 'customEvents', firstStep + 1, steps, definitions.length, (report) => prepareCustomEventsAsync(definitions, events, duration, report));
        if (token !== runId) return;
        preparedEvents.value = custom;
    }

    async function execute(token: number, steps: number, operation: () => Promise<void>): Promise<void> {
        errorMessage.value = '';
        progress.value = initialAnalysisProgress(steps);
        progressVisible.value = true;
        try {
            await operation();
        } catch (error) {
            if (error instanceof AnalysisCancelled) return;
            errorMessage.value = error instanceof Error ? error.message : String(error);
        } finally {
            if (token === runId) {
                progress.value = { ...progress.value, done: progress.value.total, percent: 100 };
                progressVisible.value = false;
            }
        }
    }

    return {
        traceEvents,
        counterEvents,
        preparedCounters,
        preparedEvents,
        progress,
        progressVisible,
        errorMessage,
        load: (video) => {
            const token = ++runId;
            return execute(token, 4, async () => {
                const trace = await runStep(token, 'trace', 1, 4, video.events.length, (report) => readMouseTraceAsync(video, report));
                if (token !== runId) return;
                traceEvents.value = trace;
                const events = await runStep(token, 'counter', 2, 4, video.events.length, (report) => readCounterEventsAsync(video, report));
                if (token !== runId) return;
                counterEvents.value = events;
                await runPrepared(token, 3, 4);
            });
        },
        refreshPrepared: () => {
            const token = ++runId;
            return execute(token, 2, () => runPrepared(token, 1, 2));
        },
        cancel: () => {
            runId++;
            progressVisible.value = false;
        },
        clear: () => {
            runId++;
            progressVisible.value = false;
            errorMessage.value = '';
            traceEvents.value = [];
            counterEvents.value = [];
            preparedCounters.value = new Map();
            preparedEvents.value = new Map();
            progress.value = initialAnalysisProgress();
        },
    };
}
