import type { BoardBackground } from '@putianyi888/vue3-minesweeper-board';
import { defineComponent, h } from 'vue';

import MiniGameSettings from './MiniGame.vue';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import i18n from '@/i18n';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import type { MinigameSettings } from '@/utils/minigame/settings';
import LeftClickTraining from '@/views/MiniGameView/LeftClickTraining/App.vue';
import { mouseAt } from '@cy/support/minigame';

const SettingsAndTraining = defineComponent({ expose: [], render: () => h('div', [h(MiniGameSettings), h(LeftClickTraining, { offline: true })]) });

describe('minigame settings section', () => {
    beforeEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });

    it('saves shared cell size and mine display settings without restarting an ongoing game', () => {
        cy.mount(SettingsAndTraining, { global: { plugins: [i18n] } });
        cy.get('[data-cy="minigame-settings-section"] .card-title').should('have.text', 'Minigames');
        cy.get('[data-cy="minigame-restart-hotkey"]').should('be.visible');
        cy.get('[data-cy="minigame-cell-size"]').should('have.value', '32');
        cy.get('[data-cy="minigame-mine-opacity"]').should('have.value', '0.5');
        cy.get('[data-cy="minigame-mine-up"]').should('be.checked');
        cy.get('.minigame-board-foreground').should('have.css', 'opacity', '0.5');
        cy.get<ComponentWrapper<typeof SettingsAndTraining>>('@vue').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            const [safe] = board.flatMap((row, r) => row.flatMap((value, c) => (value === 10 ? [{ row: r, column: c }] : [])));
            mouseAt(safe.row, safe.column, 'mousedown');
            mouseAt(safe.row, safe.column, 'mouseup');
        });
        cy.get('[data-cy="minigame-cell-size"]').should('have.attr', 'type', 'number');
        cy.get('[data-cy="minigame-cell-size"]').clear();
        cy.get('[data-cy="minigame-cell-size"]').type('27');
        cy.get('[data-cy="minigame-cell-size"]').blur();
        cy.get('[data-cy="minigame-board"]').should(($board) => {
            expect($board[0].getBoundingClientRect().width).to.be.closeTo(8 * 27, 0.5);
        });
        for (const opacity of [0, 0.25, 1]) {
            cy.get('[data-cy="minigame-mine-opacity"]').invoke('val', String(opacity)).trigger('input');
            cy.get('[data-cy="minigame-mine-opacity-value"]').should('have.text', `${opacity * 100}%`);
            cy.get('.minigame-board-foreground').should('have.css', 'opacity', String(opacity));
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value: string | null) => {
                const settings = JSON.parse(value ?? '{}') as Partial<MinigameSettings>;
                expect(settings.leftClickMineOpacity).to.eq(opacity);
                expect(settings.cellSize).to.eq(27);
            });
        }
        cy.get<ComponentWrapper<typeof SettingsAndTraining>>('@vue').then((wrapper) => {
            const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
            cy.get('[data-cy="minigame-mine-down"]').parent().click();
            cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '031');
            cy.get<ComponentWrapper<typeof SettingsAndTraining>>('@vue').should((current) => {
                expect(current.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board')).to.deep.eq(board);
                const background: boolean[][] | undefined = current.findComponent<typeof BoardBackground>('.minigame-board-background').props('board');
                expect(background).to.deep.eq(board.map((row) => row.map((cell) => cell === 0 || cell === 16)));
            });
        });
        cy.get('[data-cy="minigame-restart-hotkey"]').focus();
        cy.get('[data-cy="minigame-restart-hotkey"]').trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
        cy.get('[data-cy="minigame-restart-hotkey"]').blur();
        cy.get('[data-cy="minigame-mine-opacity"]').should('have.value', '1');
        cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value: string | null) => {
            const settings = JSON.parse(value ?? '{}') as Partial<MinigameSettings>;
            expect(settings.leftClickMineOpacity).to.eq(1);
            expect(settings.cellSize).to.eq(27);
            expect(settings.leftClickMinePressed).to.eq(true);
            expect(settings.restartHotkey?.code).to.eq('F2');
        });
    });
});
