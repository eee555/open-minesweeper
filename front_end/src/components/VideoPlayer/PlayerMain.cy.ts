import { BoardBackground } from '@putianyi888/vue3-minesweeper-board';
import type { VueWrapper } from '@vue/test-utils';
import { defineComponent, h, ref } from 'vue';

import PlayerMain from './PlayerMain.vue';

import type { AnyVideo } from '@/utils/fileIO';

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
});
