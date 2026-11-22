import { readFileSync } from 'node:fs';

import { describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref } from 'vue';

import { defaultMouseTraceAppearance, mouseTraceAppearanceProps, mouseTraceRange, readMouseTrace, readMouseTraceAsync, sliderToTailSeconds, tailSecondsToSlider } from './mouseTrace';
import type { ReplayMouseTraceEvent } from './mouseTrace';
import { parseReplay } from './replayParser';
import type { ReplayVideo } from './replayParser';
import { useReplayPosition } from './useReplayPosition';

const events: ReplayMouseTraceEvent[] = [
    { timeMs: 100, eventIndex: 0 }, { timeMs: 100, eventIndex: 2 }, { timeMs: 100, eventIndex: 4 },
    { timeMs: 200, eventIndex: 5 }, { timeMs: 200, eventIndex: 7 }, { timeMs: 300, eventIndex: 9 },
].map((event) => ({ ...event, row: 1, column: 2, action: 'mv', state: 'uu' }));

describe('mouse trace appearance', () => {
    it('disables every marker by default, retaining independent library styles for later use', () => {
        const appearance = defaultMouseTraceAppearance();
        expect(appearance.lineWidth).toBe(0.08);
        expect(Object.values(appearance.markers).every((marker) => !marker.enabled)).toBe(true);
        expect(mouseTraceAppearanceProps(appearance).markers).toEqual({ lc: false, lr: false, rc: false, rr: false });
        appearance.color.uu = 'transparent';
        appearance.markers.lc.fill = '#123456';
        appearance.markers.lr.enabled = true;
        const fresh = defaultMouseTraceAppearance();
        expect(fresh.color.uu).toBe('#ffffff');
        expect(fresh.markers.lc.fill).toBe('#ffdf00');
        expect(fresh.markers.lr.enabled).toBe(false);
    });

    it('passes all supported visual props and preserves hidden marker settings', () => {
        const appearance = defaultMouseTraceAppearance();
        appearance.lineWidth = 0.2;
        appearance.color.dd = 'rgba(0,0,0,0)';
        appearance.markers.lc = { enabled: true, shape: 'square', size: 0.8, fill: '#123456', stroke: 'transparent', strokeWidth: 0.03, opacity: 0.4 };
        appearance.markers.lr.enabled = false;
        appearance.markers.lr.size = 0.9;
        const props = mouseTraceAppearanceProps(appearance);
        expect(props.lineWidth).toBe(0.2);
        expect(props.color.dd).toBe('rgba(0,0,0,0)');
        expect(props.markers.lc).toEqual({ shape: 'square', size: 0.8, fill: '#123456', stroke: 'transparent', strokeWidth: 0.03, opacity: 0.4 });
        expect(props.markers.lr).toBe(false);
        appearance.markers.lr.enabled = true;
        expect(mouseTraceAppearanceProps(appearance).markers.lr).toMatchObject({ size: 0.9 });
        expect(props.markers.lr).toBe(false);
    });
});

describe('mouse trace range', () => {
    it.each([
        [200, 0.1, 0, 5], [250, 0.1, 0, 5], [250, 0.025, 3, 5],
        [100, 0, 0, 3], [150, 0, 0, 3], [250, 0, 3, 5],
        [50, 0, 0, 0], [400, Infinity, 0, 6], [250, Infinity, 0, 5],
    ])('selects the longest left-inclusive range at %s ms with %s s tail', (ms, tail, startIndex, endIndex) => {
        expect(mouseTraceRange(events, ms, tail)).toEqual({ startIndex, endIndex });
    });

    it('uses original event indexes while playing, including skipped non-mouse events', () => {
        expect(mouseTraceRange(events, 250, 0, 5)).toEqual({ startIndex: 3, endIndex: 4 });
        expect(mouseTraceRange(events, 150, 0, 1)).toEqual({ startIndex: 0, endIndex: 1 });
        expect(mouseTraceRange(events, 250, Infinity, 5)).toEqual({ startIndex: 0, endIndex: 4 });
        expect(mouseTraceRange(events, 250, 0)).toEqual({ startIndex: 3, endIndex: 5 });
    });

    it('handles empty traces and backwards/loop seeks without retaining old indexes', () => {
        expect(mouseTraceRange([], 500, 1)).toEqual({ startIndex: 0, endIndex: 0 });
        expect(mouseTraceRange(events, 300, 0)).toEqual({ startIndex: 5, endIndex: 6 });
        expect(mouseTraceRange(events, 100, 0)).toEqual({ startIndex: 0, endIndex: 3 });
        expect(mouseTraceRange(events, 0, 1)).toEqual({ startIndex: 0, endIndex: 0 });
    });

    it('maps slider endpoints, default and arbitrary precision without quantization', () => {
        expect(sliderToTailSeconds(0)).toBe(0);
        expect(sliderToTailSeconds(0.5)).toBe(1);
        expect(sliderToTailSeconds(1)).toBe(Infinity);
        expect(tailSecondsToSlider(Infinity)).toBe(1);
        const value = 0.123456789012345;
        expect(sliderToTailSeconds(value)).toBe(value / (1 - value));
        expect(tailSecondsToSlider(sliderToTailSeconds(value))).toBeCloseTo(value, 14);
    });
});

describe('replay mouse trace', () => {
    it('converts actions and button states, skips non-mouse records and frees wrappers', () => {
        const actions = ['mv', 'rc', 'rr', 'lc', 'lr', 'cc', 'mc', 'pf'];
        const states = ['uu', 'ud', 'ud', 'du', 'dd', 'dd', 'du', 'uu'];
        const records = actions.map((mouse, index) => {
            const payload = { mouse, x: 24, y: 40, free: vi.fn() };
            const event = { is_mouse: () => true, unwrap_mouse: () => payload, free: vi.fn() };
            return { event, time: 0.039 + index, mouse_state: index + 1, free: vi.fn() };
        });
        const nonMouse = { event: { is_mouse: () => false, free: vi.fn() }, free: vi.fn() };
        const video = { events: [nonMouse, ...records], pix_size: 16, video_start_time: -0.039 } as unknown as ReplayVideo;
        const trace = readMouseTrace(video);
        expect(trace).toHaveLength(8);
        trace.forEach((event, index) => {
            expect(event).toMatchObject({ row: 2.5, column: 1.5, state: states[index], eventIndex: index + 1 });
            expect(event.timeMs).toBeCloseTo(index * 1000);
            expect(event.action).toBe(index < 5 ? actions[index] : 'mv');
            expect(records[index].event.unwrap_mouse().free).toHaveBeenCalledOnce();
            expect(records[index].event.free).toHaveBeenCalledOnce();
            expect(records[index].free).toHaveBeenCalledOnce();
        });
        expect(nonMouse.free).toHaveBeenCalledOnce();
        expect(nonMouse.event.free).toHaveBeenCalledOnce();
    });

    it('reports progress while building the trace asynchronously', async () => {
        const records = ['mv', 'lc', 'pf'].map((mouse, index) => {
            const payload = { mouse, x: 16, y: 32, free: vi.fn() };
            const event = { is_mouse: () => true, unwrap_mouse: () => payload, free: vi.fn() };
            return { event, time: index, mouse_state: 4, free: vi.fn() };
        });
        const video = { events: records, pix_size: 16, video_start_time: 0 } as unknown as ReplayVideo;
        const progress: [number, number][] = [];
        const trace = await readMouseTraceAsync(video, async (done, total) => {
            progress.push([done, total]);
        });
        expect(trace).toHaveLength(2);
        expect(progress.at(-1)).toEqual([3, 3]);
        for (const record of records) expect(record.free).toHaveBeenCalledOnce();
    });

    it('frees all record wrappers when extraction fails', () => {
        const event = { is_mouse: () => true,
            unwrap_mouse: () => {
                throw new Error('Invalid mouse');
            },
            free: vi.fn() };
        const records = [{ event, free: vi.fn() }, { free: vi.fn() }];
        expect(() => readMouseTrace({ events: records, pix_size: 16, video_start_time: 0 } as unknown as ReplayVideo)).toThrow('Invalid mouse');
        expect(event.free).toHaveBeenCalledOnce();
        for (const record of records) expect(record.free).toHaveBeenCalledOnce();
    });

    for (const [filename, software] of [
        ['52200.evf', 'e'], ['Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', 'a'],
        ['Lin_Jin_Fan_Exp_60.623bv207.mvf', 'm'], ['3819-Time-1616-NF-9469-32-20151031.rmv', 'r'],
    ] as const) {
        it(`keeps plain trace snapshots and synchronizes with the positioned event index for ${filename}`, async () => {
            const bytes = Uint8Array.from(readFileSync(new URL(`../../../cypress/fixtures/${filename}`, import.meta.url)));
            const video = parseReplay(bytes.buffer, filename, software);
            const scope = effectScope();
            try {
                const trace = readMouseTrace(video);
                expect(trace.length).toBeGreaterThan(0);
                expect(trace.every((event) => Number.isFinite(event.row) && Number.isFinite(event.column))).toBe(true);
                const currentMs = ref(0);
                const position = scope.run(() => useReplayPosition(video, currentMs));
                if (position === undefined) throw new Error('Position scope did not start');
                for (const ms of [5000, video.rtime_ms, 0]) {
                    currentMs.value = ms;
                    await nextTick();
                    expect(position.currentEventIndex.value).toBe(video.current_event_id);
                    const range = mouseTraceRange(trace, ms, 1, position.currentEventIndex.value);
                    expect(range.endIndex).toBe(trace.filter((event) => event.eventIndex <= video.current_event_id).length);
                    expect(range.startIndex).toBeLessThanOrEqual(range.endIndex);
                    expect(video.game_board).toEqual(position.gameBoard.value);
                }
            } finally {
                scope.stop();
                video.free();
            }
        });
    }
});
