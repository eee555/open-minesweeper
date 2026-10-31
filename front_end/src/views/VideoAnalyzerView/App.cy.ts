import type { BoardForeground, BoardProbability, MinesweeperBoard, MouseTrace } from '@putianyi888/vue3-minesweeper-board';
import type { VueWrapper } from '@vue/test-utils';
import { defineComponent, h, ref } from 'vue';
import type { VNode } from 'vue';

import App from './App.vue';
import { analyzerConfig, defaultAnalyzerConfig } from './store';
import type { AnalyzerConfig } from './store';

import type BoardCursorLayer from '@/components/VideoAnalyzer/BoardCursorLayer.vue';
import type BoardPanel from '@/components/VideoAnalyzer/BoardPanel.vue';
import { displayCounter, prepareCounter } from '@/components/VideoAnalyzer/counter';
import type { CounterEvent } from '@/components/VideoAnalyzer/counter';
import type CounterPanel from '@/components/VideoAnalyzer/CounterPanel.vue';
import { defaultCustomEvent } from '@/components/VideoAnalyzer/customEvents';
import { mouseTraceAppearanceProps } from '@/components/VideoAnalyzer/mouseTrace';
import type TimelinePanel from '@/components/VideoAnalyzer/TimelinePanel.vue';
import $axios from '@/http';
import i18n from '@/i18n';
import { videoPlayerConfig } from '@/store';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';
import { mockVideoInfo } from '@cy/support/videoInfo';

type Layout = 'counter-left' | 'counter-right' | 'counter-top' | 'board-top';

function mountAnalyzer(width = 1100, fixture: { filename: string; durationMs: number; software?: string } = { filename: 'c_10_129.073_24_0.186_Pu Tian Yi(Hu Bei).evf', durationMs: 129073 }, info?: () => VNode[]) {
    cy.viewport(1280, 800);
    cy.mockPlayerNameFallback();
    const metadata = mockVideoInfo([{ id: 123, software: fixture.software ?? 'e', upload_time: '2026-10-12T10:00:00Z' }], 'getSoftware');
    cy.intercept('GET', '**/api/common/video/123/analyzer-info', { body: { video: metadata[0], tournament_ids: [], filename: fixture.filename, rankings: [] } }).as('getWebsiteInfo');
    cy.intercept('GET', '**/api/video/preview**', {
        headers: { 'content-type': 'application/octet-stream', 'x-replay-container-version': '0' },
        fixture: `${fixture.filename},null`,
    }).as('getReplay');
    cy.mount(defineComponent({
        expose: [],
        render: () => h('div', { class: 'analyzer-test-container', style: { width: `${width}px`, height: '600px' } }, [h(App, { id: '123' }, info === undefined ? undefined : { info })]),
    }), { global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } }, stubs: { transition: false } } }).then(({ wrapper }) => {
        cy.wrap(wrapper).as('analyzer');
    });
    cy.wait('@parsedVideoInfo').its('request.query.ids').should('eq', '123');
    cy.wait('@getReplay').its('request.query.id').should('eq', '123');
    cy.get('.analyzer-progress-bar__slider', { timeout: 10000 }).should('have.attr', 'max', String(fixture.durationMs)).and('not.be.disabled');
}

function selectLayout(layout: string) {
    cy.get('.video-analyzer-board__layout-control button').click();
    cy.get('.video-analyzer-view__layout-select:visible').select(layout);
}
function assertSelectedLayout(layout: string) {
    cy.get('.video-analyzer-board__layout-control button').should('have.attr', 'aria-expanded', 'false').click();
    cy.get('.video-analyzer-view__layout-select:visible').should('have.value', layout).trigger('keydown', { key: 'Escape' });
    cy.get('.video-analyzer-board__layout-control button').should('have.attr', 'aria-expanded', 'false');
    cy.shouldBeAbsentOrHidden('.video-analyzer-view__layout-select');
}
function assertOpenedCells(count: number) {
    cy.get<VueWrapper>('@analyzer').should((wrapper) => {
        const board = wrapper.findComponent<typeof MinesweeperBoard>('.video-analyzer-board__main').props('board');
        if (board === undefined) throw new Error('Expected a loaded board');
        expect(board.flat().filter((cell) => cell >= 0 && cell <= 8)).to.have.length(count);
    });
}

function canvasPixels(canvas: HTMLCanvasElement) {
    const context = canvas.getContext('2d');
    if (context === null) throw new Error('Expected a board canvas');
    return context.getImageData(0, 0, canvas.width, canvas.height).data;
}

function assertBackground(rows: number, columns: number) {
    cy.get('.minesweeper-board-content').should('have.length', 1);
    cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').should('have.length', 1).and('be.visible').and(($canvas) => {
        expect($canvas[0].width).to.be.greaterThan(0);
        expect($canvas[0].width / columns).to.be.closeTo($canvas[0].height / rows, 1);
        const opened = $canvas[0].closest('.video-analyzer-board__main')?.querySelector<HTMLCanvasElement>('canvas.video-analyzer-board__opened');
        expect($canvas[0].width).to.eq(opened?.width);
        expect($canvas[0].height).to.eq(opened?.height);
        expect(canvasPixels($canvas[0]).some((value) => value !== 0)).to.equal(true);
    });
}

function assertGlobalBoard(rows: number, columns: number, mines: number) {
    cy.get<VueWrapper>('@analyzer').should((wrapper) => {
        const board = wrapper.findComponent<typeof BoardForeground>('.video-analyzer-board__global').props('board');
        if (board === undefined) throw new Error('Expected a global board');
        expect(board).to.have.length(rows);
        for (const row of board) expect(row).to.have.length(columns);
        expect(board.flat().filter((cell) => cell === -1)).to.have.length(mines);
        expect(board.flat().every((cell) => cell >= -1 && cell <= 8)).to.equal(true);
    });
}

function assertLayout(layout: Layout) {
    cy.get('.video-analyzer-view__workspace').should(($workspace) => {
        for (const panel of ['info', 'board', 'counter', 'timeline']) expect($workspace.find(`.video-analyzer-${panel}`)).to.have.length(1);
        const info = $workspace.find('.video-analyzer-info')[0].getBoundingClientRect();
        const board = $workspace.find('.video-analyzer-board')[0].getBoundingClientRect();
        const counter = $workspace.find('.video-analyzer-counter')[0].getBoundingClientRect();
        const timeline = $workspace.find('.video-analyzer-timeline')[0].getBoundingClientRect();
        const workspace = $workspace[0].getBoundingClientRect();
        const infoOnTop = workspace.width < 720;
        const counterRegion = { left: counter.left, right: counter.right, top: infoOnTop ? counter.top : info.top, bottom: counter.bottom };

        for (const panel of [info, board, counter, timeline]) {
            expect(panel.width).to.be.greaterThan(0);
            expect(panel.height).to.be.greaterThan(0);
            expect(panel.left).to.be.at.least(workspace.left);
            expect(panel.right).to.be.at.most(workspace.right + 1);
            expect(panel.top).to.be.at.least(workspace.top);
            expect(panel.bottom).to.be.at.most(workspace.bottom + 1);
        }

        if (infoOnTop) {
            expect(info.top).to.be.closeTo(workspace.top + 1, 1);
            expect(info.bottom).to.be.closeTo(Math.min(board.top, counter.top), 1);
            expect(info.width).to.be.closeTo(timeline.width, 1);
        } else {
            expect(info.bottom).to.be.closeTo(counter.top, 1);
            expect(info.left).to.be.closeTo(counter.left, 1);
            expect(info.width).to.be.closeTo(counter.width, 1);
        }

        if (layout === 'counter-left' || layout === 'counter-right') {
            const [left, right] = layout === 'counter-left' ? [counterRegion, board] : [board, counterRegion];
            expect(left.right).to.be.closeTo(right.left, 1);
            expect(left.top).to.be.closeTo(right.top, 1);
            expect(left.bottom).to.be.closeTo(timeline.top, 1);
        } else {
            const [top, middle] = layout === 'board-top' ? [board, counterRegion] : [counterRegion, board];
            expect(top.bottom).to.be.closeTo(middle.top, 1);
            expect(middle.bottom).to.be.closeTo(timeline.top, 1);
            expect(top.left).to.be.closeTo(middle.left, 1);
        }
        expect(timeline.left).to.be.closeTo(workspace.left + 1, 1);
        expect(timeline.right).to.be.closeTo(workspace.right - 1, 1);
    });
}

function dragDivider(selector: string, index: number, dx: number, dy: number) {
    cy.get(selector).eq(index).should('be.visible').then(($handle) => {
        cy.window().then((win) => {
            const [handle] = $handle;
            const rect = handle.getBoundingClientRect();
            const clientX = rect.left + rect.width / 2;
            const clientY = rect.top + rect.height / 2;
            handle.dispatchEvent(new win.MouseEvent('mousedown', { bubbles: true, button: 0, buttons: 1, clientX, clientY }));
            win.dispatchEvent(new win.MouseEvent('mousemove', { buttons: 1, clientX: clientX + dx, clientY: clientY + dy }));
            win.dispatchEvent(new win.MouseEvent('mouseup', { button: 0, clientX: clientX + dx, clientY: clientY + dy }));
        });
    });
}

describe('<VideoAnalyzerView />', () => {
    installHashHistoryCleanup();

    it('sends counter keys to slots, shares prepared data, and preserves tracks and the time window across layouts', () => {
        mountAnalyzer();
        cy.get('.timeline-event-row__key').should(($keys) => {
            expect([...$keys].map((key) => key.textContent)).to.deep.eq(['left', 'right', 'pluck']);
        });
        cy.get('.video-analyzer-counter__label > span:last-child').should(($labels) => {
            expect([...$labels].map((label) => label.textContent?.trim())).to.deep.eq(['Bvs', 'Ces', 'Mov']);
        });
        cy.get('.timeline-slot').first().find('.timeline-slot__legend-button').should('have.text', 'BvsCes');
        cy.get('.timeline-slot').eq(1).find('.timeline-slot__legend-button').should('have.text', 'Mov');
        cy.get('.video-analyzer-counter__handle').first().click();
        cy.get('.video-analyzer-counter__send-to-slot:visible').select('0');
        cy.get('.timeline-slot').first().find('.timeline-slot__legend-button').should('have.text', 'BvsCesBvs');
        cy.get('.timeline-slot').first().find<SVGPathElement>('.timeline-plot__line path').should(($paths) => {
            expect($paths).to.have.length(3);
            expect($paths[0].getTotalLength()).to.be.greaterThan(0);
        });
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof CounterPanel>('.video-analyzer-counter').props('counters')).to.equal(wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('counters'));
        });
        cy.get('.video-analyzer-timeline__ruler').then(($ruler) => {
            const rect = $ruler[0].getBoundingClientRect();
            cy.wrap($ruler).trigger('wheel', { eventConstructor: 'WheelEvent', deltaY: -300, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 });
        });
        let timeWindow = { startMs: 0, endMs: 0 };
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('window')).to.have.property('endMs').that.is.lessThan(129073);
        }).then((wrapper) => {
            timeWindow = { ...wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('window') };
        });
        selectLayout('counter-top');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('window')).to.deep.eq(timeWindow);
            expect(wrapper.findComponent<typeof CounterPanel>('.video-analyzer-counter').props('counters')).to.equal(wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('counters'));
        });
        cy.get('.timeline-slot').first().find('.timeline-slot__legend-button').should('have.text', 'BvsCesBvs');
        cy.get('.timeline-slot').eq(1).find('.timeline-slot__legend-button').should('have.text', 'Mov');
        cy.window().should((win) => {
            const stored = JSON.parse(win.localStorage.getItem('video-analyzer-config') ?? '{}') as AnalyzerConfig;
            expect(stored.timeline.slots[0]).to.deep.eq([{ key: 'Bvs', color: '#4e79a7' }, { key: 'Ces', color: '#f28e2c' }, { key: 'Bvs', color: '#e15759' }]);
            expect(stored.timeline).not.to.have.property('window');
            expect(stored).not.to.have.property('preparedCounters');
        });
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('uses real native snapshots for custom events, persists definitions and preserves them across layouts', () => {
        analyzerConfig.value.customEvents = [{ ...defaultCustomEvent(), key: 'click', expression: 'd(left) > 0' }];
        mountAnalyzer();
        cy.get('.timeline-event-row__key').should('have.text', 'click');
        cy.get('.timeline-plot__event-pulses .plot-scatter__point').should(($points) => {
            expect($points.length).to.be.greaterThan(0);
        });
        let nativeEvents: CounterEvent[] = [];
        cy.get<VueWrapper>('@analyzer').then((wrapper) => {
            const events = wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('events');
            if (events === undefined) throw new Error('Expected loaded native event snapshots');
            nativeEvents = events;
        });
        selectLayout('counter-top');
        cy.get('.timeline-event-row__key').should('have.text', 'click');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof TimelinePanel>('.video-analyzer-timeline').props('events')).to.equal(nativeEvents);
        });
        cy.window().should((win) => {
            const saved = JSON.parse(win.localStorage.getItem('video-analyzer-config') ?? '{}') as AnalyzerConfig;
            expect(saved.customEvents).to.deep.eq(analyzerConfig.value.customEvents);
            expect(saved).not.to.have.property('preparedEvents');
        });
        cy.get('@getReplay.all').should('have.length', 1);
    });

    let originalProbabilityColorScheme = videoPlayerConfig.value.probabilityColorScheme;
    let originalAnalyzerConfig = analyzerConfig.value;
    beforeEach(() => {
        originalProbabilityColorScheme = videoPlayerConfig.value.probabilityColorScheme;
        originalAnalyzerConfig = JSON.parse(JSON.stringify(analyzerConfig.value)) as AnalyzerConfig;
        analyzerConfig.value = defaultAnalyzerConfig();
    });
    afterEach(() => {
        videoPlayerConfig.value.probabilityColorScheme = originalProbabilityColorScheme;
        analyzerConfig.value = originalAnalyzerConfig;
    });

    it('samples the real replay once, synchronizes counter time, and persists added rows across layouts', () => {
        analyzerConfig.value.counter.rows[0].expression = 'left';
        let events: CounterEvent[];
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get<VueWrapper>('@analyzer').then((wrapper) => {
            events = wrapper.findComponent<typeof CounterPanel>('.video-analyzer-counter').props('events');
        });
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const panel = wrapper.findComponent<typeof CounterPanel>('.video-analyzer-counter');
            const prepared = prepareCounter(analyzerConfig.value.counter.rows[0], events);
            expect(panel.props('currentMs')).to.eq(5000);
            expect(panel.find('.video-analyzer-counter__value').text()).to.eq(displayCounter(prepared, 5000).value);
        });
        cy.get('.video-analyzer-counter__handle').first().click();
        cy.get('.video-analyzer-counter__add-below:visible').click();
        cy.get('.counter-row-editor__key').type('analysis-path');
        cy.get('.counter-row-editor__expression').type('path');
        cy.get('.counter-row-editor__sampling').select('continuous');
        cy.get('.counter-row-editor__save').click();
        cy.get('.counter-row-editor').should('not.exist');
        cy.get('.video-analyzer-counter tr').should('have.length', 4);
        selectLayout('board-top');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const panel = wrapper.findComponent<typeof CounterPanel>('.video-analyzer-counter');
            expect(panel.props('events')).to.eq(events);
            expect(panel.props('modelValue')).to.deep.eq(analyzerConfig.value.counter);
            expect(panel.props('currentMs')).to.eq(5000);
        });
        cy.window().should((win) => {
            const saved = JSON.parse(win.localStorage.getItem('video-analyzer-config') ?? '{}') as AnalyzerConfig;
            expect(saved.counter.rows[0].expression).to.eq('left');
            expect(saved.counter.rows[1]).to.deep.eq({ key: 'analysis-path', expression: 'path', format: '.3f', samplingMode: 'continuous' });
        });
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('visits equal-timestamp keyframes with distinct prior boards and clears the override on a same-time seek', () => {
        mountAnalyzer(1100, { filename: 'Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', durationMs: 35090, software: 'a' });
        cy.get('.analyzer-progress-bar__slider').invoke('val', 2910).trigger('input');
        let normalBoard: number[][] | null | undefined;
        cy.get<VueWrapper>('@analyzer').then((wrapper) => {
            normalBoard = wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board').props('board');
        });
        cy.get('.analyzer-progress-bar__previous-keyframe').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const board = wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board');
            expect(board.props('currentEventIndex')).to.eq(532);
            const cells: number[][] | null | undefined = board.props('board');
            expect(cells?.flat().filter((cell) => cell <= 8)).to.have.length(42);
        });
        cy.get('.analyzer-progress-bar__time').should('contain.text', '2.910 /');
        cy.get('.analyzer-progress-bar__next-keyframe').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const board = wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board');
            expect(board.props('currentEventIndex')).to.eq(535);
            const cells: number[][] | null | undefined = board.props('board');
            expect(cells?.flat().filter((cell) => cell <= 8)).to.have.length(43);
        });
        cy.get('.analyzer-progress-bar__time').should('contain.text', '2.910 /');
        cy.get('.analyzer-progress-bar__previous-keyframe').click();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 2910).trigger('input');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const board = wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board');
            expect(board.props('currentEventIndex')).to.eq(535);
            expect(board.props('board')).to.deep.eq(normalBoard);
        });
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('reports missing adjacent keyframes, includes pre-zero events and preserves playback when stepping', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.analyzer-progress-bar__previous-keyframe').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const board = wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board');
            expect(board.props('currentEventIndex')).to.eq(0);
            const cells: number[][] | null | undefined = board.props('board');
            expect(cells?.flat().every((cell) => cell === 10)).to.eq(true);
        });
        cy.get('.analyzer-progress-bar__time').should('contain.text', '0.000 /');
        cy.get('.analyzer-progress-bar__previous-keyframe').click();
        cy.contains('.el-notification', 'No previous keyframe').should('be.visible');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardPanel>('.video-analyzer-board').props('currentEventIndex')).to.eq(0);
        });
        cy.closeElNotifications();
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.analyzer-progress-bar__next-keyframe').click();
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause').click();
        cy.get('.analyzer-progress-bar__end').click();
        cy.get('.analyzer-progress-bar__next-keyframe').click();
        cy.contains('.el-notification', 'No next keyframe').should('be.visible');
        cy.get('.analyzer-progress-bar__time').should('contain.text', '10.732 /');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.closeElNotifications();
    });

    it('defaults to counters on the left in a wide container', () => {
        mountAnalyzer();
        cy.get('.video-analyzer-board__content').should('have.attr', 'aria-busy', 'false');
        cy.get('.video-analyzer-board__opened').should('be.visible');
        cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__opened').should(($canvas) => {
            const [canvas] = $canvas;
            expect(canvas.width).to.be.greaterThan(0);
            expect(canvas.height).to.be.greaterThan(0);
            expect(canvasPixels(canvas).some((value) => value !== 0)).to.equal(true);
        });
        cy.get('.video-analyzer-view__toolbar').should('not.exist');
        cy.get('.video-analyzer-view h1').should('not.exist');
        cy.shouldBeAbsentOrHidden('.video-analyzer-view__layout-select');
        assertSelectedLayout('auto');
        cy.get('.video-analyzer-board__layout-control button').should('be.visible');
        cy.get('.website-replay-info__strange-dust').should('be.visible').and(($link) => {
            const replay = new URL(new URL($link.attr('href') ?? '').searchParams.get('replay') ?? '');
            expect(replay.searchParams.get('id')).to.eq('123');
        });
        cy.get('.video-analyzer-board__settings').should(($settings) => {
            const layout = $settings[0].querySelector('.video-analyzer-board__layout-control')?.getBoundingClientRect();
            const size = $settings[0].querySelector('.video-analyzer-board__size-controls')?.getBoundingClientRect();
            if (!layout || !size) throw new Error('Expected layout and size controls');
            expect(layout.bottom).to.be.at.most(size.top);
            expect(layout.right).to.be.closeTo(size.right, 1);
        });
        assertLayout('counter-left');
        cy.get('.el-splitter-bar__dragger').should('have.length', 2);
    });

    it('defaults to board on top in a narrow container, even on a wide viewport', () => {
        mountAnalyzer(360);
        assertLayout('board-top');
        cy.get('.el-splitter-bar__dragger-horizontal').should('not.exist');
        cy.get('.el-splitter-bar__dragger-vertical').should('have.length', 2);
    });

    it('automatically shares height with custom information and puts it first in narrow containers', () => {
        const lines = ref(1);
        mountAnalyzer(1100, undefined, () => [h('div', { class: 'custom-replay-info' }, Array.from({ length: lines.value }, (_, index) => h('div', { style: { height: '24px' } }, `Replay detail ${index}`)))]);
        cy.get('.video-analyzer-info').should('contain.text', 'Replay detail 0').and('not.contain.text', 'Website replay information');
        assertLayout('counter-left');
        cy.get('.video-analyzer-counter').then(($counter) => {
            const initialHeight = $counter[0].getBoundingClientRect().height;
            cy.then(() => {
                lines.value = 3;
            });
            cy.get('.video-analyzer-counter').should(($resized) => {
                expect($resized[0].getBoundingClientRect().height).to.be.closeTo(initialHeight - 48, 1);
            });
        });
        selectLayout('counter-right');
        assertLayout('counter-right');
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get('.analyzer-test-container').invoke('css', 'width', '360px');
        assertLayout('counter-right');
        selectLayout('auto');
        assertLayout('board-top');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.custom-replay-info').should('have.length', 1).and('contain.text', 'Replay detail 2');
        cy.get('@getSoftware.all').should('have.length', 0);
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('keeps the progress bar at the board bottom and preserves playback across layout changes', () => {
        mountAnalyzer();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 2000).trigger('input');
        cy.get('.analyzer-progress-bar__range-start').click();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 8000).trigger('input');
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.get('.analyzer-progress-bar__faster').click();
        cy.get('.analyzer-progress-bar__loop-all').click();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 10000).trigger('input');
        cy.get('.analyzer-progress-bar__play').click();

        for (const layout of ['counter-top', 'counter-right', 'board-top', 'counter-left'] as const) {
            selectLayout(layout);
            assertLayout(layout);
            cy.get('.video-analyzer-board').should(($board) => {
                const board = $board[0].getBoundingClientRect();
                const bar = $board.find('.analyzer-progress-bar')[0].getBoundingClientRect();
                expect(bar.bottom).to.be.closeTo(board.bottom, 1);
                expect(bar.left).to.be.closeTo(board.left, 1);
                expect(bar.right).to.be.closeTo(board.right, 1);
            });
            cy.get('.analyzer-progress-bar').should('have.length', 1);
            cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
            cy.get('.analyzer-progress-bar__normal').should('contain.text', '1.5x');
            cy.get('.analyzer-progress-bar__loop-all').should('have.attr', 'aria-pressed', 'true').and('be.disabled');
            cy.get('.analyzer-progress-bar__range-time').should('have.text', '[2.000, 8.000] s');
            cy.get('.analyzer-progress-bar__slider').should(($input) => {
                expect(Number($input.val())).to.be.greaterThan(10000);
            });
        }
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('@getSoftware.all').should('have.length', 0);
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('adapts auto layout to container width and preserves a manual choice', () => {
        mountAnalyzer();
        assertLayout('counter-left');
        cy.get('.analyzer-test-container').invoke('css', 'width', '360px');
        assertLayout('board-top');
        selectLayout('counter-top');
        cy.get('.analyzer-test-container').invoke('css', 'width', '1100px');
        assertLayout('counter-top');
        selectLayout('auto');
        assertLayout('counter-left');
    });

    it('resizes both boundaries in a side-by-side layout', () => {
        mountAnalyzer();
        assertLayout('counter-left');
        cy.get('.video-analyzer-counter').then(($counter) => {
            const initialWidth = $counter[0].getBoundingClientRect().width;
            dragDivider('.el-splitter-bar__dragger-horizontal', 0, 80, 0);
            cy.get('.video-analyzer-counter').should(($resized) => {
                expect($resized[0].getBoundingClientRect().width).to.be.closeTo(initialWidth + 80, 2);
            });
        });
        cy.get('.video-analyzer-timeline').then(($timeline) => {
            const initialHeight = $timeline[0].getBoundingClientRect().height;
            dragDivider('.el-splitter-bar__dragger-vertical', 0, 0, -60);
            cy.get('.video-analyzer-timeline').should(($resized) => {
                expect($resized[0].getBoundingClientRect().height).to.be.closeTo(initialHeight + 60, 2);
            });
        });
        assertLayout('counter-left');
        cy.window().should((win) => {
            const raw = win.localStorage.getItem('video-analyzer-config');
            if (raw === null) throw new Error('Expected persisted settings');
            const stored = JSON.parse(raw) as AnalyzerConfig;
            expect(stored.panelSizes['counter-left'].upper[0]).to.be.greaterThan(30);
            expect(stored.panelSizes['counter-left'].outer[1]).to.be.greaterThan(25);
        });
        selectLayout('board-top');
        selectLayout('counter-left');
        cy.get('.video-analyzer-counter').should(($counter) => {
            const counter = $counter[0].getBoundingClientRect();
            const board = $counter[0].closest('.video-analyzer-view__upper-splitter')?.querySelector('.video-analyzer-board')?.getBoundingClientRect();
            if (board === undefined) throw new Error('Expected board');
            expect(counter.width / (counter.width + board.width) * 100).to.be.closeTo(analyzerConfig.value.panelSizes['counter-left'].upper[0], 0.1);
        });
    });

    it('resizes both boundaries in a stacked layout and enforces minimum sizes', () => {
        mountAnalyzer(360);
        assertLayout('board-top');
        cy.get('.video-analyzer-board').then(($board) => {
            const initialHeight = $board[0].getBoundingClientRect().height;
            dragDivider('.el-splitter-bar__dragger-vertical', 0, 0, -40);
            cy.get('.video-analyzer-board').should(($resized) => {
                expect($resized[0].getBoundingClientRect().height).to.be.closeTo(initialHeight - 40, 2);
            });
        });
        cy.get('.video-analyzer-timeline').then(($timeline) => {
            const initialHeight = $timeline[0].getBoundingClientRect().height;
            dragDivider('.el-splitter-bar__dragger-vertical', 1, 0, -30);
            cy.get('.video-analyzer-timeline').should(($resized) => {
                expect($resized[0].getBoundingClientRect().height).to.be.closeTo(initialHeight + 30, 2);
            });
        });
        dragDivider('.el-splitter-bar__dragger-vertical', 0, 0, -1000);
        cy.get('.video-analyzer-view__splitter').should(($splitter) => {
            const boardHeight = $splitter.find('.video-analyzer-board')[0].getBoundingClientRect().height;
            expect(boardHeight).to.be.closeTo($splitter[0].getBoundingClientRect().height * 0.15, 2);
        });
        assertLayout('board-top');
    });

    it('reports backend errors and keeps playback disabled', () => {
        cy.intercept('GET', '**/api/common/video/999999/analyzer-info', { statusCode: 404, body: '' });
        cy.intercept('GET', '**/api/video/staticdetailbatch*', { statusCode: 404, body: '' }).as('getSoftware');
        cy.intercept('GET', '**/api/video/preview**', { body: '' }).as('getReplay');
        cy.mount(defineComponent({ expose: [], render: () => h(App, { id: '999999' }) }), { global: { plugins: [i18n, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait('@getSoftware');
        cy.get('.video-analyzer-board__error').should('contain.text', '404');
        selectLayout('board-top');
        assertSelectedLayout('board-top');
        cy.get('.analyzer-progress-bar__slider').should('be.disabled');
        cy.get('.analyzer-progress-bar__play').should('be.disabled');
        cy.get('@getReplay.all').should('have.length', 0);
    });

    it('renders shared-time game_board when seeking, rewinding and reaching the end', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.board-size-controls__fixed-toggle').click();
        assertOpenedCells(128);
        assertBackground(16, 16);
        cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').should(($canvas) => {
            expect($canvas[0].width).to.eq(512);
            expect($canvas[0].height).to.eq(512);
        });
        cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').its('0').invoke('toDataURL').as('initialBackground', { type: 'static' });
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        assertOpenedCells(180);
        cy.get<string>('@initialBackground').then((initial) => {
            cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').should(($canvas) => {
                expect($canvas[0].toDataURL() === initial, 'background changes after seeking').to.eq(false);
            });
        });
        cy.get('.analyzer-progress-bar__end').click();
        assertOpenedCells(216);
        cy.get('.analyzer-progress-bar__start').click();
        assertOpenedCells(128);
        cy.get<string>('@initialBackground').then((initial) => {
            cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').should(($canvas) => {
                expect($canvas[0].toDataURL() === initial, 'background returns to its initial pixels').to.eq(true);
            });
        });
    });

    it('updates the board while playing', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        assertOpenedCells(128);
        cy.get('.analyzer-progress-bar__play').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const board = wrapper.findComponent<typeof MinesweeperBoard>('.video-analyzer-board__main').props('board');
            if (board === undefined) throw new Error('Expected a loaded board');
            expect(board.flat().filter((cell) => cell >= 0 && cell <= 8).length).to.be.greaterThan(128);
        });
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('aligns probability above opened cells, updates it on seeks and preserves its toggle across layouts', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.video-analyzer-board__probability-toggle').should('be.visible').and('have.attr', 'aria-pressed', 'true');
        cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__probability').should('be.visible').and(($canvas) => {
            const [canvas] = $canvas;
            expect(canvasPixels(canvas).some((value) => value !== 0)).to.equal(true);
            const opened = canvas.parentElement?.querySelector<HTMLCanvasElement>('canvas.video-analyzer-board__opened');
            if (opened === null || opened === undefined) throw new Error('Expected an opened layer');
            expect(canvas.width).to.eq(opened.width);
            expect(canvas.height).to.eq(opened.height);
            expect(Number(getComputedStyle(canvas).zIndex)).to.be.greaterThan(Number(getComputedStyle(opened).zIndex));
            for (const key of ['left', 'top', 'width', 'height'] as const) expect(canvas.getBoundingClientRect()[key]).to.be.closeTo(opened.getBoundingClientRect()[key], 1);
        });
        cy.get<VueWrapper>('@analyzer').then((wrapper) => {
            cy.wrap(wrapper.findComponent<typeof BoardProbability>('.video-analyzer-board__probability').props('board')).as('initialProbability');
        });
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        assertOpenedCells(180);
        cy.get<number[][]>('@initialProbability').then((initial) => {
            cy.get<VueWrapper>('@analyzer').should((wrapper) => {
                expect(wrapper.findComponent<typeof BoardProbability>('.video-analyzer-board__probability').props('board')).not.to.deep.equal(initial);
            });
        });
        cy.get('.video-analyzer-board__probability-toggle').click();
        cy.get('.video-analyzer-board__probability').should('not.be.visible');
        cy.get('.video-analyzer-board__opened').should('be.visible');
        selectLayout('board-top');
        cy.get('.video-analyzer-board__probability-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.get('.video-analyzer-board__probability-toggle').click();
        cy.get('.video-analyzer-board__probability').should('be.visible');
        cy.get('.video-analyzer-board__opened').should('be.visible');
        cy.get('.analyzer-progress-bar__start').click();
        cy.get<number[][]>('@initialProbability').then((initial) => {
            cy.get<VueWrapper>('@analyzer').should((wrapper) => {
                expect(wrapper.findComponent<typeof BoardProbability>('.video-analyzer-board__probability').props('board')).to.deep.equal(initial);
            });
        });
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('opens layer settings separately from toggles and edits the shared probability palette', () => {
        mountAnalyzer();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        for (const [layer, visible] of [['global', false], ['probability', true]] as const) {
            cy.get(`.video-analyzer-board__${layer}-control .board-settings-control__handle`).click();
            cy.get('.board-settings-control__settings:visible').should('have.length', 1);
            cy.get('.board-settings-control__settings:visible .board-layer-control__visible').should(visible ? 'be.checked' : 'not.be.checked');
            cy.get(`.video-analyzer-board__${layer}-toggle`).should('have.attr', 'aria-pressed', String(visible));
            cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        }
        cy.get('.board-settings-control__settings:visible .color-scheme-setting__import-toggle').click();
        cy.get('.board-settings-control__settings:visible .color-scheme-setting__json').invoke('val', JSON.stringify({ colors: ['#123456', '#abcdef'], thresholds: [50] })).trigger('input');
        cy.get('.board-settings-control__settings:visible .color-scheme-setting__apply').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(videoPlayerConfig.value.probabilityColorScheme).to.deep.eq({ colors: ['#123456', '#abcdef'], thresholds: [50] });
            const color = wrapper.findComponent<typeof BoardProbability>('.video-analyzer-board__probability').props('color');
            if (color === undefined) throw new Error('Expected a probability color mapper');
            expect(color(0.25, 0, 0)).to.eq('#123456');
            expect(color(0.75, 0, 0)).to.eq('#abcdef');
        });
        cy.get('.board-settings-control__settings:visible .board-layer-control__visible').uncheck();
        cy.get('.video-analyzer-board__probability-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.video-analyzer-board__probability').should('not.be.visible');
        cy.get('.video-analyzer-board__opened').should('be.visible');
        cy.get('.board-settings-control__settings:visible').should('be.visible');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('adjusts layer opacity independently and preserves both values across layouts and toggles', () => {
        mountAnalyzer();
        cy.get('.video-analyzer-board__layers .board-layer-control').should('have.length', 3);
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        for (const [layer, opacity] of [['global', 0.25], ['probability', 0.65]] as const) {
            cy.get(`.video-analyzer-board__${layer}`).should('have.css', 'opacity', '1');
            cy.get(`.video-analyzer-board__${layer}-control .board-settings-control__handle`).click();
            cy.get('.board-settings-control__settings:visible .board-layer-control__opacity').invoke('val', opacity).trigger('input');
            cy.get(`.video-analyzer-board__${layer}`).should('have.css', 'opacity', String(opacity));
            cy.get('.video-analyzer-board__opened').should('be.visible').and('have.css', 'opacity', '1');
            cy.get('.video-analyzer-board__background').should('have.css', 'opacity', '1');
        }
        cy.get('.video-analyzer-board__global-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.video-analyzer-board__probability-toggle').should('have.attr', 'aria-pressed', 'true');
        cy.get('.video-analyzer-board__probability-control .board-settings-control__handle').click();
        selectLayout('board-top');
        cy.get('.video-analyzer-board__layers .board-layer-control').should('have.length', 3);
        for (const [layer, opacity] of [['global', 0.25], ['probability', 0.65]] as const) {
            cy.get(`.video-analyzer-board__${layer}`).should('have.css', 'opacity', String(opacity));
            cy.get(`.video-analyzer-board__${layer}-control .board-settings-control__handle`).click();
            cy.get('.board-settings-control__settings:visible .board-layer-control__opacity').should('have.value', String(opacity));
            cy.get(`.video-analyzer-board__${layer}-toggle`).click();
            cy.get(`.video-analyzer-board__${layer}-toggle`).click();
            cy.get(`.video-analyzer-board__${layer}`).should('have.css', 'opacity', String(opacity));
        }
        cy.get('.video-analyzer-board__global').should('have.css', 'opacity', '0.25');
        cy.get('.video-analyzer-board__opened').should('be.visible').and('have.css', 'opacity', '1');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('renders the mouse trace above probability and keeps its settings across layouts', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.video-analyzer-board__trace-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.video-analyzer-board__trace').should('not.exist');
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get('.video-analyzer-board__trace-toggle').click();
        cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__trace').should('be.visible').and(($canvas) => {
            const [canvas] = $canvas;
            const probability = canvas.parentElement?.querySelector<HTMLCanvasElement>('canvas.video-analyzer-board__probability');
            if (probability === null || probability === undefined) throw new Error('Expected probability layer');
            expect(canvas.width).to.eq(probability.width);
            expect(canvas.height).to.eq(probability.height);
            expect(Number(getComputedStyle(canvas).zIndex)).to.be.greaterThan(Number(getComputedStyle(probability).zIndex));
            const pixels = canvasPixels(canvas);
            expect(pixels.some((value, index) => index % 4 !== 3 && value !== 0)).to.equal(true);
        });
        cy.get('.video-analyzer-board__trace-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__trace-tail').should('have.value', '0.5').and('have.attr', 'step', 'any');
        cy.get('.video-analyzer-board__trace-mask').should('have.value', '0.5');
        cy.get('.board-settings-control__settings:visible .board-layer-control__opacity').invoke('val', 0.6).trigger('input');
        cy.get('.video-analyzer-board__trace-mask').invoke('val', 0.25).trigger('input');
        cy.get('.video-analyzer-board__trace-tail').invoke('val', 1).trigger('input');
        cy.get('.mouse-trace-settings__line-width').clear();
        cy.get('.mouse-trace-settings__line-width').type('0.2');
        cy.get('.mouse-trace-settings__line-width').blur();
        cy.get('.mouse-trace-settings__marker--lc summary').click();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__enabled').should('not.be.checked').check();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__shape').select('square');
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__size').clear();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__size').type('0.8');
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__size').blur();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__enabled').uncheck();
        cy.get('.video-analyzer-board__trace-setting output').first().should('have.text', 'Infinite');
        cy.window().should((win) => {
            const raw = win.localStorage.getItem('video-analyzer-config');
            if (raw === null) throw new Error('Expected persisted settings');
            const stored = JSON.parse(raw) as AnalyzerConfig;
            expect(stored.traceTailSeconds).to.eq('infinite');
            expect(stored.traceOpacity).to.eq(0.6);
            expect(stored.traceMaskOpacity).to.eq(0.25);
            expect(stored.traceVisible).to.eq(true);
            expect(stored.traceAppearance.lineWidth).to.eq(0.2);
            expect(stored.traceAppearance.markers.lc).to.include({ shape: 'square', size: 0.8, enabled: false });
        });
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            const trace = wrapper.findComponent<typeof MouseTrace>('.video-analyzer-board__trace');
            expect(trace.props('startIndex')).to.eq(0);
            expect(trace.props('opacity')).to.eq(0.25);
            expect(trace.props('markers')).to.deep.eq(mouseTraceAppearanceProps(analyzerConfig.value.traceAppearance).markers);
            expect(trace.props('lineWidth')).to.eq(0.2);
        });
        cy.get('.video-analyzer-board__trace-control .board-settings-control__handle').click();
        selectLayout('board-top');
        cy.get('.video-analyzer-board__trace').should('be.visible').and('have.css', 'opacity', '0.6');
        cy.get('.video-analyzer-board__trace-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__trace-tail').should('have.value', '1');
        cy.get('.video-analyzer-board__trace-mask').should('have.value', '0.25');
        cy.get('.mouse-trace-settings__line-width').should('have.value', '0.2');
        cy.get('.mouse-trace-settings__marker--lc summary').click();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__enabled').check();
        cy.get('.mouse-trace-settings__marker--lc .mouse-trace-settings__size').should('have.value', '0.8');
        cy.get('.video-analyzer-board__trace-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__trace-toggle').click();
        cy.get('.video-analyzer-board__trace').should('not.exist');
        cy.get('.video-analyzer-board__trace-toggle').click();
        cy.get('.video-analyzer-board__trace').should('have.css', 'opacity', '0.6');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('selects board events, persists layer settings, and follows timeline rename, style and deletion', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.video-analyzer-board__event-toggle').should('have.attr', 'aria-pressed', 'true');
        cy.get('.board-event-layer__event').should('have.attr', 'data-event-key', 'pluck');
        cy.get('.board-event-layer__pulse').should('exist');
        cy.get('.video-analyzer-board__event-toggle').click();
        cy.get('.board-event-layer').should('not.exist');
        cy.get('.video-analyzer-board__event-toggle').click();
        cy.get('.board-event-layer__event').should('have.attr', 'data-event-key', 'pluck');
        cy.get('.video-analyzer-board__event-control .board-settings-control__handle').click();
        cy.get('.board-event-settings__key[value="pluck"]').uncheck();
        cy.get('.board-event-settings__key[value="left"]').check();
        cy.get('.board-event-settings__range').should('have.value', 'all');
        cy.get('.board-event-settings__spacing').clear();
        cy.get('.board-event-settings__spacing').type('48');
        cy.get('.board-event-settings__shape').select('open');
        cy.get('.video-analyzer-board__event-control .board-settings-control__handle').click();
        cy.get('.board-event-layer__path').should('exist');
        cy.get('.board-event-layer__arrow').should('exist');
        cy.get('.video-analyzer-board__stack').should(($stack) => {
            const [events] = $stack.find('.board-event-layer');
            const [cursor] = $stack.find('.board-cursor-layer');
            const [probability] = $stack.find('.video-analyzer-board__probability');
            expect(Number(getComputedStyle(events).zIndex)).to.be.lessThan(Number(getComputedStyle(cursor).zIndex));
            expect(Number(getComputedStyle(events).zIndex)).to.be.greaterThan(Number(getComputedStyle(probability).zIndex));
        });
        cy.window().should((win) => {
            const saved = JSON.parse(win.localStorage.getItem('video-analyzer-config') ?? '{}') as AnalyzerConfig;
            expect(saved.eventLayer).to.deep.eq({ visible: true, keys: ['left'], timeRange: 'all', arrowSpacing: 48, arrowSize: 8, arrowShape: 'open' });
        });
        cy.get('.timeline-event-row__settings').first().click();
        cy.get('.custom-event-editor__key').clear();
        cy.get('.custom-event-editor__key').type('held');
        cy.get('.custom-event-editor__line-style').select('dot');
        cy.get('.custom-event-editor__save').click();
        cy.get('.board-event-layer__path').should('have.attr', 'stroke-dasharray', '1 3').and(() => {
            expect(analyzerConfig.value.eventLayer.keys).to.deep.eq(['held']);
        });
        cy.get('.timeline-event-row__settings').first().click();
        cy.get('.custom-event-editor__delete').click();
        cy.get('.board-event-layer__event').should('not.exist').and(() => {
            expect(analyzerConfig.value.eventLayer.keys).to.deep.eq([]);
        });
    });

    it('synchronizes the top cursor on seeks and edits its shape and absolute SVG boundary', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.video-analyzer-board__cursor-toggle').should('have.attr', 'aria-pressed', 'true');
        cy.get('.board-cursor-layer__dot').should('be.visible');
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardCursorLayer>('.video-analyzer-board__cursor').props('position')).to.deep.eq({ columnIndex: 7 / 26, rowIndex: 296 / 26 });
        });
        cy.get('.analyzer-progress-bar__end').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardCursorLayer>('.video-analyzer-board__cursor').props('position')).to.deep.eq({ columnIndex: 248 / 26, rowIndex: 67 / 26 });
        });
        cy.get('.analyzer-progress-bar__start').click();
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof BoardCursorLayer>('.video-analyzer-board__cursor').props('position')).to.deep.eq({ columnIndex: 166 / 26, rowIndex: 35 / 26 });
        });
        cy.get('.video-analyzer-board__cursor-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__cursor-shape').should('have.length', 4);
        cy.get('.video-analyzer-board__cursor-shape--dot').should('have.attr', 'aria-pressed', 'true');
        cy.get('.video-analyzer-board__cursor-shape--windows').click();
        cy.get('.video-analyzer-board__cursor-shape--windows').should('have.attr', 'aria-pressed', 'true');
        cy.get('.video-analyzer-board__cursor-shape--dot').should('have.attr', 'aria-pressed', 'false');
        cy.get('.video-analyzer-board__cursor-shapes [aria-pressed="true"]').should('have.length', 1);
        cy.get('.video-analyzer-board__cursor-size').should('have.attr', 'min', '4').and('have.attr', 'max', '40').and('have.attr', 'step', '1');
        for (const size of [4, 40]) {
            cy.get('.video-analyzer-board__cursor-size').invoke('val', size).trigger('input');
            cy.get('.video-analyzer-board__cursor-size-setting output').should('have.text', `${size}px`);
            cy.get<SVGSVGElement>('.board-cursor-layer__svg').should(($svg) => {
                expect($svg[0].getBoundingClientRect().width).to.eq(size);
                expect($svg[0].getBoundingClientRect().height).to.eq(size);
            });
        }
        cy.get('.board-cursor-layer__windows').should('be.visible');
        cy.get('.video-analyzer-board__cursor-visible').uncheck();
        cy.get('.board-cursor-layer').should('not.exist');
        cy.get('.video-analyzer-board__opened').should('be.visible');
        cy.get('.video-analyzer-board__probability').should('be.visible');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '0');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.get('@getReplay.all').should('have.length', 1);
    });

    it('restores settings on reopen without retaining replay position or range endpoints', () => {
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        cy.get('.board-size-controls__fixed-toggle').click();
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.contains('.board-size-controls__fixed-preset', '48px').click();
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.get('.board-size-controls__relative .board-settings-control__handle').click();
        cy.contains('.board-size-controls__relative-preset', '150%').click();
        cy.get('.board-size-controls__relative .board-settings-control__handle').click();
        selectLayout('counter-right');
        cy.get('.video-analyzer-board__cursor-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__cursor-shape--windows').click();
        cy.get('.video-analyzer-board__cursor-size').invoke('val', 24).trigger('input');
        cy.get('.video-analyzer-board__cursor-visible').uncheck();
        cy.get('.video-analyzer-board__cursor-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__global-toggle').click();
        cy.get('.video-analyzer-board__probability-toggle').click();
        cy.get('.analyzer-progress-bar__faster').click();
        cy.get('.analyzer-progress-bar__loop-range').click();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 2000).trigger('input');
        cy.get('.analyzer-progress-bar__range-start').click();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 8000).trigger('input');
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.window().should((win) => {
            const raw = win.localStorage.getItem('video-analyzer-config');
            if (raw === null) throw new Error('Expected persisted settings');
            const stored = JSON.parse(raw) as AnalyzerConfig;
            expect(stored.selectedLayout).to.eq('counter-right');
            expect(stored.globalVisible).to.eq(true);
            expect(stored.probabilityVisible).to.eq(false);
            expect(stored.playbackRate).to.eq(1.5);
            expect(stored.loopMode).to.eq('range');
            expect(stored.cellSizeMode).to.eq('fixed');
            expect(stored.fixedCellSize).to.eq(48);
            expect(stored.cellScale).to.eq(1.5);
            expect(stored.cursorVisible).to.eq(false);
            expect(stored.cursorShape).to.eq('windows');
            expect(stored.cursorSize).to.eq(24);
            for (const field of ['currentMs', 'durationMs', 'isPlaying', 'rangeStartMs', 'rangeEndMs', 'video']) expect(stored).not.to.have.property(field);
        });
        cy.get<VueWrapper>('@analyzer').then((wrapper) => {
            wrapper.unmount();
        });
        mountAnalyzer(1100, { filename: '52200.evf', durationMs: 10732 });
        assertSelectedLayout('counter-right');
        assertLayout('counter-right');
        cy.get('.video-analyzer-board__cursor-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.board-cursor-layer').should('not.exist');
        cy.get('.video-analyzer-board__cursor-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__cursor-shape--windows').should('have.attr', 'aria-pressed', 'true');
        cy.get('.video-analyzer-board__cursor-size').should('have.value', '24');
        cy.get('.video-analyzer-board__cursor-control .board-settings-control__handle').click();
        cy.get('.board-size-controls__fixed-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('48px');
        }).and('have.attr', 'aria-pressed', 'true');
        cy.get('.board-size-controls__relative-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('150%');
        });
        cy.get<VueWrapper>('@analyzer').should((wrapper) => {
            expect(wrapper.findComponent<typeof MinesweeperBoard>('.video-analyzer-board__main').props('size')).to.eq(48);
        });
        cy.get('.video-analyzer-board__global-toggle').should('have.attr', 'aria-pressed', 'true');
        cy.get('.video-analyzer-board__probability-toggle').should('have.attr', 'aria-pressed', 'false');
        cy.get('.analyzer-progress-bar__normal').should('contain.text', '1.5x');
        cy.get('.analyzer-progress-bar__loop-range').should('have.attr', 'aria-pressed', 'true');
        cy.get('.analyzer-progress-bar__range-time').should('have.text', '[0.000, 10.732] s');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '0');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    for (const fixture of [
        { filename: '52200.evf', durationMs: 10732, rows: 16, columns: 16 },
        { filename: 'c_10_39.832_24_0.477_Pu Tian Yi(Hu Bei)_fail.evf', durationMs: 39832, rows: 8, columns: 8 },
    ]) {
        it(`renders the full global board independently of playback for ${fixture.filename}`, () => {
            mountAnalyzer(1100, fixture);
            cy.get('.video-analyzer-board__probability-toggle').click();
            cy.get('.video-analyzer-board__global-toggle').should('have.attr', 'aria-pressed', 'false');
            cy.get('.video-analyzer-board__global').should('not.be.visible');
            assertGlobalBoard(fixture.rows, fixture.columns, 40);
            cy.get<VueWrapper>('@analyzer').then((wrapper) => {
                cy.wrap(wrapper.findComponent<typeof BoardForeground>('.video-analyzer-board__global').props('board')).as('globalBoard');
            });
            cy.get('.video-analyzer-board__global-toggle').click();
            cy.get('.video-analyzer-board__stack').should(($stack) => {
                const [opened] = $stack.find('.video-analyzer-board__opened');
                const [global] = $stack.find('.video-analyzer-board__global');
                expect(Number(getComputedStyle(opened).zIndex)).to.be.greaterThan(Number(getComputedStyle(global).zIndex) || 0);
                const openedRect = opened.getBoundingClientRect();
                const globalRect = global.getBoundingClientRect();
                for (const key of ['left', 'top', 'width', 'height'] as const) expect(globalRect[key]).to.be.closeTo(openedRect[key], 1);
            });
            cy.get('.video-analyzer-board__opened').should('be.visible');
            cy.get('.video-analyzer-board__global').should('be.visible');
            cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__global').should(($canvas) => {
                const [canvas] = $canvas;
                const opened = canvas.parentElement?.querySelector<HTMLCanvasElement>('canvas.video-analyzer-board__opened');
                expect(canvas.width).to.eq(opened?.width);
                expect(canvas.height).to.eq(opened?.height);
                expect(canvasPixels(canvas).some((value) => value !== 0)).to.equal(true);
            });
            cy.get('.analyzer-progress-bar__end').click();
            cy.get<number[][]>('@globalBoard').then((initial) => {
                cy.get<VueWrapper>('@analyzer').should((wrapper) => {
                    expect(wrapper.findComponent<typeof BoardForeground>('.video-analyzer-board__global').props('board')).to.deep.equal(initial);
                });
            });
            cy.get('.analyzer-progress-bar__start').click();
            selectLayout('board-top');
            cy.get('.video-analyzer-board__global-toggle').should('have.attr', 'aria-pressed', 'true');
            cy.get('.video-analyzer-board__global').should('be.visible');
            cy.get('.video-analyzer-board__global-toggle').click();
            cy.get('.video-analyzer-board__global').should('not.be.visible');
            assertBackground(fixture.rows, fixture.columns);
            cy.get('.video-analyzer-board__stack').should(($stack) => {
                const opened = $stack.find('.video-analyzer-board__opened')[0].getBoundingClientRect();
                expect($stack[0].getBoundingClientRect().width).to.eq(opened.width);
                expect($stack[0].getBoundingClientRect().height).to.eq(opened.height);
            });
            cy.get('.video-analyzer-board__opened').should('be.visible');
            cy.get('.analyzer-progress-bar__slider').should('have.value', '0');
            cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
            cy.get('@getReplay.all').should('have.length', 1);
        });
    }
});
