import { BoardBackground, BoardProbability, MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import type { VueWrapper } from '@vue/test-utils';
import { transpose } from 'd3-array';
import { defineComponent, h, ref } from 'vue';

import PlayerMain from './PlayerMain.vue';

import type { AnyVideo } from '@/utils/fileIO';
import { replayPressedBackground } from '@/utils/replayBoardPress';

describe('<PlayerMain />', () => {
    it('updates pressed backgrounds on playback frames while preserving flags', () => {
        const board = [[10, 10, 10], [10, 11, 10], [10, 10, 10]];
        const currentMs = ref(0);
        const video = { game_board: board, game_board_poss: [], mine_num: 1, flag: 1, mouse_state: 4 } as unknown as AnyVideo;
        cy.mount(defineComponent({
            setup: () => () => h(PlayerMain, { video, currentMs: currentMs.value, cursorPosition: { rowIndex: 1.5, columnIndex: 2.5 }, showProbability: false }),
        })).then(({ wrapper }) => {
            cy.wrap(wrapper).as('player');
        });
        for (const [state, expected] of [
            [4, [[false, false, false], [false, false, true], [false, false, false]]],
            [5, [[false, true, true], [false, false, true], [false, true, true]]],
            [6, [[false, true, true], [false, false, true], [false, true, true]]],
            [1, undefined],
        ] as const) {
            cy.then(() => {
                Object.assign(video, { mouse_state: state });
                currentMs.value++;
            });
            cy.get<VueWrapper>('@player').should((wrapper) => {
                expect(wrapper.findComponent(BoardBackground).props('board')).to.deep.eq(expected);
            });
        }
    });

    it('transposes every board layer and swaps the display cursor', () => {
        const board = [[10, 11, 10], [12, 13, 14], [15, 16, 17]];
        const probability = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]];
        const cursorPosition = { rowIndex: 1.5, columnIndex: 2.5 };
        const pressed = replayPressedBackground(board, 4, cursorPosition);
        if (pressed === undefined) throw new Error('Expected a pressed background.');
        const video = { game_board: board, game_board_poss: probability, mine_num: 1, flag: 1, mouse_state: 4 } as unknown as AnyVideo;
        cy.mount(defineComponent({
            setup: () => () => h(PlayerMain, { video, currentMs: 0, cursorPosition, showProbability: true, transposed: true }),
        })).then(({ wrapper }) => {
            cy.wrap(wrapper).as('player');
        });
        cy.get<VueWrapper>('@player').should((wrapper) => {
            expect(wrapper.findComponent(MinesweeperBoard).props('board')).to.deep.eq(transpose(board));
            expect(wrapper.findComponent(MinesweeperBoard).props('cursorPosition')).to.deep.eq({ rowIndex: 2.5, columnIndex: 1.5 });
            expect(wrapper.findComponent(BoardBackground).props('board')).to.deep.eq(transpose(pressed));
            expect(wrapper.findComponent(BoardProbability).props('board')).to.deep.eq(transpose(probability));
        });
    });
});
