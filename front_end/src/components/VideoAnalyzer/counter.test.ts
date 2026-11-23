import { readFileSync } from 'node:fs';

import { AvfVideo, Event as ReplayEvent, EvfVideo, GameBoard, KeyDynamicParams, MouseEvent as ReplayMouseEvent, MvfVideo, RmvVideo, VideoActionStateRecorder } from 'ms-toollib';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { counterStaticVariables, counterValue, counterVariables, defaultCounterConfig, displayCounter, moveCounterRow, parseCounterConfig, parseCounterExpression, prepareCounter, prepareCountersAsync, readCounterEvents, readCounterEventsAsync } from './counter';
import type { CounterEvent, CounterRow, CounterValues } from './counter';
import { parseReplay } from './replayParser';

function event(index: number, value: number, button = true, boardChanged = true): CounterEvent {
    const values = Object.fromEntries(counterVariables.map((key) => [key, value])) as CounterValues;
    values.time = index;
    return { eventIndex: index, timeMs: index * 1000, button, boardChanged, values };
}

function row(expression = 'bbbv_solved'): CounterRow {
    return { key: 'bvs', expression, format: '.3f', samplingMode: 'button' as const };
}

afterEach(() => vi.restoreAllMocks());

describe('counter expressions', () => {
    it('allows snapshot and selected static variables and library functions', () => {
        const { values } = event(3, 2);
        for (const key of counterVariables) expect(parseCounterExpression(key).evaluate(values)).toBe(values[key]);
        expect(parseCounterExpression('roundTo(bbbv_solved / time, 3)').evaluate(values)).toBe(0.667);
        expect(parseCounterExpression('bbbv_solved / bbbv + mine_num / (row * column)').evaluate(values)).toBe(1.5);
        for (let state = 1; state <= 8; state++) {
            expect(parseCounterExpression('mouse_state == 4 ? 1 : 0').evaluate({ ...values, mouse_state: state })).toBe(state === 4 ? 1 : 0);
        }
        for (const forbidden of ['bbbv_s', 'rtime_ms', 'etime', 'current_time', 'cl', 'unknown']) expect(() => parseCounterExpression(forbidden)).toThrow(`Unknown variable: ${forbidden}`);
        expect(() => parseCounterExpression('left = 2')).toThrow();
    });

    it('uses pixel coordinates in differences, cell formulas and interpolated counter displays', () => {
        const snapshots = [event(0, 0), event(1, 0), event(2, 0)];
        snapshots.forEach((snapshot, index) => {
            Object.assign(snapshot.values, { x: index * 24, y: index * 32, pix_size: 16 });
        });
        const distance = prepareCounter(row('sqrt(d(x)^2 + d(y)^2) / pix_size'), snapshots);
        expect(distance.error).toBe('');
        expect(distance.samples.map((sample) => sample.value)).toEqual([NaN, 2.5, 2.5]);
        expect(prepareCounter(row('floor(x / pix_size)'), snapshots).samples.map((sample) => sample.value)).toEqual([0, 1, 3]);
        expect(prepareCounter(row('s(y, 2)'), snapshots).samples.map((sample) => sample.value)).toEqual([0, 32, 96]);
        expect(displayCounter(prepareCounter(row('x'), snapshots), 500).value).toBe('12.000');
    });

    it.each(['"3"', '[left, right]', 'left > right', 'roundTo'])('shows a type error for nonnumeric result %s', (expression) => {
        const prepared = prepareCounter(row(expression), [event(0, 1)]);
        expect(displayCounter(prepared, 0)).toEqual({ value: 'Expression must return a single number', error: true });
    });

    it.each([['0 / 0', NaN], ['1 / 0', Infinity], ['-1 / 0', -Infinity]] as const)('preserves nonfinite result %s', (expression, expected) => {
        const prepared = prepareCounter(row(expression), [event(0, 1)]);
        expect(prepared.error).toBe('');
        expect(prepared.samples[0].value).toBe(expected);
        expect(displayCounter(prepared, 0).error).toBe(false);
    });

    it('formats only the final number and reports parse, evaluation and format errors in the value', () => {
        const prepared = prepareCounter(row(), [event(0, 1), event(1, 2)]);
        expect(displayCounter(prepared, 500)).toEqual({ value: '1.500', error: false });
        expect(prepared.samples[0].value).toBe(1);
        for (const config of [row('left +'), row('missing'), { ...row(), format: 'invalid format' }]) {
            const result = displayCounter(prepareCounter(config, [event(0, 1)]), 0);
            expect(result.error).toBe(true);
            expect(result.value.length).toBeGreaterThan(0);
            expect(result.value).not.toBe('0');
        }
    });

    it('selects continuous, button and board snapshots without modifying the source', () => {
        const events = [event(0, 1, false, false), event(1, 2, true, false), event(2, 3, false, true), event(3, 4)].map((entry, timeMs) => ({ ...entry, timeMs }));
        const original = structuredClone(events);
        expect(prepareCounter({ ...row(), samplingMode: 'continuous' }, events).samples.map((sample) => sample.eventIndex)).toEqual([0, 1, 2, 3]);
        expect(prepareCounter({ ...row(), samplingMode: 'button' }, events).samples.map((sample) => sample.eventIndex)).toEqual([1, 3]);
        expect(prepareCounter({ ...row(), samplingMode: 'board' }, events).samples.map((sample) => sample.eventIndex)).toEqual([2, 3]);
        expect(events).toEqual(original);
    });

    it('filters before keeping the last eligible event in each millisecond and evaluates only surviving snapshots', () => {
        const events = [
            event(0, 0, false, false),
            { ...event(1, 10), timeMs: 1 },
            { ...event(2, 20), timeMs: 1 },
            { ...event(3, 30, false, false), timeMs: 1 },
            { ...event(4, 40, true, false), timeMs: 2 },
            { ...event(5, 50, false, true), timeMs: 2 },
            { ...event(6, 60, false, false), timeMs: 2 },
            { ...event(7, 70), timeMs: 10 },
        ];
        const original = structuredClone(events);
        for (const [samplingMode, indices] of [['continuous', [0, 3, 6, 6, 6, 6, 6, 6, 6, 6, 7]], ['button', [2, 4, 7]], ['board', [2, 5, 7]]] as const) {
            const prepared = prepareCounter({ ...row('bbbv_solved == 10 ? "discarded" : bbbv_solved'), samplingMode }, events);
            expect(prepared.error).toBe('');
            expect(prepared.samples.map((sample) => sample.eventIndex)).toEqual(indices);
            expect(prepared.samples.map((sample) => sample.value)).toEqual(indices.map((index) => events[index].values.bbbv_solved));
            expect(new Set(prepared.samples.map((sample) => sample.timeMs)).size).toBe(prepared.samples.length);
        }
        expect(events).toEqual(original);
    });

    it('samples every millisecond through replay end, falling back without changing source time or fields', () => {
        const events = [event(0, 0), event(1, 10)];
        const original = structuredClone(events);
        const prepared = prepareCounter({ ...row('time + left'), samplingMode: 'continuous' }, events, 1005);
        expect(prepared.samples).toHaveLength(1006);
        expect(prepared.samples.map((sample) => sample.timeMs)).toEqual(Array.from({ length: 1006 }, (_, index) => index));
        expect(prepared.samples[999]).toEqual({ timeMs: 999, eventIndex: 0, value: 0 });
        expect(prepared.samples[1000]).toEqual({ timeMs: 1000, eventIndex: 1, value: 11 });
        expect(prepared.samples[1005]).toEqual({ timeMs: 1005, eventIndex: 1, value: 11 });
        expect(counterValue(prepared.samples, 250)).toBe(0);
        expect(counterValue(prepared.samples, 999.5)).toBe(5.5);
        expect(events).toEqual(original);
        const late = prepareCounter({ ...row('time'), samplingMode: 'continuous' }, [events[1]], 1002);
        expect(late.samples).toEqual([1000, 1001, 1002].map((timeMs) => ({ timeMs, eventIndex: 1, value: 1 })));
        expect(prepareCounter({ ...row('time'), samplingMode: 'continuous' }, [], 100).samples).toEqual([]);
    });

    it('reports a removed sampling mode instead of silently using another mode', () => {
        const prepared = prepareCounter({ ...row(), samplingMode: 'event' as CounterRow['samplingMode'] }, [event(0, 1)]);
        expect(displayCounter(prepared, 0)).toEqual({ value: 'Unknown sampling mode: event', error: true });
    });

    it('prepares counters asynchronously with the same samples and progress', async () => {
        const events = [event(0, 1), event(1, 2)];
        const progress: [number, number][] = [];
        const prepared = await prepareCountersAsync([row()], events, undefined, (done, total) => {
            progress.push([done, total]);
            return Promise.resolve();
        });
        expect(prepared.get('bvs')?.samples).toEqual(prepareCounter(row(), events).samples);
        expect(progress.at(-1)).toEqual([1, 1]);
    });
});

describe('counter interpolation', () => {
    const samples = [
        { timeMs: 0, eventIndex: 0, value: 0 },
        { timeMs: 1000, eventIndex: 6, value: 30 },
        { timeMs: 2000, eventIndex: 8, value: 50 },
    ];

    it('interpolates only by time and returns exact samples unchanged', () => {
        expect(counterValue(samples, 500)).toBe(15);
        expect(counterValue(samples, 1500)).toBe(40);
        for (const sample of samples) expect(counterValue(samples, sample.timeMs)).toBe(sample.value);
    });

    it('holds the nearest endpoint outside sampling bounds and for a single sample', () => {
        expect(counterValue(samples, -1000)).toBe(0);
        expect(counterValue(samples, 3000)).toBe(50);
        for (const time of [-1, 1000, 5000]) expect(counterValue([samples[1]], time)).toBe(30);
    });

    it('returns raw nonfinite endpoints and leaves interpolation arithmetic unchanged', () => {
        const infinite = [{ timeMs: 0, eventIndex: 0, value: Infinity }, { timeMs: 1000, eventIndex: 1, value: Infinity }];
        expect(counterValue(infinite, 0)).toBe(Infinity);
        expect(counterValue(infinite, 1000)).toBe(Infinity);
        expect(counterValue(infinite, 500)).toBeNaN();
        expect(counterValue([{ ...infinite[0], value: 1 }, infinite[1]], 500)).toBe(Infinity);
        expect(counterValue([{ ...infinite[0], value: NaN }], -1)).toBeNaN();
    });
});

describe('counter configuration', () => {
    it('roundtrips ordered key-only rows with independent sampling modes', () => {
        const config = defaultCounterConfig();
        config.rows.push({ key: 'other', expression: 'path', format: '.1e', samplingMode: 'board' });
        config.rows.push({ key: 'time', expression: 'time', format: '.0f', samplingMode: 'continuous' });
        const restored = parseCounterConfig(JSON.stringify(config));
        expect(restored).toEqual(config);
        expect(restored.rows).not.toBe(config.rows);
        expect(defaultCounterConfig().rows).toHaveLength(3);
        expect(config.rows[0]).toEqual({ key: 'Bvs', expression: 'd(bbbv_solved, 1000) / d(time, 1000)', samplingMode: 'continuous', format: '.3f' });
    });

    it('rejects malformed JSON, invalid schemas and duplicate keys but not formula errors', () => {
        expect(() => parseCounterConfig('[,]')).toThrow(SyntaxError);
        for (const config of [{}, { ...defaultCounterConfig(), rows: [{}] }, { ...defaultCounterConfig(), thWidth: '80' }, { ...defaultCounterConfig(), rows: [{ ...row(), samplingMode: 'unknown' }] }, { ...defaultCounterConfig(), rows: [{ ...row(), samplingMode: 'event' }] }]) expect(() => parseCounterConfig(JSON.stringify(config))).toThrow('invalidConfig');
        expect(() => parseCounterConfig(JSON.stringify({ ...defaultCounterConfig(), rows: [row(), row()] }))).toThrow('duplicateKey');
        expect(parseCounterConfig(JSON.stringify({ ...defaultCounterConfig(), rows: [row('bad expression')] })).rows[0].expression).toBe('bad expression');
    });

    it('does not impose width bounds', () => {
        expect(parseCounterConfig(JSON.stringify({ ...defaultCounterConfig(), thWidth: 0, tdWidth: -2.5 }))).toMatchObject({ thWidth: 0, tdWidth: -2.5 });
    });

    it('moves by signed offset, clamps to first or last, and preserves the original rows', () => {
        const rows = ['a', 'b', 'c', 'd'].map((key) => ({ ...row(), key }));
        expect(moveCounterRow(rows, 'b', 2).map((entry) => entry.key)).toEqual(['a', 'c', 'd', 'b']);
        expect(moveCounterRow(rows, 'c', -100).map((entry) => entry.key)).toEqual(['c', 'a', 'b', 'd']);
        expect(moveCounterRow(rows, 'b', 100).map((entry) => entry.key)).toEqual(['a', 'c', 'd', 'b']);
        expect(rows.map((entry) => entry.key)).toEqual(['a', 'b', 'c', 'd']);
        expect(moveCounterRow(rows, 'missing', 1)).toBe(rows);
        expect(moveCounterRow(rows, 'a', 0.5)).toBe(rows);
    });
});

describe('real replay snapshots', () => {
    for (const [filename, software, Parser] of [
        ['52200.evf', 'e', EvfVideo],
        ['Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', 'a', AvfVideo],
        ['Lin_Jin_Fan_Exp_60.623bv207.mvf', 'm', MvfVideo],
        ['3819-Time-1616-NF-9469-32-20151031.rmv', 'r', RmvVideo],
    ] as const) {
        it(`reads ${filename} without seeking and releases event wrappers`, () => {
            const bytes = Uint8Array.from(readFileSync(new URL(`../../../cypress/fixtures/${filename}`, import.meta.url))).buffer;
            const video = parseReplay(bytes, filename, software, ['pluck']);
            try {
                expect(video).toBeInstanceOf(Parser);
                expect(video.row).toBeGreaterThan(0);
                expect(video.column).toBeGreaterThan(0);
                expect(video.rtime_ms).toBeGreaterThan(0);
                if (software === 'e') {
                    expect(video.rtime_ms).toBe(10732);
                    expect(video.is_completed).toBe(true);
                }
                const fullBoard = video.board as number[][];
                expect(fullBoard).toHaveLength(video.row);
                expect(fullBoard.flat().filter((cell) => cell === -1)).toHaveLength(video.mine_num);
                for (const cells of fullBoard) expect(cells).toHaveLength(video.column);
                video.current_time = video.rtime_ms / 2000;
                const position = video.current_event_id;
                const board = video.game_board;
                const staticValues = Object.fromEntries(counterStaticVariables.map((key) => [key, video[key]]));
                const staticGetters = counterStaticVariables.map((key) => vi.spyOn(video, key, 'get'));
                const free = vi.spyOn(VideoActionStateRecorder.prototype, 'free');
                const freeParams = vi.spyOn(KeyDynamicParams.prototype, 'free');
                const freeEvent = vi.spyOn(ReplayEvent.prototype, 'free');
                const freeBoard = vi.spyOn(GameBoard.prototype, 'free');
                const freeMouse = vi.spyOn(ReplayMouseEvent.prototype, 'free');
                const mouseX = vi.spyOn(ReplayMouseEvent.prototype, 'x', 'get');
                const mouseY = vi.spyOn(ReplayMouseEvent.prototype, 'y', 'get');
                const mouseState = vi.spyOn(VideoActionStateRecorder.prototype, 'mouse_state', 'get');
                const pluck = vi.spyOn(KeyDynamicParams.prototype, 'pluck', 'get');
                const events = readCounterEvents(video);
                expect(pluck).toHaveBeenCalledTimes(events.length);
                expect(events.map((snapshot) => snapshot.values.pluck)).toEqual(pluck.mock.results.map((result) => result.value as number));
                expect(events.every((snapshot) => Number.isFinite(snapshot.values.pluck))).toBe(true);
                expect(mouseState).toHaveBeenCalledTimes(events.length);
                expect(events.map((snapshot) => snapshot.values.mouse_state)).toEqual(mouseState.mock.results.map((result) => result.value as number));
                for (const getter of staticGetters) expect(getter).toHaveBeenCalledOnce();
                for (const snapshot of events) expect(snapshot.values).toMatchObject(staticValues);
                expect(free).toHaveBeenCalledTimes(events.length);
                expect(freeParams).toHaveBeenCalledTimes(events.length);
                expect(freeEvent).toHaveBeenCalledTimes(events.length);
                expect(freeBoard).toHaveBeenCalledTimes(events.length * 2);
                let mouseIndex = 0;
                let cursor = { x: NaN, y: NaN };
                const sourceRecords = video.events as VideoActionStateRecorder[];
                try {
                    for (const [index, record] of sourceRecords.entries()) {
                        const { event: sourceEvent } = record;
                        try {
                            if (sourceEvent.is_mouse()) {
                                const mouse = sourceEvent.unwrap_mouse();
                                try {
                                    const { x } = mouse;
                                    const { y } = mouse;
                                    expect(mouseX.mock.results[mouseIndex].value).toBe(x);
                                    expect(mouseY.mock.results[mouseIndex].value).toBe(y);
                                    mouseIndex++;
                                    cursor = { x, y };
                                } finally {
                                    mouse.free();
                                }
                            }
                        } finally {
                            sourceEvent.free();
                        }
                        expect(events[index].values).toMatchObject(cursor);
                    }
                    expect(freeMouse).toHaveBeenCalledTimes(mouseIndex * 2);
                } finally {
                    for (const record of sourceRecords) record.free();
                }
                expect(video.current_event_id).toBe(position);
                expect(video.game_board).toEqual(board);
                expect(events.length).toBeGreaterThan(0);
                expect(Object.keys(events[0].values).sort()).toEqual([...counterVariables].sort());
                for (const snapshot of events) {
                    expect(Number.isInteger(snapshot.values.mouse_state)).toBe(true);
                    expect(snapshot.values.mouse_state).toBeGreaterThanOrEqual(1);
                    expect(snapshot.values.mouse_state).toBeLessThanOrEqual(8);
                    expect(snapshot.values.bbbv_solved_left + snapshot.values.bbbv_solved_chord).toBe(snapshot.values.bbbv_solved);
                    expect(snapshot.values.luck).toBeCloseTo(10 ** -snapshot.values.pluck, 12);
                    expect(snapshot.timeMs).toBe(Math.round((snapshot.values.time + video.video_start_time) * 1000));
                    expect(Number.isInteger(snapshot.timeMs)).toBe(true);
                }
                const last = events[events.length - 1];
                if (software === 'e') expect(last.values.pluck).toBeCloseTo(0.08109874939134086, 12);
                expect(last.values.bbbv_solved).toBeGreaterThan(0);
                expect(last.values.path).toBeGreaterThan(0);
                for (const samplingMode of ['continuous', 'button', 'board'] as const) {
                    const prepared = prepareCounter({ ...row(), samplingMode }, events);
                    expect(prepared.error).toBe('');
                    expect(prepared.samples.length).toBeGreaterThan(0);
                    expect(displayCounter(prepared, video.rtime_ms).error).toBe(false);
                    const selected = events.filter((entry) => samplingMode === 'continuous' || (samplingMode === 'button' ? entry.button : entry.boardChanged));
                    const lastPerMs = new Map(selected.map((entry) => [entry.timeMs, entry]));
                    if (samplingMode === 'continuous') {
                        const expected: number[] = [];
                        let [previous] = events;
                        for (let { timeMs } = previous; timeMs <= last.timeMs; timeMs++) {
                            previous = lastPerMs.get(timeMs) ?? previous;
                            expected.push(previous.eventIndex);
                        }
                        expect(prepared.samples.map((sample) => sample.eventIndex)).toEqual(expected);
                    } else expect(prepared.samples.map((sample) => sample.eventIndex)).toEqual([...lastPerMs.values()].map((entry) => entry.eventIndex));
                }
                const progress = prepareCounter(row('bbbv_solved / bbbv'), events);
                expect(progress.error).toBe('');
                expect(progress.samples[progress.samples.length - 1].value).toBe(last.values.bbbv_solved / last.values.bbbv);
                expect(prepareCounter(row('pluck'), events).samples.at(-1)?.value).toBe(last.values.pluck);
                video.current_time = Infinity;
                for (const key of ['c_path', 'e_path', 'bbbv_solved_left', 'bbbv_solved_chord', 'luck', 'expected_bbbv_solved_per_attempt', 'expected_bbbv_solved_per_win', 'expected_time_per_attempt', 'expected_time_per_win'] as const) {
                    expect(last.values[key]).toBeCloseTo(video[key], 10);
                    expect(prepareCounter(row(key), events).samples.at(-1)?.value).toBe(last.values[key]);
                }
            } finally {
                video.free();
            }
        });
    }

    it('carries raw cursor positions across non-mouse events and resets them for each sync or async read', async () => {
        const bytes = Uint8Array.from(readFileSync(new URL('../../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
        const video = parseReplay(bytes, '52200.evf', 'e');
        try {
            const position = video.current_event_id;
            let recordIndex = 0;
            vi.spyOn(ReplayEvent.prototype, 'is_mouse').mockImplementation(() => [1, 3, 4].includes(recordIndex++));
            const xs = [0, 24, 65535];
            const ys = [0, 47, 65535];
            let mouseIndex = 0;
            vi.spyOn(ReplayMouseEvent.prototype, 'x', 'get').mockImplementation(() => xs[mouseIndex]);
            vi.spyOn(ReplayMouseEvent.prototype, 'y', 'get').mockImplementation(() => ys[mouseIndex++]);
            const sync = readCounterEvents(video);
            expect(sync.slice(0, 6).map(({ values: { x, y } }) => ({ x, y }))).toEqual([
                { x: NaN, y: NaN }, { x: 0, y: 0 }, { x: 0, y: 0 }, { x: 24, y: 47 }, { x: 65535, y: 65535 }, { x: 65535, y: 65535 },
            ]);
            recordIndex = 0;
            mouseIndex = 0;
            expect(await readCounterEventsAsync(video, () => Promise.resolve())).toEqual(sync);
            expect(video.current_event_id).toBe(position);
            const sampling = prepareCounter({ ...row('x / pix_size'), samplingMode: 'continuous' }, sync);
            expect(sampling.error).toBe('');
        } finally {
            video.free();
        }
    });

    it('preserves the library pluck value in incomplete replay counter samples', () => {
        const filename = 'c_10_39.832_24_0.477_Pu Tian Yi(Hu Bei)_fail.evf';
        const bytes = Uint8Array.from(readFileSync(new URL(`../../../cypress/fixtures/${filename}`, import.meta.url))).buffer;
        const video = parseReplay(bytes, filename, 'e', ['pluck']);
        try {
            expect(video).toBeInstanceOf(EvfVideo);
            expect(video.rtime_ms).toBe(39832);
            expect(video.is_completed).toBe(false);
            const board = video.board as number[][];
            expect(board).toHaveLength(video.row);
            expect(board.flat().filter((cell) => cell === -1)).toHaveLength(video.mine_num);
            for (const cells of board) expect(cells).toHaveLength(video.column);
            video.current_time = Infinity;
            const expectedPluck = video.pluck;
            expect(expectedPluck).toBeGreaterThan(0);
            const events = readCounterEvents(video);
            expect(events.at(-1)?.values.pluck).toBe(expectedPluck);
            expect(prepareCounter(row('pluck'), events).samples.at(-1)?.value).toBe(expectedPluck);
        } finally {
            video.free();
        }
    });

    it('preserves special library values without replacing or filtering them', () => {
        const bytes = Uint8Array.from(readFileSync(new URL('../../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
        const video = parseReplay(bytes, '52200.evf', 'e');
        try {
            vi.spyOn(video, 'zini', 'get').mockReturnValue(NaN);
            vi.spyOn(video, 'hzini', 'get').mockReturnValue(Infinity);
            vi.spyOn(KeyDynamicParams.prototype, 'pluck', 'get').mockReturnValue(Number.MAX_VALUE);
            vi.spyOn(KeyDynamicParams.prototype, 'luck', 'get').mockReturnValue(NaN);
            vi.spyOn(KeyDynamicParams.prototype, 'expected_time_per_win', 'get').mockReturnValue(Infinity);
            const events = readCounterEvents(video);
            for (const snapshot of events) {
                expect(snapshot.values.zini).toBeNaN();
                expect(snapshot.values.hzini).toBe(Infinity);
                expect(snapshot.values.pluck).toBe(Number.MAX_VALUE);
                expect(snapshot.values.luck).toBeNaN();
                expect(snapshot.values.expected_time_per_win).toBe(Infinity);
            }
            expect(prepareCounter(row('zini'), events).samples[0].value).toBeNaN();
            expect(prepareCounter(row('hzini'), events).samples[0].value).toBe(Infinity);
            expect(prepareCounter(row('pluck'), events).samples.at(-1)?.value).toBe(Number.MAX_VALUE);
            expect(prepareCounter(row('luck'), events).samples[0].value).toBeNaN();
            expect(prepareCounter(row('expected_time_per_win'), events).samples.at(-1)?.value).toBe(Infinity);
        } finally {
            video.free();
        }
    });

    it('frees snapshots and all record wrappers when reading a snapshot throws', () => {
        const bytes = Uint8Array.from(readFileSync(new URL('../../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
        const video = parseReplay(bytes, '52200.evf', 'e');
        try {
            const records = video.events as VideoActionStateRecorder[];
            const count = records.length;
            for (const record of records) record.free();
            const free = vi.spyOn(VideoActionStateRecorder.prototype, 'free');
            const freeParams = vi.spyOn(KeyDynamicParams.prototype, 'free');
            const freeEvent = vi.spyOn(ReplayEvent.prototype, 'free');
            const freeBoard = vi.spyOn(GameBoard.prototype, 'free');
            vi.spyOn(KeyDynamicParams.prototype, 'left', 'get').mockImplementation(() => {
                throw new Error('snapshot failure');
            });
            expect(() => readCounterEvents(video)).toThrow('snapshot failure');
            expect(free).toHaveBeenCalledTimes(count);
            expect(freeParams).toHaveBeenCalledOnce();
            expect(freeEvent).toHaveBeenCalledOnce();
            expect(freeBoard).toHaveBeenCalledTimes(2);
        } finally {
            video.free();
        }
    });
});
