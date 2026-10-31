import { createI18n } from 'vue-i18n';

import App from '../../../local-minigame/App.vue';
import version from '../../../local-minigame/version.json';

import type MiniGameBoard from '@/components/MiniGame/Board.vue';
import en from '@/i18n/locales/en';
import zhCn from '@/i18n/locales/zh-cn';
import { loadReplayArchiveCodec } from '@/utils/minigame/archive';
import { flagChordModes } from '@/utils/minigame/flagChordTraining';
import { getMinigameDatabase, MINIGAME_RESULTS_STORE } from '@/utils/minigame/history';
import type { MinigameStoredEntry } from '@/utils/minigame/history';
import { leftClickModes, multiTouchModes } from '@/utils/minigame/leftClickTraining';
import { missingCellModes } from '@/utils/minigame/missingCellTraining';
import { defaultMinigameSettings, minigameSettings } from '@/utils/minigame/settings';
import { isolateMinigameHistory, mouseAt, rightAt, savedMinigameResults } from '@cy/support/minigame';

function mountOfflineApp() {
    const i18n = createI18n({ legacy: false, locale: 'en', messages: { en, 'zh-cn': zhCn } });
    cy.mount(App, { global: { plugins: [i18n], stubs: { transition: false } } });
}

describe('offline minigames', () => {
    isolateMinigameHistory();

    beforeEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });
    afterEach(() => {
        minigameSettings.value = defaultMinigameSettings();
    });

    it('shares cell size across offline games and mine display settings between left-click and multi-touch training', () => {
        mountOfflineApp();
        cy.get('[data-cy="minigame-cell-size"]').clear();
        cy.get('[data-cy="minigame-cell-size"]').type('24');
        cy.get('[data-cy="minigame-cell-size"]').blur();
        cy.get('[data-cy="minigame-board"]').should(($board) => {
            expect($board[0].getBoundingClientRect().width).to.be.closeTo(8 * 24, 0.5);
        });
        cy.get('[data-cy="minigame-mine-opacity"]').invoke('val', '0.25').trigger('input');
        cy.get('.minigame-board-foreground').should('have.css', 'opacity', '0.25');
        cy.get('[data-cy="minigame-mine-down"]').parent().click();
        cy.get('[data-cy="game-multi-touch"]').click();
        cy.get('[data-cy="training-game"]').should('have.attr', 'aria-label', 'Multi-touch training');
        cy.get('.minigame-board-foreground').should('have.css', 'opacity', '0.25');
        cy.get<ComponentWrapper<typeof App>>('@vue').should((wrapper) => {
            expect(wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('minePressed')).to.eq(true);
        });
        for (const game of ['flag-chord', 'missing-cell']) {
            cy.get(`[data-cy="game-${game}"]`).click();
            cy.get('[data-cy="minigame-cell-size"]').should('have.value', '24');
            cy.get('[data-cy="minigame-board"]').should(($board) => {
                expect($board[0].getBoundingClientRect().width).to.be.closeTo(8 * 24, 0.5);
            });
            cy.get('.minigame-board-foreground').should('have.css', 'opacity', '1');
        }
        cy.get('[data-cy="game-left-click"]').click();
        cy.get('[data-cy="minigame-cell-size"]').should('have.value', '24');
        cy.get('[data-cy="minigame-mine-opacity"]').should('have.value', '0.25');
        cy.get('[data-cy="minigame-mine-down"]').should('be.checked');
        cy.get('.minigame-board-foreground').should('have.css', 'opacity', '0.25');
    });

    it('saves one restart hotkey for all games, ignores edits and repeated keys, and allows clearing it', () => {
        mountOfflineApp();
        cy.get('[data-cy="minigame-restart-hotkey"]').should('have.value', '');
        cy.get('[data-cy="minigame-clear-hotkey"]').should('be.disabled');
        cy.get('[data-cy="game-missing-cell"]').click();
        mouseAt(0, 0, 'mousedown');
        mouseAt(0, 0, 'mouseup');
        cy.window().trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        cy.get('[data-cy="minigame-restart-hotkey"]').focus();
        cy.get('[data-cy="minigame-restart-hotkey"]').trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
        cy.get('[data-cy="minigame-restart-hotkey"]').should('have.value', 'F2');
        cy.get('[data-cy="minigame-restart-hotkey"]').blur();
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        cy.window().its('localStorage').invoke('getItem', 'minigame-settings').should((value) => {
            expect(JSON.parse(String(value))).to.have.nested.property('restartHotkey.code', 'F2');
        });
        for (const extra of [{ repeat: true }, { isComposing: true }, { ctrlKey: true }]) {
            cy.window().trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2', ...extra });
            cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        }
        cy.get('[data-cy="minigame-cell-size"]').focus();
        cy.get('[data-cy="minigame-cell-size"]').trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
        cy.get('[data-cy="minigame-cell-size"]').blur();
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        for (const [game, prefix] of [['left-click', 'training'], ['flag-chord', 'flag-chord'], ['missing-cell', 'missing-cell']]) {
            cy.get(`[data-cy="game-${game}"]`).click();
            cy.get('[data-cy="minigame-restart-hotkey"]').should('have.value', 'F2');
            cy.get<ComponentWrapper<typeof App>>('@vue').then((wrapper) => {
                const board: number[][] = wrapper.findComponent<typeof MiniGameBoard>('[data-cy="minigame-board"]').props('board');
                const value = game === 'flag-chord' ? 16 : 10;
                const [cell] = board.flatMap((row, r) => row.flatMap((entry, c) => (entry === value ? [{ row: r, column: c }] : [])));
                if (game === 'flag-chord') rightAt(cell.row, cell.column);
                else {
                    mouseAt(cell.row, cell.column, 'mousedown');
                    mouseAt(cell.row, cell.column, 'mouseup');
                }
            });
            cy.get(`[data-cy="${prefix}-game"]`).should('have.attr', 'data-phase', 'playing');
            cy.get('[data-cy="minigame-board"]').should('be.focused');
            cy.window().trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
            cy.get(`[data-cy="${prefix}-game"]`).should('have.attr', 'data-phase', 'ready');
            cy.get(`[data-cy="${prefix}-time"]`).should('have.attr', 'aria-label', '000.000');
        }
        cy.get('[data-cy="minigame-clear-hotkey"]').click();
        cy.get('[data-cy="minigame-restart-hotkey"]').should('have.value', '');
        mouseAt(0, 0, 'mousedown');
        mouseAt(0, 0, 'mouseup');
        cy.window().trigger('keydown', { eventConstructor: 'KeyboardEvent', code: 'F2', key: 'F2' });
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
    });

    it('plays the shared game with local language/theme controls and no download link', () => {
        mountOfflineApp();
        cy.contains(`v${version.version}`).should('be.visible');
        cy.get('[data-cy="training-download"]').should('not.exist');
        cy.get('[data-cy="minigame-cell-size"]').should('have.value', '32');
        cy.get('[data-cy="training-level"] input:checked').should('have.length', 1).and('have.value', 'b');
        cy.get('[data-cy="training-density"]').select('87.5');
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '008');
        cy.get('[data-cy="offline-language"]').click();
        cy.get('.training-page').should('have.attr', 'aria-label', '左键训练');
        cy.get('.training-page header, .training-page h1, [data-cy="training-restart"]').should('not.exist');
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '008');
        cy.document().its('documentElement.lang').should('eq', 'zh-cn');
        cy.get('[data-cy="offline-theme"]').select('dark');
        cy.get('html').should('have.class', 'dark');
        cy.get('[data-cy="offline-theme"]').select('light');
        cy.get('html').should('not.have.class', 'dark');
        cy.get('.training-frame-counters').click();
        cy.get('[data-cy="training-game"]').should('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy="training-time"]').should('have.attr', 'aria-label', '000.000');
        cy.get('details').first().find('summary').click();
        cy.get('details').first().should('contain.text', 'No server or internet connection is required.');
        cy.get('[data-cy="game-flag-chord"]').click();
        cy.get('.training-page').should('have.attr', 'aria-label', '标双训练');
        cy.get('.training-page header, .training-page h1, [data-cy="flag-chord-restart"]').should('not.exist');
        cy.get('[data-cy="flag-chord-download"]').should('not.exist');
        cy.get('[data-cy="minigame-cell-size"]').should('have.value', '32');
        cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '004');
        cy.get('[data-cy="flag-chord-level"] input[value="i"]').parent().click();
        cy.get('[data-cy="flag-chord-level"] input:checked').should('have.length', 1).and('have.value', 'i');
        cy.get('[data-cy="flag-chord-remaining"]').should('have.attr', 'aria-label', '015');
        cy.get('[data-cy="game-missing-cell"]').click();
        cy.get('.training-page').should('have.attr', 'aria-label', '漏雷训练');
        cy.get('.training-page header, .training-page h1, [data-cy="missing-cell-restart"]').should('not.exist');
        cy.get('[data-cy="missing-cell-download"]').should('not.exist');
        cy.get('[data-cy="minigame-cell-size"]').should('have.value', '32');
        cy.get('[data-cy="missing-cell-remaining"]').should('have.attr', 'aria-label', '010');
        mouseAt(0, 0, 'mousedown');
        mouseAt(0, 0, 'mouseup');
        cy.get('[data-cy="missing-cell-game"]').should('have.attr', 'data-phase', 'playing');
        cy.get('[data-cy="game-left-click"]').click();
        cy.get('[data-cy="training-remaining"]').should('have.attr', 'aria-label', '032');
    });

    it('filters and replays all four games from local history without making API requests or duplicating results', () => {
        cy.viewport(1440, 1000);
        const initialBoard = 'AAAAAP////8';
        const mouse = { version: 1, cellSize: 32, initialBoard, events: [], specialEvents: [] };
        const recordings = [
            { game: 'left-click', mode: leftClickModes[0], source: mouse },
            { game: 'multi-touch', mode: multiTouchModes[0], source: { version: 1, cellSize: 32, initialBoard, events: [[0, 16, 16, 0, 0]] } },
            { game: 'flag-chord', mode: flagChordModes[0], source: { ...mouse, initialBoard: [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]] } },
            { game: 'missing-cell', mode: missingCellModes[0], source: { version: 1, rounds: Array.from({ length: 10 }, () => ({ board: 'gAAAAAAAAAA', target: [7, 7], timeMs: 100 })) } },
        ] as const;
        cy.then(async () => {
            const codec = await loadReplayArchiveCodec();
            const db = await getMinigameDatabase();
            for (const recording of recordings) {
                await db.add(MINIGAME_RESULTS_STORE, { game: recording.game, mode: recording.mode, playedAt: Date.now(), scoreMs: 1234, replay: codec.pack(recording.source) } as MinigameStoredEntry);
            }
        });
        cy.intercept('/api/**', { statusCode: 500 }).as('api');
        mountOfflineApp();
        cy.get('[data-cy=minigame-history-toggle]').click();
        for (const { game } of recordings) {
            cy.get(`[data-cy=game-${game}]`).click();
            cy.get('.history-row').should('have.length', 1);
            cy.get('.history-row').click();
            cy.get('.training-page').should('have.attr', 'data-replay', 'true').and('have.attr', 'data-phase', 'won');
            const prefix = game === 'flag-chord' ? 'flag-chord' : game === 'missing-cell' ? 'missing-cell' : 'training';
            cy.get(`[data-cy=${prefix}-time]`).should('have.attr', 'aria-label', '001.234');
            if (game === 'missing-cell') cy.get('[data-cy=missing-cell-round-times] .plot-bar rect').should('have.length', 10);
            else cy.get('[data-cy=minigame-replay-controls]').should('be.visible');
            cy.get('.training-frame-counters').click();
            cy.get('.training-page').should('have.attr', 'data-replay', 'false').and('have.attr', 'data-phase', 'ready');
        }
        cy.get('[data-cy=game-left-click]').click();
        cy.get('.history-row').click();
        cy.get('.training-page').should('have.attr', 'data-replay', 'true');
        cy.get('[data-cy=training-density]').select('75');
        cy.get('.training-page').should('have.attr', 'data-replay', 'false').and('have.attr', 'data-phase', 'ready');
        cy.get('[data-cy=minigame-history-panel]').should('contain.text', 'No matching local results');
        cy.get('[data-cy=offline-theme]').select('dark');
        cy.get('[data-cy=offline-language]').click();
        cy.get('.el-drawer').should('have.attr', 'aria-label', '本地历史');
        cy.get('.el-drawer__close-btn').click();
        cy.get('[data-cy=minigame-history-toggle]').should('be.visible');
        savedMinigameResults().should('have.length', 4);
        cy.get('@api.all').should('have.length', 0);
    });

    it('reports a damaged recording and keeps it in local history', () => {
        cy.viewport(1440, 1000);
        cy.then(async () => {
            const db = await getMinigameDatabase();
            await db.add(MINIGAME_RESULTS_STORE, { game: 'left-click', mode: leftClickModes[0], playedAt: Date.now(), scoreMs: 1234, replay: new ArrayBuffer(0) });
        });
        mountOfflineApp();
        cy.get('[data-cy=minigame-history-toggle]').click();
        cy.get('.history-row').click();
        cy.get('[data-cy=minigame-replay-error]').should('contain.text', 'damaged');
        cy.get('.training-page').should('have.attr', 'data-phase', 'ready');
        cy.get('.history-row').should('have.length', 1);
        cy.get('.training-frame-counters').click();
        cy.get('[data-cy=minigame-replay-error]').should('not.exist');
        cy.then(async () => {
            const db = await getMinigameDatabase();
            expect(await db.count(MINIGAME_RESULTS_STORE)).to.equal(1);
        });
    });
});
