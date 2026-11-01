import type { VueWrapper } from '@vue/test-utils';
import { toRefs } from '@vueuse/core';
import { defineComponent, h, ref, shallowRef } from 'vue';
import type { VueDraggable } from 'vue-draggable-plus';

import { defaultAnalyzerConfig } from './config';
import { counterVariables, defaultCounterConfig, prepareCounters } from './counter';
import type { CounterEvent, CounterValues, PreparedCounter } from './counter';
import { defaultCustomEvent } from './customEvents';
import type { CustomEventDefinition } from './customEvents';
import { addTimelineTrack, defaultTimelineConfig, timelinePadding } from './timeline';
import type { TimelineConfig, TimeWindow } from './timeline';
import TimelinePanel from './TimelinePanel.vue';
import { provideAnalyzerState } from './useAnalyzerState';
import { usePlayback } from './usePlayback';
import type { PlaybackController } from './usePlayback';

import i18n from '@/i18n';
import { createAnalyzerTestState } from '@cy/support/analyzerState';

function emptyTimelineConfig(): TimelineConfig {
    return { ...defaultTimelineConfig(), slots: [[], []] };
}

function mountTimeline(config: TimelineConfig = emptyTimelineConfig(), width = 800, definitions: CustomEventDefinition[] = [], durationMs = 20000) {
    const counterConfig = defaultCounterConfig();
    counterConfig.rows = [{ ...counterConfig.rows[0], key: 'bvs', expression: 'left', samplingMode: 'button' }];
    counterConfig.rows.push({ ...counterConfig.rows[0], key: 'path', expression: 'path' });
    const events: CounterEvent[] = [0, 5000, 10000, 20000].map((timeMs, index) => ({ timeMs, eventIndex: index, button: true, boardChanged: true, values: { ...Object.fromEntries(counterVariables.map((key) => [key, index * 2])) as CounterValues, path: index * 100 } }));
    const analyzerConfig = ref(defaultAnalyzerConfig());
    analyzerConfig.value.counter = counterConfig;
    analyzerConfig.value.timeline = config;
    analyzerConfig.value.customEvents = definitions;
    const { timeline: stored, customEvents } = toRefs(analyzerConfig, { replaceRef: false });
    const timeWindow = ref<TimeWindow>({ startMs: 0, endMs: durationMs });
    const counters = shallowRef(prepareCounters(counterConfig.rows, events));
    let playback: PlaybackController;
    cy.viewport(1000, 720);
    cy.mount(defineComponent({
        expose: [],
        setup() {
            playback = usePlayback(durationMs);
            provideAnalyzerState(createAnalyzerTestState({ config: analyzerConfig, playback, counterEvents: shallowRef(events), preparedCounters: counters, timeWindow }));
            return () => h('div', { style: { width: `${width}px`, height: '450px' } }, [
                h(TimelinePanel),
            ]);
        },
    }), { global: { plugins: [i18n], stubs: { transition: false } } });
    cy.get('.video-analyzer-timeline__ruler').should(($ruler) => {
        expect($ruler[0].clientWidth).to.be.greaterThan(200);
    });
    return { stored, customEvents, timeWindow, counters, playback: () => playback };
}

function addTrack(slot: number, key = 'bvs') {
    cy.get('.timeline-slot__add-track').eq(slot).click();
    cy.get('.timeline-slot__track-select:visible').select(key);
}

function wheel(selector: string, deltaY: number, ctrlKey = false) {
    cy.get(selector).first().then(($plot) => {
        const rect = $plot[0].getBoundingClientRect();
        cy.wrap($plot).trigger('wheel', { eventConstructor: 'WheelEvent', deltaY, clientX: rect.left + timelinePadding.left + (rect.width - timelinePadding.left - timelinePadding.right) / 2, clientY: rect.top + rect.height / 2, ctrlKey });
    });
}

function drag(selector: string, dx: number, dy = 0) {
    cy.get(selector).first().scrollIntoView();
    cy.get(selector).first().should('be.visible').realMouseDown();
    cy.get(selector).first().realMouseMove(6, 0, { position: 'center', scrollBehavior: false });
    cy.get(selector).first().realMouseMove(dx, dy, { position: 'center', scrollBehavior: false });
    cy.get(selector).first().realMouseUp({ position: 'center', scrollBehavior: false });
}

describe('<TimelinePanel />', () => {
    it('renders a long millisecond series after loading and retains the full y range while zooming and hovering', () => {
        const config = emptyTimelineConfig();
        addTimelineTrack(config, 0, 'bvs');
        const { counters, timeWindow } = mountTimeline(config, 800, [], 250000);
        cy.then(() => {
            const samples = Array.from({ length: 250001 }, (_, index) => ({ timeMs: index, eventIndex: index, value: index === 240000 ? 1000 : 5 }));
            counters.value = new Map([['bvs', { samples, formatter: String, error: '' }]]);
        });
        cy.get('.timeline-slot').first().find('.plot-axis--vertical text').should(($labels) => {
            const values = [...$labels].map((label) => Number(label.textContent));
            expect(values.some((value) => value >= 1000)).to.eq(true);
        });
        cy.get('.timeline-slot').first().find('.timeline-plot__line path').should(($paths) => {
            expect($paths).to.have.length(1);
            const data = $paths[0].getAttribute('d') ?? '';
            const width = $paths[0].closest('svg')?.clientWidth ?? 0;
            expect(width).to.be.greaterThan(0);
            const commands = data.match(/[ML]/g) ?? [];
            expect(commands.length).to.be.greaterThan(0).and.at.most(4 * (Math.ceil(width) + 1));
            expect(data).not.to.match(/NaN|Infinity/);
            expect(counters.value.get('bvs')?.samples.length).to.eq(250001);
        });
        cy.then(() => {
            timeWindow.value = { startMs: 0, endMs: 10000 };
        });
        cy.get('.timeline-slot').first().find('.plot-axis--vertical text').should(($labels) => {
            const values = [...$labels].map((label) => Number(label.textContent));
            expect(values.some((value) => value >= 1000)).to.eq(true);
        });
        cy.get('.timeline-slot__plot').first().realHover();
        cy.get('.timeline-plot__values output').should('contain.text', 'bvs: 5');
    });

    it('renders major time labels and shorter minor ticks, updating them with the time window', () => {
        const { timeWindow } = mountTimeline();
        cy.get('.video-analyzer-timeline__ruler .timeline-plot__time-label').should(($labels) => {
            expect($labels.first().text().trim()).to.eq('0');
            expect($labels.last().text().trim()).to.eq('20');
            const ruler = $labels.closest('.timeline-plot')[0].getBoundingClientRect();
            for (const label of $labels) {
                const bounds = label.getBoundingClientRect();
                expect(bounds.width).to.be.greaterThan(0);
                expect(bounds.height).to.be.greaterThan(0);
                expect(bounds.left).to.be.at.least(ruler.left);
                expect(bounds.right).to.be.at.most(ruler.right);
                expect(bounds.top).to.be.at.least(ruler.top);
                expect(bounds.bottom).to.be.at.most(ruler.bottom);
            }
        });
        cy.get('.video-analyzer-timeline__ruler .plot-axis__tick > line').should(($ticks) => {
            const lengths = [...$ticks].map((tick) => Number(tick.getAttribute('y2')) - Number(tick.getAttribute('y1')));
            expect(lengths).to.include(4).and.include(2);
            for (const tick of $ticks) {
                if (Number(tick.getAttribute('y2')) - Number(tick.getAttribute('y1')) === 2) expect(tick.parentElement?.querySelector('text')?.textContent?.trim()).to.eq('');
            }
        });
        cy.then(() => {
            timeWindow.value = { startMs: 5000, endMs: 10000 };
        });
        cy.get('.video-analyzer-timeline__ruler .timeline-plot__time-label').should(($labels) => {
            expect($labels.first().text().trim()).to.eq('5');
            expect($labels.last().text().trim()).to.eq('10');
        });
        cy.then(() => {
            timeWindow.value = { startMs: 12000, endMs: 12500 };
        });
        cy.get('.video-analyzer-timeline__ruler .timeline-plot__time-label').should(($labels) => {
            expect($labels.first().text().trim()).to.eq('12');
            expect($labels.last().text().trim()).to.eq('12.5');
        });
    });

    it('starts empty, manages plot names, confirms deletion, and allows adding after deleting all plots', () => {
        const { stored } = mountTimeline();
        cy.get('.timeline-slot').should('have.length', 2);
        cy.get('.timeline-slot__name').first().should('have.text', 'Plot 1');
        cy.get('.video-analyzer-timeline__add-slot').should('have.attr', 'aria-label', 'Add plot');
        cy.get('.timeline-slot__legend-button').should('not.exist');
        cy.get('.timeline-slot__rename').first().click();
        cy.get('.timeline-slot__name-input').clear();
        cy.get('.timeline-slot__name-input').type('Measurements');
        cy.get('.timeline-slot__confirm').click();
        cy.get('.timeline-slot__name').first().should('have.text', 'Measurements');
        cy.get('.timeline-slot__delete').first().click();
        cy.get('.timeline-slot__cancel').click();
        cy.get('.timeline-slot').should('have.length', 2);
        for (let index = 0; index < 2; index++) {
            cy.get('.timeline-slot__delete').first().click();
            cy.get('.timeline-slot__confirm').click();
        }
        cy.get('.timeline-slot').should('not.exist');
        cy.get('.video-analyzer-timeline__add-slot').click();
        cy.get('.timeline-slot').should('have.length', 1).and(() => {
            expect(stored.value.slots).to.deep.eq([[]]);
        });
    });

    it('preserves duplicate tracks and colors, and removes only the selected legend entry', () => {
        const { stored } = mountTimeline();
        addTrack(0);
        addTrack(0);
        addTrack(1);
        cy.get('.timeline-slot').first().find('.timeline-slot__legend-button').should('have.length', 2);
        cy.get('.timeline-slot').first().find<SVGPathElement>('.timeline-plot__line path').should('have.length', 2).and(($paths) => {
            for (const path of $paths) expect(path.getTotalLength()).to.be.greaterThan(0);
        });
        cy.get('.timeline-slot__legend-button').first().click();
        cy.get('.timeline-slot__remove-track:visible').click();
        cy.get('.timeline-slot__legend-button').should('have.length', 2).and(() => {
            expect(stored.value.slots.map((slot) => slot.map((track) => track.color))).to.deep.eq([['#f28e2c'], ['#4e79a7']]);
        });
    });

    it('keeps invalid keys in place without drawing or hover values and permits manual removal', () => {
        const config = emptyTimelineConfig();
        addTimelineTrack(config, 0, 'missing');
        addTimelineTrack(config, 0, 'bvs');
        const { stored } = mountTimeline(config);
        cy.get('.timeline-slot__legend-button--missing').should('have.text', 'missing');
        cy.get('.timeline-slot').first().find('.timeline-plot__line').should('have.length', 1);
        cy.get('.timeline-slot__plot').first().realHover();
        cy.get('.timeline-plot__values output').should('have.length', 1).and('contain.text', 'bvs:');
        cy.get('.timeline-slot__legend-button--missing').click();
        cy.get('.timeline-slot__remove-track:visible').click();
        cy.get('.timeline-slot__legend-button').should('have.length', 1).and(() => {
            expect(stored.value.slots[0]).to.deep.eq([{ key: 'bvs', color: '#f28e2c' }]);
        });
    });

    it('aligns ruler and plots, shares hover values, and redraws all references after changing counter data', () => {
        const config = emptyTimelineConfig();
        addTimelineTrack(config, 0, 'bvs');
        addTimelineTrack(config, 0, 'path');
        addTimelineTrack(config, 1, 'bvs');
        const { counters } = mountTimeline(config, 500);
        cy.get('.video-analyzer-timeline__ruler').should(($ruler) => {
            const ruler = $ruler[0].getBoundingClientRect();
            const panel = $ruler[0].closest('.video-analyzer-timeline');
            if (!panel) throw new Error('Missing timeline panel');
            expect(ruler.left - panel.getBoundingClientRect().left).to.be.closeTo(46, 1);
            for (const plot of $ruler[0].ownerDocument.querySelectorAll('.timeline-slot__plot')) {
                const rect = plot.getBoundingClientRect();
                expect(rect.left).to.be.closeTo(ruler.left, 1);
                expect(rect.width).to.be.closeTo(ruler.width, 1);
                const current = plot.querySelector('.timeline-plot__current');
                if (!current) throw new Error('Missing current time line');
                expect(current.getBoundingClientRect().left).to.be.closeTo(ruler.left + 4, 1);
            }
        });
        cy.get('.timeline-plot__y-axis text').should(($labels) => {
            for (const label of $labels) {
                const element = label.closest('.timeline-slot__plot');
                if (!element) throw new Error('Missing timeline plot');
                const plot = element.getBoundingClientRect();
                const rect = label.getBoundingClientRect();
                expect(rect.left).to.be.at.least(plot.left);
                expect(rect.right).to.be.at.most(plot.right);
            }
        });
        cy.get('.timeline-slot__plot').first().realHover();
        cy.get('.timeline-plot__hover').should('have.length', 3);
        cy.get('.timeline-plot__values output').should('have.length', 3);
        cy.then(() => {
            const changed: PreparedCounter = { samples: [{ timeMs: 0, eventIndex: 0, value: 42 }, { timeMs: 20000, eventIndex: 3, value: 42 }], formatter: (value) => value.toFixed(1), error: '' };
            counters.value = new Map([...counters.value, ['bvs', changed]]);
        });
        cy.get('.timeline-plot__values output').filter(':contains("bvs:")').should('have.length', 2).and('contain.text', '42.0');
    });

    it('zooms only on the ruler and pans within replay bounds without seeking, leaving plot and modifier wheel untouched', () => {
        const { timeWindow, playback } = mountTimeline();
        drag('.video-analyzer-timeline__ruler', -50);
        cy.then(() => expect(timeWindow.value).to.deep.eq({ startMs: 0, endMs: 20000 }));
        wheel('.timeline-slot__plot', -500);
        cy.get('.video-analyzer-timeline__ruler').should('not.have.class', 'timeline-plot--pannable').and(() => {
            expect(timeWindow.value).to.deep.eq({ startMs: 0, endMs: 20000 });
        });
        wheel('.video-analyzer-timeline__ruler', -500);
        cy.get('.video-analyzer-timeline__ruler').should('have.class', 'timeline-plot--pannable').and(() => {
            expect(timeWindow.value.endMs - timeWindow.value.startMs).to.be.lessThan(20000);
        });
        cy.get('.video-analyzer-timeline__ruler').then(($ruler) => {
            const plotWidth = $ruler[0].getBoundingClientRect().width - timelinePadding.left - timelinePadding.right;
            const remainingMs = playback().durationMs.value - timeWindow.value.endMs;
            const spanMs = timeWindow.value.endMs - timeWindow.value.startMs;
            const distance = remainingMs / spanMs * plotWidth;
            // Keep each real pointer gesture inside the viewport and overshoot to exercise clamping.
            const step = Math.floor(plotWidth / 3);
            for (let index = 0; index < Math.ceil(distance / step) + 1; index++) drag('.video-analyzer-timeline__ruler', -step);
        });
        cy.get('.video-analyzer-timeline__ruler').should(() => {
            expect(timeWindow.value.endMs).to.be.closeTo(20000, 0.01);
            expect(playback().currentMs.value).to.eq(0);
        });
        cy.then(() => {
            const previous = { ...timeWindow.value };
            wheel('.timeline-slot__plot', 500);
            cy.get('.video-analyzer-timeline__ruler').should(() => {
                expect(timeWindow.value).to.deep.eq(previous);
            });
            wheel('.video-analyzer-timeline__ruler', -500, true);
            cy.get('.video-analyzer-timeline__ruler').should(() => {
                expect(timeWindow.value).to.deep.eq(previous);
            });
        });
        wheel('.video-analyzer-timeline__ruler', 500);
        cy.get('.timeline-slot__plot').should('have.length', 2);
    });

    it('seeks on click and drag while preserving paused/playing state and shares interval markers', () => {
        const { playback } = mountTimeline();
        cy.get('.timeline-slot__plot').first().realClick();
        cy.get('.timeline-plot__current').should(() => {
            expect(playback().currentMs.value).to.be.within(8000, 11000);
            expect(playback().isPlaying.value).to.eq(false);
        });
        cy.then(() => {
            playback().seek(2000);
            playback().setRangeStart();
            playback().seek(16000);
            playback().setRangeEnd();
            playback().play();
        });
        cy.get('.timeline-plot__range-start').should('have.length', 3);
        cy.get('.timeline-plot__range-end').should('have.length', 3);
        drag('.timeline-slot__plot', 100);
        let releasedMs = 0;
        cy.get('.timeline-plot__current').should(() => {
            expect(playback().isPlaying.value).to.eq(true);
            expect(playback().currentMs.value).to.be.within(10000, 17000);
        }).then(() => {
            releasedMs = playback().currentMs.value;
        });
        cy.get('.timeline-plot__current').should(() => {
            expect(playback().currentMs.value).to.be.greaterThan(releasedMs);
        });
        cy.then(() => {
            playback().pause();
        });
    });

    it('resizes only the target slot and keeps settings and track arrays paired when sorting', () => {
        const config = emptyTimelineConfig();
        addTimelineTrack(config, 0, 'bvs');
        const { stored } = mountTimeline(config);
        drag('.timeline-slot__resize-bottom', 0, 30);
        cy.get('.timeline-slot').first().should(() => {
            expect(stored.value.slotSettings[0].height).to.be.greaterThan(160);
            expect(stored.value.slotSettings[1].height).to.eq(160);
        });
        cy.get<VueWrapper>('@vue').then((wrapper) => {
            const sortable = wrapper.findComponent<typeof VueDraggable>('.video-analyzer-timeline__slots');
            const entries = sortable.props('modelValue');
            sortable.vm.$emit('update:modelValue', [...entries].reverse());
        });
        cy.get('.timeline-slot__name').first().should('have.text', 'Plot 2').and(() => {
            expect(stored.value.slots[0]).to.deep.eq([]);
            expect(stored.value.slots[1][0].key).to.eq('bvs');
            expect(stored.value.slotSettings[1].height).to.be.greaterThan(160);
        });
    });

    it('adds, edits, validates, reorders and deletes independent custom events without changing slots', () => {
        const { customEvents, stored } = mountTimeline();
        cy.get('.timeline-event-row').should('not.exist');
        cy.get('.video-analyzer-timeline__add-buttons').find('button').should('have.length', 2);
        cy.get('.video-analyzer-timeline__add-event').click();
        cy.get('.custom-event-editor__key').type('bvs');
        cy.get('.custom-event-editor__expression').type('d(left) > 0');
        cy.get('.custom-event-editor__shape').select('diamond');
        cy.get('.custom-event-editor__marker-size').clear();
        cy.get('.custom-event-editor__marker-size').type('24');
        cy.get('.custom-event-editor__preview').should('contain.text', '3');
        cy.get('.custom-event-editor .counter-expression-help__link').should('be.visible').and('have.attr', 'target', '_blank');
        cy.get('.custom-event-editor .counter-expression-help__link').should('have.attr', 'href').and('match', /\/docs\/guide\/replay-expressions$/);
        cy.get('.custom-event-editor__save').click();
        cy.get('.timeline-event-row__key').should('have.text', 'bvs');
        cy.get('.timeline-plot__event-pulses .plot-scatter__point').should('have.length', 3);
        cy.get('.timeline-event-row__settings').click();
        cy.get('.custom-event-editor__key').clear();
        cy.get('.custom-event-editor__key').type('renamed');
        cy.get('.custom-event-editor__cancel').click();
        cy.get('.custom-event-editor').should('not.exist');
        cy.get('.timeline-event-row__key').should('have.text', 'bvs');
        cy.get('.timeline-event-row__settings').click();
        cy.get('.custom-event-editor__key').clear();
        cy.get('.custom-event-editor__key').type('renamed');
        cy.get('.custom-event-editor__marker-size').clear();
        cy.get('.custom-event-editor__marker-size').type('40');
        cy.get('.custom-event-editor__save').click();
        cy.get('.timeline-event-row__key').should('have.text', 'renamed');
        cy.get('.timeline-plot__event-pulses polygon').should('have.attr', 'points', '0,-4 4,0 0,4 -4,0').and(() => {
            expect(customEvents.value[0].marker.size).to.eq(40);
        });
        cy.get('.video-analyzer-timeline__add-event').click();
        cy.get('.custom-event-editor__key').type('renamed');
        cy.get('.custom-event-editor__expression').type('true');
        cy.get('.custom-event-editor__save').click();
        cy.get('.custom-event-editor [role="alert"]').should('contain.text', 'unique');
        cy.get('.custom-event-editor__key').clear();
        cy.get('.custom-event-editor__key').type('held');
        cy.get('.custom-event-editor__types').contains('button', 'Sustained').click();
        cy.get('.custom-event-editor__line-style').select('dash');
        cy.get('.custom-event-editor__save').click();
        cy.get('.timeline-event-row').should('have.length', 2);
        cy.get<VueWrapper>('@vue').then((wrapper) => {
            const sortable = wrapper.findComponent<typeof VueDraggable>('.video-analyzer-timeline__events');
            const entries = sortable.props('modelValue');
            sortable.vm.$emit('update:modelValue', [...entries].reverse());
        });
        cy.get('.timeline-event-row__key').first().should('have.text', 'held').and(() => {
            expect(customEvents.value.map((event) => event.key)).to.deep.eq(['held', 'renamed']);
            expect(customEvents.value[0].line.style).to.eq('dash');
            expect(customEvents.value[1].marker.shape).to.eq('diamond');
        });
        cy.get('.timeline-event-row__settings').first().click();
        cy.get('.custom-event-editor__delete').click();
        cy.get('.timeline-event-row').should('have.length', 1).and(() => {
            expect(customEvents.value.map((event) => event.key)).to.deep.eq(['renamed']);
            expect(stored.value.slots).to.deep.eq([[], []]);
        });
    });

    it('shares one board-style Tippy across event axes, omits native titles and booleans and shows full span times', () => {
        const definitions: CustomEventDefinition[] = [
            { ...defaultCustomEvent(), key: 'numeric', expression: 'd(left)' },
            { ...defaultCustomEvent(), key: 'boolean', expression: 'd(left) > 0' },
            { ...defaultCustomEvent(), key: 'string', expression: 'd(left) > 0 ? "<b>text</b>" : ""' },
            { ...defaultCustomEvent(), key: 'held', expression: 'left > 0 and left < 4', type: 'sustained' },
        ];
        const { timeWindow } = mountTimeline(emptyTimelineConfig(), 600, definitions);
        let instance: unknown;
        cy.get<HTMLElement & { _tippy?: unknown }>('.video-analyzer-timeline').then(($timeline) => {
            instance = $timeline[0]._tippy;
            expect(instance).to.exist;
        });
        cy.get('.timeline-event-row__key').should('not.have.attr', 'title');
        cy.get('.timeline-event-row__plot title').should('not.exist');
        const point = (index: number) => cy.get('.timeline-event-row').eq(index).find('.plot-scatter__point').first();
        point(0).realHover();
        cy.get('.timeline-event-tooltip:visible').should('have.length', 1);
        cy.get('.event-tooltip__time:visible').should('have.text', 'Time: 5.000 s');
        cy.get('.event-tooltip__value:visible').should('have.text', 'Value: 2');
        point(1).realHover();
        cy.get('.event-tooltip__time:visible').should('have.text', 'Time: 5.000 s');
        cy.get('.event-tooltip__value:visible').should('not.exist');
        point(2).realHover();
        cy.get('.event-tooltip__value:visible').should('have.text', 'Value: <b>text</b>');
        cy.get('.event-tooltip__value:visible b').should('not.exist');
        cy.get('.timeline-plot__event-span-hit').realHover();
        cy.get('.timeline-event-tooltip:visible').should('have.length', 1).within(() => {
            cy.get('strong').should('have.text', 'held');
            cy.get('.event-tooltip__start').should('have.text', 'Start: 5.000 s');
            cy.get('.event-tooltip__end').should('have.text', 'End: 10.000 s');
            cy.get('.event-tooltip__duration').should('have.text', 'Duration: 5.000 s');
        });
        cy.then(() => {
            timeWindow.value = { startMs: 6000, endMs: 8000 };
        });
        cy.get('.timeline-event-tooltip:visible').should('not.exist');
        cy.get('.video-analyzer-timeline__ruler').realHover();
        cy.get('.timeline-plot__event-span-hit').realHover();
        cy.get('.event-tooltip__start:visible').should('have.text', 'Start: 5.000 s');
        cy.get('.event-tooltip__end:visible').should('have.text', 'End: 10.000 s');
        cy.get('.event-tooltip__duration:visible').should('have.text', 'Duration: 5.000 s');
        cy.get<HTMLElement & { _tippy?: unknown }>('.video-analyzer-timeline').should(($timeline) => {
            expect($timeline[0]._tippy).to.eq(instance);
        });
        cy.then(() => {
            timeWindow.value = { startMs: 10000, endMs: 20000 };
        });
        cy.get('.timeline-event-tooltip:visible').should('not.exist');
        point(0).realHover();
        cy.get('.event-tooltip__time:visible').should('have.text', 'Time: 10.000 s');
        cy.get('.video-analyzer-timeline__ruler').realHover();
        cy.get('.timeline-event-tooltip:visible').should('not.exist');
    });

    it('aligns custom event marks with the shared time window, hover and playback position', () => {
        const definitions: CustomEventDefinition[] = [
            { ...defaultCustomEvent(), key: 'pulse', expression: 'd(left) > 0' },
            { ...defaultCustomEvent(), key: 'held', expression: 'left > 0', type: 'sustained', line: { style: 'dot', width: 3, opacity: 0.5 } },
        ];
        const { timeWindow, playback } = mountTimeline(emptyTimelineConfig(), 600, definitions);
        cy.get('.video-analyzer-timeline__slots').should('have.css', 'border-top-width', '1px');
        cy.get('.timeline-event-row').should('have.length', 2).and(($rows) => {
            for (const row of $rows) {
                expect(getComputedStyle(row).borderBottomWidth).to.eq('0px');
                expect(row.getBoundingClientRect().height).to.eq(24);
            }
            expect($rows[1].getBoundingClientRect().top).to.be.closeTo($rows[0].getBoundingClientRect().bottom, 0.5);
        });
        cy.get<SVGLineElement>('.timeline-plot__event-axis > line').should('have.length', 2).and(($axes) => {
            for (const axis of $axes) {
                expect(Number(axis.getAttribute('x2'))).to.be.greaterThan(Number(axis.getAttribute('x1')));
                expect(axis.getAttribute('y1')).to.eq(axis.getAttribute('y2'));
            }
        });
        cy.get<SVGPathElement>('.timeline-plot__event-span path').should('have.length', 1).and(($path) => {
            expect($path[0].getTotalLength()).to.be.greaterThan(0);
            expect($path[0].getAttribute('stroke-width')).to.eq('3');
            expect(getComputedStyle($path[0]).strokeDasharray).to.eq('1px, 3px');
        });
        cy.get('.video-analyzer-timeline__ruler').should(($ruler) => {
            const rect = $ruler[0].getBoundingClientRect();
            for (const plot of $ruler[0].ownerDocument.querySelectorAll('.timeline-event-row__plot')) {
                expect(plot.getBoundingClientRect().left).to.be.closeTo(rect.left, 1);
                expect(plot.getBoundingClientRect().width).to.be.closeTo(rect.width, 1);
            }
        });
        cy.get('.timeline-event-row__plot').first().realHover();
        cy.get('.timeline-plot__hover').should('have.length', 5);
        cy.get('.timeline-event-row__plot').first().realClick();
        cy.get('.timeline-plot__current').should(() => {
            expect(playback().currentMs.value).to.be.within(8000, 11000);
        });
        cy.then(() => {
            timeWindow.value = { startMs: 10000, endMs: 20000 };
        });
        cy.get('.timeline-plot__event-pulses .plot-scatter__point').should('have.length', 2);
        cy.get('.timeline-event-row__plot').find('.timeline-plot__values').should('not.exist');
    });
});
