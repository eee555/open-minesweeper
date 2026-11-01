import type { BoardBackground, MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import type { VueWrapper } from '@vue/test-utils';
import { computed, defineComponent, h, ref, shallowRef } from 'vue';

import BoardPanel from './BoardPanel.vue';
import { defaultAnalyzerConfig } from './config';
import type { AnalyzerConfig } from './config';
import { usePlayback } from './usePlayback';
import { provideAnalyzerState } from './useAnalyzerState';

import i18n from '@/i18n';
import { videoPlayerConfig } from '@/store';
import { createAnalyzerTestState } from '@cy/support/analyzerState';

function mountBoard() {
    const nativeSize = ref(16);
    const height = ref(360);
    const cursorPosition = ref<{ rowIndex: number; columnIndex: number } | null>({ rowIndex: 1.5, columnIndex: 2.5 });
    const config = ref(defaultAnalyzerConfig());
    config.value.globalVisible = true;
    config.value.traceVisible = true;
    cy.viewport(1000, 600);
    cy.mount(defineComponent({
        expose: [],
        setup() {
            const playback = usePlayback(10000);
            provideAnalyzerState(createAnalyzerTestState({
                config,
                playback,
                probabilityColorScheme: ref(videoPlayerConfig.value.probabilityColorScheme),
                frame: computed(() => ({
                    board: [[10, 0, 1, 10], [10, 1, 2, 10], [10, 10, 10, 10]],
                    globalBoard: [[0, 0, 1, -1], [1, 1, 2, 1], [-1, 1, 0, 0]],
                    probabilityBoard: [[0.5, 0, 0, 0.5], [0.5, 0, 0, 0.5], [0.5, 0.5, 0.5, 0.5]],
                    nativeCellSize: nativeSize.value,
                    cursorPosition: cursorPosition.value,
                    mouseState: 0,
                    currentEventIndex: null,
                })),
                traceEvents: shallowRef([
                    { row: 0.5, column: 0.5, timeMs: 0, eventIndex: 0, state: 'uu', action: 'mv' },
                    { row: 1.5, column: 2.5, timeMs: 100, eventIndex: 1, state: 'uu', action: 'mv' },
                ]),
            }));
            return () => h('div', { class: 'board-test-container', style: { width: '650px', height: `${height.value}px` } }, [
                h(BoardPanel),
            ]);
        },
    }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
        cy.wrap(wrapper).as('board');
    });
    cy.wrap(nativeSize).as('nativeSize');
    cy.wrap(height).as('height');
    cy.wrap(cursorPosition).as('cursorPosition');
    cy.wrap(config).as('config');
}

function editNumber(selector: string, value: string) {
    cy.get(selector).clear();
    if (value !== '') cy.get(selector).type(value);
    cy.get(selector).blur();
}

function assertSize(size: number | 'auto') {
    cy.get<VueWrapper>('@board').should((wrapper) => {
        expect(wrapper.findComponent<typeof MinesweeperBoard>('.video-analyzer-board__main').props('size')).to.eq(size);
    });
}

function assertLayers(width?: number, height?: number) {
    cy.get('.video-analyzer-board__stack').should(($stack) => {
        const canvases = $stack[0].querySelectorAll<HTMLCanvasElement>('canvas');
        expect(canvases).to.have.length(4);
        const opened = $stack[0].querySelector<HTMLCanvasElement>('canvas.video-analyzer-board__opened');
        if (opened === null) throw new Error('Expected an opened layer');
        expect(opened.width).to.be.greaterThan(0);
        if (width !== undefined) expect(opened.width).to.eq(width);
        if (height !== undefined) expect(opened.height).to.eq(height);
        for (const canvas of canvases) {
            expect(canvas.width).to.eq(opened.width);
            expect(canvas.height).to.eq(opened.height);
            for (const key of ['left', 'top', 'width', 'height'] as const) expect(canvas.getBoundingClientRect()[key]).to.be.closeTo(opened.getBoundingClientRect()[key], 1);
        }
    });
}

describe('<BoardPanel /> cell sizing', () => {
    it('edits config in place and follows replacement settings', () => {
        mountBoard();
        let original: AnalyzerConfig;
        cy.get<{ value: AnalyzerConfig }>('@config').then((config) => {
            original = config.value;
        });
        cy.get('.board-size-controls__fixed-toggle').click();
        cy.get<{ value: AnalyzerConfig }>('@config').should((config) => {
            expect(config.value).to.eq(original);
            expect(config.value.cellSizeMode).to.eq('fixed');
        });
        cy.get<{ value: AnalyzerConfig }>('@config').then((config) => {
            config.value = { ...config.value, fixedCellSize: 40, traceTailSeconds: 'infinite', cursorVisible: false };
        });
        assertSize(40);
        cy.get('.board-cursor-layer').should('not.exist');
        cy.get('.video-analyzer-board__trace-control .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__trace-tail').should('have.value', '1');
        cy.get('.video-analyzer-board__trace-tail').invoke('val', 0.5).trigger('input');
        cy.get<{ value: AnalyzerConfig }>('@config').should((config) => {
            expect(config.value.traceTailSeconds).to.eq(1);
        });
    });

    it('shows press feedback independently of cursor visibility and clears it on release', () => {
        const board = [[10, 10, 10], [10, 11, 10], [10, 10, 10]];
        const mouseState = ref(4);
        const config = ref(defaultAnalyzerConfig());
        config.value.cursorVisible = false;
        cy.mount(defineComponent({
            setup() {
                const playback = usePlayback(10000);
                provideAnalyzerState(createAnalyzerTestState({
                    config,
                    frame: computed(() => ({ board, globalBoard: null, probabilityBoard: null, mouseState: mouseState.value, cursorPosition: { rowIndex: 1.5, columnIndex: 2.5 }, currentEventIndex: null, nativeCellSize: 16 })),
                    playback,
                }));
                return () => h('div', { style: { width: '650px', height: '360px' } }, [h(BoardPanel)]);
            },
        }), { global: { plugins: [i18n] } }).then(({ wrapper }) => {
            cy.wrap(wrapper).as('board');
        });
        for (const [state, expected] of [
            [4, [[false, false, false], [false, false, true], [false, false, false]]],
            [5, [[false, true, true], [false, false, true], [false, true, true]]],
            [6, [[false, true, true], [false, false, true], [false, true, true]]],
            [1, undefined],
        ] as const) {
            cy.then(() => {
                mouseState.value = state;
            });
            cy.get<VueWrapper>('@board').should((wrapper) => {
                expect(wrapper.findComponent<typeof BoardBackground>('.video-analyzer-board__background').props('board')).to.deep.eq(expected);
            });
        }
        cy.get('.board-cursor-layer').should('not.exist');
    });

    it('keeps the cursor above all other layers, in place and at the same SVG size across sizing modes', () => {
        mountBoard();
        cy.get('.video-analyzer-board__cursor-toggle').should('have.attr', 'aria-pressed', 'true');
        for (const mode of ['fixed', 'relative', 'auto']) {
            cy.get(`.board-size-controls__${mode}-toggle`).click();
            cy.get<SVGSVGElement>('.board-cursor-layer__svg').should(($svg) => {
                expect($svg[0].getBoundingClientRect().width).to.eq(32);
                expect($svg[0].getBoundingClientRect().height).to.eq(32);
                const root = $svg[0].parentElement;
                const stack = root?.parentElement;
                const board = stack?.getBoundingClientRect();
                if (root === null || root === undefined || stack === null || stack === undefined || board === undefined) throw new Error('Expected cursor layer');
                const cursor = root.getBoundingClientRect();
                expect(cursor.left - board.left).to.be.closeTo(2.5 * board.width / 4, 1);
                expect(cursor.top - board.top).to.be.closeTo(1.5 * board.height / 3, 1);
                for (const layer of stack.querySelectorAll('canvas')) expect(Number(getComputedStyle(root).zIndex)).to.be.greaterThan(Number(getComputedStyle(layer).zIndex) || 0);
            });
        }
        cy.get<{ value: { rowIndex: number; columnIndex: number } | null }>('@cursorPosition').then((position) => {
            position.value = null;
        });
        cy.get('.board-cursor-layer').should('not.be.visible');
    });

    it('uses adaptive sizing by default, fits resized panels and keeps controls outside board scrolling', () => {
        mountBoard();
        assertSize('auto');
        cy.get('.board-size-controls__auto-toggle').should('have.attr', 'aria-pressed', 'true');
        cy.get('.board-size-controls__fixed-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('32px');
        });
        cy.get('.board-size-controls__relative-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('100%');
        });
        assertLayers();
        cy.get('.video-analyzer-board__main').should(($board) => {
            const board = $board[0].getBoundingClientRect();
            const viewport = $board[0].parentElement?.getBoundingClientRect();
            expect(board.width).to.be.closeTo(Math.min((viewport?.width ?? 0) / 4, (viewport?.height ?? 0) / 3) * 4, 1);
        });
        cy.get<{ value: number }>('@height').then((height) => {
            height.value = 280;
        });
        cy.get('.video-analyzer-board__main').should(($board) => {
            const viewport = $board[0].parentElement?.getBoundingClientRect();
            expect($board[0].getBoundingClientRect().height).to.be.closeTo(viewport?.height ?? 0, 1);
        });
        assertLayers();
        cy.get('.board-size-controls__fixed-toggle').click();
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        editNumber('.board-size-controls__fixed-input', '200');
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.get('.video-analyzer-board__viewport').scrollTo('bottomRight');
        cy.get('.video-analyzer-board__size-controls').should('be.visible').and(($controls) => {
            const controls = $controls[0].getBoundingClientRect();
            const content = $controls[0].closest('.video-analyzer-board__content')?.getBoundingClientRect();
            expect(controls.bottom).to.be.at.most(content?.bottom ?? 0);
            expect($controls[0].closest('.video-analyzer-board__viewport')).to.eq(null);
        });
    });

    it('edits presets and custom values, retains both settings and scales against the replay native size', () => {
        mountBoard();
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.contains('.board-size-controls__fixed-preset', '48px').click();
        assertSize('auto');
        editNumber('.board-size-controls__fixed-input', '40');
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.get('.board-size-controls__fixed-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('40px');
        }).click();
        assertSize(40);
        assertLayers(160, 120);
        cy.get('.board-size-controls__relative .board-settings-control__handle').click();
        cy.contains('.board-size-controls__relative-preset', '150%').click();
        editNumber('.board-size-controls__relative-input', '125');
        cy.get('.board-size-controls__relative .board-settings-control__handle').click();
        cy.get('.board-size-controls__relative-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('125%');
        }).click();
        cy.get('.board-size-controls__fixed-toggle').should('have.attr', 'aria-pressed', 'false');
        assertSize(20);
        assertLayers(80, 60);
        cy.get<{ value: number }>('@nativeSize').then((size) => {
            size.value = 24;
        });
        assertSize(30);
        assertLayers(120, 90);
        cy.get('.board-size-controls__fixed-toggle').click();
        assertSize(40);
        cy.get('.board-size-controls__auto-toggle').click();
        assertSize('auto');
        cy.get('.board-size-controls__fixed-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('40px');
        });
        cy.get('.board-size-controls__relative-toggle').should(($button) => {
            expect($button.text().trim()).to.eq('125%');
        });
    });

    it('changes size without seeking or pausing and rejects empty or nonpositive input', () => {
        mountBoard();
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        editNumber('.board-size-controls__fixed-input', '');
        cy.get('.board-size-controls__fixed-input').should('have.value', '32');
        editNumber('.board-size-controls__fixed-input', '0');
        cy.get('.board-size-controls__fixed-input').should('have.value', '1');
        cy.get('.board-size-controls__fixed .board-settings-control__handle').click();
        cy.get('.board-size-controls__relative-toggle').click();
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.board-size-controls__fixed-toggle').click();
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
        cy.get('.analyzer-progress-bar__slider').should(($slider) => {
            expect(Number($slider.val())).to.be.greaterThan(5000);
        });
        cy.get('.analyzer-progress-bar__play').click();
    });
});
