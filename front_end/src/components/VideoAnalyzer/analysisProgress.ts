import { nextTick } from 'vue';
import type { Ref } from 'vue';

export const ANALYSIS_CHUNK_SIZE = 2000;

export type AnalysisStepKey = 'trace' | 'counter' | 'counters' | 'customEvents';

export interface AnalysisProgressSnapshot {
    key: AnalysisStepKey;
    step: number;
    steps: number;
    done: number;
    total: number;
    percent: number;
}

export type ProgressReport = (done: number, total: number) => Promise<void>;

export class AnalysisCancelled extends Error {
    public constructor() {
        super('Analysis cancelled');
    }
}

export function initialAnalysisProgress(steps = 4): AnalysisProgressSnapshot {
    return { key: 'trace', step: 1, steps, done: 0, total: 1, percent: 0 };
}

export function yieldToBrowser(): Promise<void> {
    return new Promise((resolve) => {
        setTimeout(resolve, 0);
    });
}

export function createProgressReporter(progress: Ref<AnalysisProgressSnapshot>, isCancelled: () => boolean): ProgressReport {
    let lastUpdate = 0;
    return async (done, total) => {
        if (isCancelled()) throw new AnalysisCancelled();
        const { step, steps } = progress.value;
        const fraction = total > 0 ? Math.min(1, done / total) : 1;
        const raw = Math.round(((step - 1) + fraction) / steps * 100);
        const percent = Math.max(progress.value.percent, Math.min(100, raw));
        const now = Date.now();
        if (percent === progress.value.percent && now - lastUpdate < 60 && done < total) return;
        lastUpdate = now;
        progress.value = { ...progress.value, done, total, percent };
        await nextTick();
        await yieldToBrowser();
        if (isCancelled()) throw new AnalysisCancelled();
    };
}
