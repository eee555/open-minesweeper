import { bisector } from 'd3-array';
import { format } from 'd3-format';
import { Parser } from 'expr-eval';
import type { Expression } from 'expr-eval';
import type { VideoActionStateRecorder } from 'ms-toollib';

import { ANALYSIS_CHUNK_SIZE, AnalysisCancelled, createSubReporter } from './analysisProgress';
import type { ProgressReport } from './analysisProgress';
import { createDifferenceEvaluator } from './counterDifference';
import type { ReplayVideo } from './replayParser';

export const counterStaticVariables = ['row', 'column', 'mine_num', 'pix_size', 'bbbv', 'op', 'isl', 'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8', 'zini', 'hzini', 'rtime', 'level', 'mode'] as const;
export const counterVariables = ['time', 'path', 'c_path', 'e_path', 'bbbv_solved', 'bbbv_solved_left', 'bbbv_solved_chord', 'left', 'right', 'double', 'lce', 'rce', 'dce', 'flag', 'op_solved', 'isl_solved', 'mouse_state', 'pluck', 'luck', 'expected_bbbv_solved_per_attempt', 'expected_bbbv_solved_per_win', 'expected_time_per_attempt', 'expected_time_per_win', ...counterStaticVariables] as const;
export type CounterValues = Record<typeof counterVariables[number], number>;
export const samplingModes = ['continuous', 'button', 'board'] as const;
export type SamplingMode = typeof samplingModes[number];

export interface CounterRow {
    key: string;
    expression: string;
    format: string;
    samplingMode: SamplingMode;
}

export interface CounterConfig {
    rows: CounterRow[];
    thWidth: number;
    tdWidth: number;
}

export interface CounterEvent {
    timeMs: number;
    eventIndex: number;
    button: boolean;
    boardChanged: boolean;
    values: CounterValues;
}

export interface CounterSample {
    timeMs: number;
    eventIndex: number;
    value: number;
}

export interface PreparedCounter {
    samples: CounterSample[];
    formatter: (value: number) => string;
    error: string;
}

const parser = new Parser({ operators: { assignment: false } });
(parser.functions as Record<string, () => never>).d = () => {
    throw new Error('d requires a direct call in a sampling context');
};
const byTime = bisector<CounterSample, number>((sample) => sample.timeMs);
const buttonActions = new Set(['lc', 'lr', 'rc', 'rr', 'mc', 'mr', 'cc', 'cr']);

export function defaultCounterConfig(): CounterConfig {
    return { thWidth: 80,
        tdWidth: 96,
        rows: [
            { key: 'Bvs', expression: 'd(bbbv_solved, 1000) / d(time, 1000)', format: '.3f', samplingMode: 'continuous' },
            { key: 'Ces', expression: 'd(lce+rce+dce, 1000)/d(time, 1000)', format: '.3f', samplingMode: 'continuous' },
            { key: 'Mov', expression: 'd(path, 1000) / d(time, 1000) / 16', format: '.3f', samplingMode: 'continuous' },
        ] };
}

export function parseCounterExpression(expression: string): Expression {
    const parsed = parser.parse(expression);
    const unknown = parsed.variables().filter((variable) => !counterVariables.includes(variable as typeof counterVariables[number]));
    if (unknown.length > 0) throw new Error(`Unknown variable: ${unknown.join(', ')}`);
    return parsed;
}

export function counterError(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
}

export function parseCounterConfig(json: string): CounterConfig {
    const config = JSON.parse(json) as unknown;
    if (typeof config !== 'object' || config === null || !('rows' in config) || !Array.isArray(config.rows)
        || !('thWidth' in config) || typeof config.thWidth !== 'number' || !Number.isFinite(config.thWidth)
        || !('tdWidth' in config) || typeof config.tdWidth !== 'number' || !Number.isFinite(config.tdWidth)) throw new Error('invalidConfig');
    const keys = new Set<string>();
    const rows = config.rows.map((row: unknown): CounterRow => {
        if (typeof row !== 'object' || row === null
            || !('key' in row) || typeof row.key !== 'string'
            || !('expression' in row) || typeof row.expression !== 'string'
            || !('format' in row) || typeof row.format !== 'string'
            || !('samplingMode' in row) || !samplingModes.includes(row.samplingMode as SamplingMode)) throw new Error('invalidConfig');
        if (keys.has(row.key)) throw new Error('duplicateKey');
        keys.add(row.key);
        return { key: row.key, expression: row.expression, format: row.format, samplingMode: row.samplingMode as SamplingMode };
    });
    return { rows, thWidth: config.thWidth, tdWidth: config.tdWidth };
}

export function moveCounterRow(rows: CounterRow[], key: string, offset: number): CounterRow[] {
    const index = rows.findIndex((row) => row.key === key);
    if (index < 0 || !Number.isInteger(offset)) return rows;
    const target = Math.max(0, Math.min(rows.length - 1, index + offset));
    const result = [...rows];
    const [row] = result.splice(index, 1);
    result.splice(target, 0, row);
    return result;
}

function readCounterEvent(record: VideoActionStateRecorder, eventIndex: number, staticValues: Pick<CounterValues, typeof counterStaticVariables[number]>, startTime: number): CounterEvent {
    const params = record.key_dynamic_params;
    const { event } = record;
    try {
        let button = false;
        if (event.is_mouse()) {
            const mouse = event.unwrap_mouse();
            try {
                button = buttonActions.has(mouse.mouse);
            } finally {
                mouse.free();
            }
        }
        const prior = record.prior_game_board;
        try {
            const next = record.next_game_board;
            try {
                const before = prior.game_board as number[][];
                const after = next.game_board as number[][];
                const boardChanged = before.length !== after.length || before.some((row, r) => row.length !== after[r]?.length || row.some((cell, c) => cell !== after[r][c]));
                return {
                    eventIndex,
                    timeMs: Math.round((record.time + startTime) * 1000),
                    button,
                    boardChanged,
                    values: {
                        ...staticValues,
                        time: record.time,
                        path: record.path,
                        c_path: record.c_path,
                        e_path: record.e_path,
                        bbbv_solved: params.bbbv_solved,
                        bbbv_solved_left: params.bbbv_solved_left,
                        bbbv_solved_chord: params.bbbv_solved_chord,
                        left: params.left,
                        right: params.right,
                        double: params.double,
                        lce: params.lce,
                        rce: params.rce,
                        dce: params.dce,
                        flag: params.flag,
                        op_solved: params.op_solved,
                        isl_solved: params.isl_solved,
                        mouse_state: record.mouse_state,
                        pluck: params.pluck,
                        luck: params.luck,
                        expected_bbbv_solved_per_attempt: params.expected_bbbv_solved_per_attempt,
                        expected_bbbv_solved_per_win: params.expected_bbbv_solved_per_win,
                        expected_time_per_attempt: params.expected_time_per_attempt,
                        expected_time_per_win: params.expected_time_per_win,
                    },
                };
            } finally {
                next.free();
            }
        } finally {
            prior.free();
        }
    } finally {
        event.free();
        params.free();
    }
}

export function readCounterEvents(video: ReplayVideo): CounterEvent[] {
    const staticValues = Object.fromEntries(counterStaticVariables.map((key) => [key, video[key]])) as Pick<CounterValues, typeof counterStaticVariables[number]>;
    const records = video.events as VideoActionStateRecorder[];
    const startTime = video.video_start_time;
    try {
        return records.map((record, eventIndex) => readCounterEvent(record, eventIndex, staticValues, startTime));
    } finally {
        for (const record of records) record.free();
    }
}

export async function readCounterEventsAsync(video: ReplayVideo, report: ProgressReport): Promise<CounterEvent[]> {
    const staticValues = Object.fromEntries(counterStaticVariables.map((key) => [key, video[key]])) as Pick<CounterValues, typeof counterStaticVariables[number]>;
    const records = video.events as VideoActionStateRecorder[];
    const startTime = video.video_start_time;
    const events: CounterEvent[] = [];
    try {
        for (let eventIndex = 0; eventIndex < records.length; eventIndex++) {
            events.push(readCounterEvent(records[eventIndex], eventIndex, staticValues, startTime));
            if ((eventIndex + 1) % ANALYSIS_CHUNK_SIZE === 0) await report(eventIndex + 1, records.length);
        }
        await report(records.length, records.length);
    } finally {
        for (const record of records) record.free();
    }
    return events;
}

export function selectCounterEvents(events: CounterEvent[], samplingMode: SamplingMode, durationMs?: number): CounterEvent[] {
    const selected = new Map<number, CounterEvent>();
    for (const event of events) {
        if (samplingMode === 'continuous' || (samplingMode === 'button' ? event.button : event.boardChanged)) selected.set(event.timeMs, event);
    }
    const snapshots = [...selected.values()];
    if (samplingMode !== 'continuous' || snapshots.length === 0) return snapshots;
    const endMs = Math.max(snapshots[snapshots.length - 1].timeMs, Math.floor(durationMs ?? 0));
    const samples: CounterEvent[] = [];
    let index = 0;
    const [first] = snapshots;
    for (let { timeMs } = first; timeMs <= endMs; timeMs++) {
        while (index + 1 < snapshots.length && snapshots[index + 1].timeMs <= timeMs) index++;
        const snapshot = snapshots[index];
        // Keep every source field, including time, unchanged when filling an event-free millisecond.
        samples.push(timeMs === snapshot.timeMs ? snapshot : { ...snapshot, timeMs });
    }
    return samples;
}

export async function selectCounterEventsAsync(events: CounterEvent[], samplingMode: SamplingMode, durationMs: number | undefined, report: ProgressReport): Promise<CounterEvent[]> {
    const selected = new Map<number, CounterEvent>();
    let done = 0;
    for (const event of events) {
        if (samplingMode === 'continuous' || (samplingMode === 'button' ? event.button : event.boardChanged)) selected.set(event.timeMs, event);
        done++;
        if (done % ANALYSIS_CHUNK_SIZE === 0) await report(done, events.length);
    }
    const snapshots = [...selected.values()];
    if (samplingMode !== 'continuous' || snapshots.length === 0) {
        await report(events.length, events.length);
        return snapshots;
    }
    const endMs = Math.max(snapshots[snapshots.length - 1].timeMs, Math.floor(durationMs ?? 0));
    const [first] = snapshots;
    let { timeMs } = first;
    const total = events.length + endMs - timeMs + 1;
    const samples: CounterEvent[] = [];
    let index = 0;
    for (; timeMs <= endMs; timeMs++) {
        while (index + 1 < snapshots.length && snapshots[index + 1].timeMs <= timeMs) index++;
        const snapshot = snapshots[index];
        samples.push(timeMs === snapshot.timeMs ? snapshot : { ...snapshot, timeMs });
        done++;
        if (done % ANALYSIS_CHUNK_SIZE === 0) await report(done, total);
    }
    await report(total, total);
    return samples;
}

export function createCounterEvaluator(expression: Expression, events: CounterEvent[]): (index: number) => unknown {
    return createDifferenceEvaluator(parser, expression, events.map((event) => event.values));
}

export function prepareCounter(row: CounterRow, events: CounterEvent[], durationMs?: number): PreparedCounter {
    try {
        if (!samplingModes.includes(row.samplingMode)) throw new Error(`Unknown sampling mode: ${row.samplingMode}`);
        const parsed = parseCounterExpression(row.expression);
        const formatter = format(row.format);
        const snapshots = selectCounterEvents(events, row.samplingMode, durationMs);
        const evaluate = createCounterEvaluator(parsed, snapshots);
        const samples: CounterSample[] = snapshots.map((event, index) => {
            const value = evaluate(index);
            if (typeof value !== 'number') throw new Error('Expression must return a single number');
            return { timeMs: event.timeMs, eventIndex: event.eventIndex, value };
        });
        return { samples, formatter, error: '' };
    } catch (error) {
        return { samples: [], formatter: String, error: counterError(error) };
    }
}

export function prepareCounters(rows: CounterRow[], events: CounterEvent[], durationMs?: number): Map<string, PreparedCounter> {
    return new Map(rows.map((row) => [row.key, prepareCounter(row, events, durationMs)]));
}

export async function prepareCounterAsync(row: CounterRow, events: CounterEvent[], durationMs: number | undefined, report: ProgressReport): Promise<PreparedCounter> {
    try {
        if (!samplingModes.includes(row.samplingMode)) throw new Error(`Unknown sampling mode: ${row.samplingMode}`);
        const parsed = parseCounterExpression(row.expression);
        const formatter = format(row.format);
        const selectionReporter = createSubReporter(report, 0, 0.5);
        const snapshots = await selectCounterEventsAsync(events, row.samplingMode, durationMs, selectionReporter);
        const evaluate = createCounterEvaluator(parsed, snapshots);
        const sampleReporter = createSubReporter(report, 0.5, 0.5);
        const samples: CounterSample[] = [];
        let done = 0;
        for (const [index, event] of snapshots.entries()) {
            const value = evaluate(index);
            if (typeof value !== 'number') throw new Error('Expression must return a single number');
            samples.push({ timeMs: event.timeMs, eventIndex: event.eventIndex, value });
            done++;
            if (done % ANALYSIS_CHUNK_SIZE === 0) await sampleReporter(done, snapshots.length);
        }
        await sampleReporter(snapshots.length, snapshots.length);
        return { samples, formatter, error: '' };
    } catch (error) {
        if (error instanceof AnalysisCancelled) throw error;
        return { samples: [], formatter: String, error: counterError(error) };
    }
}

export async function prepareCountersAsync(rows: CounterRow[], events: CounterEvent[], durationMs: number | undefined, report: ProgressReport): Promise<Map<string, PreparedCounter>> {
    const result = new Map<string, PreparedCounter>();
    for (let index = 0; index < rows.length; index++) {
        const rowReporter = createSubReporter(report, index / rows.length, 1 / rows.length);
        result.set(rows[index].key, await prepareCounterAsync(rows[index], events, durationMs, rowReporter));
    }
    if (rows.length === 0) await report(1, 1);
    return result;
}

export function counterValue(samples: CounterSample[], currentMs: number): number {
    const right = byTime.left(samples, currentMs);
    if (right === samples.length) return samples[samples.length - 1].value;
    if (right === 0 || samples[right].timeMs === currentMs) return samples[right].value;
    const leftSample = samples[right - 1];
    const rightSample = samples[right];
    return leftSample.value + (rightSample.value - leftSample.value) * (currentMs - leftSample.timeMs) / (rightSample.timeMs - leftSample.timeMs);
}

export function displayCounter(prepared: PreparedCounter, currentMs: number): { value: string; error: boolean } {
    if (prepared.error !== '') return { value: prepared.error, error: true };
    try {
        return { value: prepared.formatter(counterValue(prepared.samples, currentMs)), error: false };
    } catch (error) {
        return { value: counterError(error), error: true };
    }
}
