import { ANALYSIS_CHUNK_SIZE } from './analysisProgress';
import type { ProgressReport } from './analysisProgress';
import { createCounterEvaluator, parseCounterExpression, selectCounterEvents, selectCounterEventsAsync } from './counter';
import type { CounterEvent } from './counter';

export const eventMarkerShapes = ['circle', 'square', 'triangle', 'diamond', 'cross'] as const;
export const eventLineStyles = ['solid', 'dash', 'dot'] as const;

export interface CustomEventDefinition {
    key: string;
    expression: string;
    type: 'pulse' | 'sustained';
    color: string;
    marker: { shape: typeof eventMarkerShapes[number]; size: number; opacity: number };
    line: { style: typeof eventLineStyles[number]; width: number; opacity: number };
}

export interface EventPulse {
    timeMs: number;
    eventIndex: number;
    value?: number | string;
}

export interface EventSpan {
    startMs: number;
    endMs: number;
    renderEndMs: number;
    startEventIndex: number;
    lastEventIndex: number;
}

export interface PreparedCustomEvent {
    pulses: EventPulse[];
    spans: EventSpan[];
}

export function defaultCustomEvent(): CustomEventDefinition {
    return { key: '', expression: '', type: 'pulse', color: '#e15759', marker: { shape: 'circle', size: 8, opacity: 1 }, line: { style: 'solid', width: 2, opacity: 1 } };
}

export function eventOccurs(value: unknown): boolean {
    return (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string') && Boolean(value);
}

function createCustomEventCollector(definition: CustomEventDefinition, snapshots: CounterEvent[], durationMs: number): { accept: (index: number) => void; finish: () => PreparedCustomEvent } | null {
    const result: PreparedCustomEvent = { pulses: [], spans: [] };
    let evaluate: (index: number) => unknown;
    try {
        evaluate = createCounterEvaluator(parseCounterExpression(definition.expression), snapshots);
    } catch {
        return null;
    }
    let active: EventSpan | null = null;
    return {
        accept: (index) => {
            const snapshot = snapshots[index];
            let occurs = false;
            let value: unknown;
            try {
                value = evaluate(index);
                occurs = eventOccurs(value);
            } catch {
                // A failed sample ends a sustained event just like a false result.
            }
            if (definition.type === 'pulse') {
                if (occurs) {
                    const pulse: EventPulse = { timeMs: snapshot.timeMs, eventIndex: snapshot.eventIndex };
                    if (typeof value === 'number' || typeof value === 'string') pulse.value = value;
                    result.pulses.push(pulse);
                }
            } else if (occurs) {
                active ??= { startMs: snapshot.timeMs, endMs: durationMs, renderEndMs: snapshot.timeMs, startEventIndex: snapshot.eventIndex, lastEventIndex: snapshot.eventIndex };
                active.renderEndMs = snapshot.timeMs;
                active.lastEventIndex = snapshot.eventIndex;
            } else if (active !== null) {
                active.endMs = snapshot.timeMs;
                result.spans.push(active);
                active = null;
            }
        },
        finish: () => {
            if (active !== null) result.spans.push({ ...active, endMs: durationMs, renderEndMs: durationMs });
            return result;
        },
    };
}

export function prepareCustomEvent(definition: CustomEventDefinition, snapshots: CounterEvent[], durationMs: number): PreparedCustomEvent {
    const collector = createCustomEventCollector(definition, snapshots, durationMs);
    if (collector === null) return { pulses: [], spans: [] };
    for (let index = 0; index < snapshots.length; index++) collector.accept(index);
    return collector.finish();
}

export async function prepareCustomEventAsync(definition: CustomEventDefinition, snapshots: CounterEvent[], durationMs: number, report: ProgressReport): Promise<PreparedCustomEvent> {
    const collector = createCustomEventCollector(definition, snapshots, durationMs);
    if (collector === null) {
        await report(1, 1);
        return { pulses: [], spans: [] };
    }
    for (let index = 0; index < snapshots.length; index++) {
        collector.accept(index);
        if ((index + 1) % ANALYSIS_CHUNK_SIZE === 0) await report(index + 1, snapshots.length);
    }
    await report(snapshots.length, snapshots.length);
    return collector.finish();
}

export function prepareCustomEvents(definitions: CustomEventDefinition[], events: CounterEvent[], durationMs: number): Map<string, PreparedCustomEvent> {
    const snapshots = selectCounterEvents(events, 'continuous', durationMs);
    return new Map(definitions.map((definition) => [definition.key, prepareCustomEvent(definition, snapshots, durationMs)]));
}

export async function prepareCustomEventsAsync(definitions: CustomEventDefinition[], events: CounterEvent[], durationMs: number, report: ProgressReport): Promise<Map<string, PreparedCustomEvent>> {
    const snapshots = await selectCounterEventsAsync(events, 'continuous', durationMs, report);
    const result = new Map<string, PreparedCustomEvent>();
    const total = Math.max(1, definitions.length * snapshots.length);
    let done = 0;
    for (const definition of definitions) {
        result.set(definition.key, await prepareCustomEventAsync(definition, snapshots, durationMs, (current) => report(done + current, total)));
        done += snapshots.length;
        await report(done, total);
    }
    await report(total, total);
    return result;
}

export function eventLineDash(style: CustomEventDefinition['line']['style']): string {
    return style === 'dash' ? '6 3' : style === 'dot' ? '1 3' : 'none';
}
