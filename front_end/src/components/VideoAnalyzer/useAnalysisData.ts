import { nextTick, ref, shallowRef, toValue } from 'vue';
import type { MaybeRefOrGetter, Ref } from 'vue';

import { AnalysisCancelled, createProgressReporter, initialAnalysisProgress, yieldToBrowser } from './analysisProgress';
import type { AnalysisProgressSnapshot, AnalysisStepKey, ProgressReport } from './analysisProgress';
import type { AnalyzerConfig } from './config';
import { prepareCountersAsync, readCounterEventsAsync } from './counter';
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
    isRunning: Ref<boolean>;
    errorMessage: Ref<string>;
    load: (video: ReplayVideo) => Promise<void>;
    notifyCountersChanged: () => void;
    notifyCustomEventsChanged: () => void;
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
    const isRunning = ref(false);
    const errorMessage = ref('');
    let runId = 0;
    let pendingCounterRefresh = false;
    let pendingCustomEventRefresh = false;

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

    async function prepareCounters(token: number, step: number, steps: number): Promise<void> {
        const { rows } = toValue(config).counter;
        const events = counterEvents.value;
        const duration = toValue(durationMs);
        const counters = await runStep(token, 'counters', step, steps, 1, (report) => prepareCountersAsync(rows, events, duration, report));
        if (token !== runId) return;
        preparedCounters.value = counters;
    }

    async function prepareCustomEvents(token: number, step: number, steps: number): Promise<void> {
        const { customEvents: definitions } = toValue(config);
        const events = counterEvents.value;
        const duration = toValue(durationMs);
        const custom = await runStep(token, 'customEvents', step, steps, 1, (report) => prepareCustomEventsAsync(definitions, events, duration, report));
        if (token !== runId) return;
        preparedEvents.value = custom;
    }

    async function runPrepared(token: number, firstStep: number, steps: number): Promise<void> {
        await prepareCounters(token, firstStep, steps);
        if (token !== runId) return;
        await prepareCustomEvents(token, firstStep + 1, steps);
    }

    function refresh(counters: boolean, customEvents: boolean): Promise<void> {
        const token = ++runId;
        const steps = Math.max(1, Number(counters) + Number(customEvents));
        return execute(token, steps, async () => {
            let step = 1;
            if (counters) {
                await prepareCounters(token, step++, steps);
                if (token !== runId) return;
            }
            if (customEvents) await prepareCustomEvents(token, step++, steps);
        }, false);
    }

    async function execute(token: number, steps: number, operation: () => Promise<void>, showProgress = true): Promise<void> {
        errorMessage.value = '';
        progress.value = initialAnalysisProgress(steps);
        progressVisible.value = showProgress;
        isRunning.value = true;
        try {
            await operation();
        } catch (error) {
            if (error instanceof AnalysisCancelled) return;
            errorMessage.value = error instanceof Error ? error.message : String(error);
        } finally {
            if (token === runId) {
                if (showProgress) {
                    progress.value = { ...progress.value, done: progress.value.total, percent: 100 };
                    progressVisible.value = false;
                }
                isRunning.value = false;
                if (pendingCounterRefresh || pendingCustomEventRefresh) {
                    const counters = pendingCounterRefresh;
                    const customEvents = pendingCustomEventRefresh;
                    pendingCounterRefresh = false;
                    pendingCustomEventRefresh = false;
                    void refresh(counters, customEvents);
                }
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
        isRunning,
        errorMessage,
        load: (video) => {
            const token = ++runId;
            return execute(token, 4, async () => {
                const trace = await runStep(token, 'trace', 1, 4, 1, (report) => readMouseTraceAsync(video, report));
                if (token !== runId) return;
                traceEvents.value = trace;
                const events = await runStep(token, 'counter', 2, 4, 1, (report) => readCounterEventsAsync(video, report));
                if (token !== runId) return;
                counterEvents.value = events;
                await runPrepared(token, 3, 4);
            });
        },
        notifyCountersChanged: () => {
            if (isRunning.value) {
                pendingCounterRefresh = true;
                return;
            }
            void refresh(true, false);
        },
        notifyCustomEventsChanged: () => {
            if (isRunning.value) {
                pendingCustomEventRefresh = true;
                return;
            }
            void refresh(false, true);
        },
        cancel: () => {
            runId++;
            progressVisible.value = false;
            isRunning.value = false;
            pendingCounterRefresh = false;
            pendingCustomEventRefresh = false;
        },
        clear: () => {
            runId++;
            progressVisible.value = false;
            isRunning.value = false;
            pendingCounterRefresh = false;
            pendingCustomEventRefresh = false;
            errorMessage.value = '';
            traceEvents.value = [];
            counterEvents.value = [];
            preparedCounters.value = new Map();
            preparedEvents.value = new Map();
            progress.value = initialAnalysisProgress();
        },
    };
}
