import { describe, expect, it } from 'vitest';

import { defaultAnalyzerConfig } from './config';
import { counterVariables } from './counter';
import type { CounterEvent, CounterValues } from './counter';
import { defaultCustomEvent, eventLineDash, eventOccurs, prepareCustomEvents, prepareCustomEventsAsync } from './customEvents';
import type { CustomEventDefinition } from './customEvents';

function event(eventIndex: number, timeMs: number, left: number): CounterEvent {
    const values = Object.fromEntries(counterVariables.map((key) => [key, left])) as CounterValues;
    values.time = timeMs / 1000;
    return { eventIndex, timeMs, button: false, boardChanged: false, values };
}

function definition(expression: string, type: CustomEventDefinition['type'] = 'pulse'): CustomEventDefinition {
    return { ...defaultCustomEvent(), key: 'clicks', expression, type };
}

describe('custom events', () => {
    it('emits the default pluck pulse once per changed millisecond and preserves failure values', () => {
        const pluckEvent = defaultAnalyzerConfig().customEvents.find((entry) => entry.key === 'pluck');
        if (pluckEvent === undefined) throw new Error('Expected the default pluck event');
        const events = [event(0, 0, 0), event(1, 5, 0), event(2, 5, 0), event(3, 10, 0), event(4, 20, 0)];
        const values = [0, 0.1, 0.2, 0.2, Number.MAX_VALUE];
        events.forEach((entry, index) => {
            entry.values.pluck = values[index];
        });
        const prepared = prepareCustomEvents([pluckEvent], events, 22).get('pluck');
        expect(prepared?.spans).toEqual([]);
        expect(prepared?.pulses).toEqual([{ timeMs: 5, eventIndex: 2, value: 0.2 }, { timeMs: 20, eventIndex: 4, value: Number.MAX_VALUE }]);
        expect(events.at(-1)?.values.pluck).toBe(Number.MAX_VALUE);
    });

    it('uses native truthiness only for boolean, number and string results', () => {
        for (const value of [true, 1, -1, Infinity, -Infinity, '0', 'false', ' ']) expect(eventOccurs(value)).toBe(true);
        for (const value of [false, 0, -0, NaN, '', null, undefined, [], {}, () => true]) expect(eventOccurs(value)).toBe(false);
    });

    it('keeps the last native event per millisecond and falls back at every missing millisecond through replay end', () => {
        const events = [event(0, 0, 1), event(1, 0, 0), event(2, 5, 0), event(3, 5, 1), event(4, 1000, 2)];
        const original = structuredClone(events);
        const prepared = prepareCustomEvents([definition('left')], events, 1002).get('clicks');
        expect(prepared?.spans).toEqual([]);
        expect(prepared?.pulses).toHaveLength(998);
        expect(prepared?.pulses[0]).toEqual({ timeMs: 5, eventIndex: 3, value: 1 });
        expect(prepared?.pulses[994]).toEqual({ timeMs: 999, eventIndex: 3, value: 1 });
        expect(prepared?.pulses.slice(-3)).toEqual([1000, 1001, 1002].map((timeMs) => ({ timeMs, eventIndex: 4, value: 2 })));
        expect(events).toEqual(original);
    });

    it.each([['left > 0', undefined], ['left', 1], ['left ? "true" : ""', 'true']] as const)('accepts boolean, numeric and string expression %s', (expression, value) => {
        const prepared = prepareCustomEvents([definition(expression)], [event(0, 0, 0), event(1, 1, 1)], 2).get('clicks');
        const expectedValue = value === undefined ? {} : { value };
        expect(prepared?.pulses).toEqual([{ timeMs: 1, eventIndex: 1, ...expectedValue }, { timeMs: 2, eventIndex: 1, ...expectedValue }]);
    });

    it('retains exact evaluated pulse values without rounding, reevaluation or string conversion', () => {
        const events = [event(0, 0, 0), event(1, 1, 1)];
        expect(prepareCustomEvents([definition('left / 3')], events, 1).get('clicks')?.pulses).toEqual([{ timeMs: 1, eventIndex: 1, value: 1 / 3 }]);
        expect(prepareCustomEvents([definition('1 / 0')], events.slice(0, 1), 0).get('clicks')?.pulses).toEqual([{ timeMs: 0, eventIndex: 0, value: Infinity }]);
        expect(prepareCustomEvents([definition('"<b>text</b>"')], events.slice(0, 1), 0).get('clicks')?.pulses).toEqual([{ timeMs: 0, eventIndex: 0, value: '<b>text</b>' }]);
    });

    it('uses separate code and rendered endpoints, closing on false and extending an active tail to replay end', () => {
        const events = [event(0, 0, 0), event(1, 1, 1), event(2, 2, 1), event(3, 3, 0), event(4, 4, 1), event(5, 7, 1)];
        expect(prepareCustomEvents([definition('left', 'sustained')], events, 10).get('clicks')).toEqual({ pulses: [],
            spans: [
                { startMs: 1, endMs: 3, renderEndMs: 2, startEventIndex: 1, lastEventIndex: 2 },
                { startMs: 4, endMs: 10, renderEndMs: 10, startEventIndex: 4, lastEventIndex: 5 },
            ] });
    });

    it('treats invalid results and per-sample errors as false without keeping old values or stopping other definitions', () => {
        const events = [event(0, 0, 1), event(1, 1, 1), event(2, 2, 2), event(3, 3, 1), event(4, 4, 1), event(5, 5, 0)];
        for (const expression of ['left == 2 ? [left] : left', 'left == 2 ? d("invalid") : left']) {
            expect(prepareCustomEvents([definition(expression, 'sustained')], events, 6).get('clicks')?.spans).toEqual([
                { startMs: 0, endMs: 2, renderEndMs: 1, startEventIndex: 0, lastEventIndex: 1 },
                { startMs: 3, endMs: 5, renderEndMs: 4, startEventIndex: 3, lastEventIndex: 4 },
            ]);
        }
        const definitions = [definition('left +'), { ...definition('left'), key: 'valid' }];
        const prepared = prepareCustomEvents(definitions, events, 6);
        expect(prepared.get('clicks')).toEqual({ pulses: [], spans: [] });
        expect(prepared.get('valid')?.pulses).toHaveLength(5);
    });

    it.each(['unknown', 'left = 1', '[left]', 'roundTo', '0 / 0', 'false', '""'])('does not occur for invalid or false expression %s', (expression) => {
        expect(prepareCustomEvents([definition(expression)], [event(0, 0, 1)], 1).get('clicks')).toEqual({ pulses: [], spans: [] });
    });

    it('supports static variables, mouse state, library functions and nested sample-count differences after deduplication', () => {
        const events = [event(0, 0, 0), event(1, 0, 1), event(2, 1, 2), event(3, 2, 4), event(4, 3, 8)];
        const prepared = prepareCustomEvents([
            definition('d(d(left)) > 0'),
            { ...definition('d(left, 2) > 0'), key: 'step' },
            { ...definition('mouse_state == 4 and roundTo(bbbv / row, 1) == 1'), key: 'state' },
        ], events, 4);
        expect(prepared.get('clicks')?.pulses).toEqual([{ timeMs: 2, eventIndex: 3 }, { timeMs: 3, eventIndex: 4 }]);
        expect(prepared.get('step')?.pulses).toEqual([{ timeMs: 2, eventIndex: 3 }, { timeMs: 3, eventIndex: 4 }, { timeMs: 4, eventIndex: 4 }]);
        expect(prepared.get('state')?.pulses).toEqual([{ timeMs: 2, eventIndex: 3 }]);
    });

    it('does not fabricate events before a replay loads and provides independent style defaults', () => {
        expect(prepareCustomEvents([definition('true')], [], 0).get('clicks')).toEqual({ pulses: [], spans: [] });
        expect(prepareCustomEvents([], [event(0, 0, 1)], 1).size).toBe(0);
        const first = defaultCustomEvent();
        first.marker.size = 20;
        first.line.width = 5;
        expect(defaultCustomEvent().marker.size).toBe(8);
        expect(defaultCustomEvent().line.width).toBe(2);
        expect(['solid', 'dash', 'dot'].map((style) => eventLineDash(style as CustomEventDefinition['line']['style']))).toEqual(['none', '6 3', '1 3']);
    });

    it('prepares custom events asynchronously with the same results and progress', async () => {
        const events = [event(0, 0, 0), event(1, 1, 1)];
        const definitions = [definition('left')];
        const progress: [number, number][] = [];
        const prepared = await prepareCustomEventsAsync(definitions, events, 2, (done, total) => {
            progress.push([done, total]);
            return Promise.resolve();
        });
        expect(prepared.get('clicks')).toEqual(prepareCustomEvents(definitions, events, 2).get('clicks'));
        expect(progress.at(-1)).toEqual([1, 1]);
    });
});
