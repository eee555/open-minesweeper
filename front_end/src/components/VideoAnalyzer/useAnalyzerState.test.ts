import { describe, expect, it, vi } from 'vitest';
import { computed, createSSRApp, defineComponent, h, ref, shallowRef } from 'vue';
import type { ComputedRef } from 'vue';
import { renderToString } from 'vue/server-renderer';

import { defaultAnalyzerConfig } from './config';
import type { PreparedCounter } from './counter';
import { provideAnalyzerState, useAnalyzerState } from './useAnalyzerState';
import type { AnalyzerState } from './useAnalyzerState';

import { createAnalyzerTestState } from '../../../cypress/support/analyzerState';

describe('Analyzer instance state', () => {
    it('shares reactive references with descendants and keeps sibling instances isolated', async () => {
        const states: AnalyzerState[] = [];
        const snapshots: { state: AnalyzerState; currentMs: ComputedRef<number> }[] = [];
        const Consumer = defineComponent({
            setup() {
                const state = useAnalyzerState();
                snapshots.push({ state, currentMs: computed(() => state.playback.currentMs.value) });
                return () => h('span', state.filename.value);
            },
        });
        const Provider = defineComponent({
            setup() {
                const state = createAnalyzerTestState();
                states.push(state);
                provideAnalyzerState(state);
                return () => h('div', [h(Consumer), h(Consumer)]);
            },
        });
        await renderToString(createSSRApp({ render: () => h('main', [h(Provider), h(Provider)]) }));
        expect(snapshots.map((entry) => states.indexOf(entry.state))).toEqual([0, 0, 1, 1]);
        states[0].playback.seek(600);
        states[0].exporting.value = true;
        states[0].timeWindow.value = { startMs: 200, endMs: 800 };
        states[0].config.value.cursorVisible = false;
        expect(snapshots.map((entry) => entry.currentMs.value)).toEqual([600, 600, 0, 0]);
        expect(states[1].exporting.value).toBe(false);
        expect(states[1].timeWindow.value).toEqual({ startMs: 0, endMs: 1000 });
        expect(states[1].config.value.cursorVisible).toBe(true);
    });

    it('keeps external refs and reacts to replacement configs, frames, and samples', async () => {
        const config = ref(defaultAnalyzerConfig());
        const frame = shallowRef<AnalyzerState['frame']['value']>({ board: [[10]], globalBoard: [[0]], probabilityBoard: [[0]], cursorPosition: null, mouseState: 0, currentEventIndex: 0, nativeCellSize: 16 });
        const counters = shallowRef(new Map<string, PreparedCounter>());
        let state: AnalyzerState | undefined;
        const Consumer = defineComponent({ setup() { state = useAnalyzerState(); return () => null; } });
        await renderToString(createSSRApp({
            setup() {
                provideAnalyzerState(createAnalyzerTestState({ config, frame, preparedCounters: counters }));
                return () => h(Consumer);
            },
        }));
        expect(state?.config).toBe(config);
        expect(state?.frame).toBe(frame);
        config.value = { ...config.value, cursorSize: 40 };
        frame.value = { ...frame.value, mouseState: 5 };
        const nextCounters = new Map<string, PreparedCounter>();
        counters.value = nextCounters;
        expect(state?.config.value.cursorSize).toBe(40);
        expect(state?.frame.value.mouseState).toBe(5);
        expect(state?.preparedCounters.value).toBe(nextCounters);
    });

    it('reports a missing provider instead of returning a global fallback', async () => {
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        try {
            const Consumer = defineComponent({ setup() { useAnalyzerState(); return () => null; } });
            await expect(renderToString(createSSRApp(Consumer))).rejects.toThrow('Analyzer state must be provided');
        } finally {
            warn.mockRestore();
        }
    });
});
