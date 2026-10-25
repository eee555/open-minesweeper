import { getMinigameDatabase, MINIGAME_RESULTS_STORE, readMinigameHistoryEntry } from '../../src/utils/minigame/history';
import type { MinigameHistoryEntry } from '../../src/utils/minigame/history';

export function isolateMinigameHistory(): void {
    const clear = () => cy.then(async () => {
        const db = await getMinigameDatabase();
        await db.clear(MINIGAME_RESULTS_STORE);
    });
    beforeEach(clear);
    afterEach(clear);
}

export function savedMinigameResults(): Cypress.Chainable<MinigameHistoryEntry[]> {
    return cy.then(async () => {
        const db = await getMinigameDatabase();
        return Promise.all((await db.getAll(MINIGAME_RESULTS_STORE)).map(readMinigameHistoryEntry));
    });
}

/** 使用当前棋盘的坐标触发真实按钮事件，不依赖之前的 mousemove。默认格子大小为 32px。 */
export function mouseAt(row: number, column: number, type: 'mousedown' | 'mouseup' | 'mousemove', button = 0, buttons = type === 'mousedown' ? 1 : 0, size = 32): void {
    cy.get('[data-cy="minigame-board"]').scrollIntoView({ duration: 0 });
    cy.get('[data-cy="minigame-board"]').then(($board) => {
        const rect = $board[0].getBoundingClientRect();
        const x = (column + 0.5) * size;
        const y = (row + 0.5) * size;
        cy.wrap($board).trigger(type, x, y, { eventConstructor: 'MouseEvent', button, buttons, clientX: rect.left + x, clientY: rect.top + y, scrollBehavior: false });
    });
}

export function chordAt(row: number, column: number): void {
    mouseAt(row, column, 'mousedown');
    mouseAt(row, column, 'mousedown', 2, 3);
    mouseAt(row, column, 'mouseup', 0, 2);
    mouseAt(row, column, 'mouseup', 2, 0);
}

export function rightAt(row: number, column: number): void {
    mouseAt(row, column, 'mousedown', 2, 2);
    mouseAt(row, column, 'mouseup', 2, 0);
}

/** Synthetic contacts use the real PointerEvent API; tests stub native pointer capture. */
export function touchAt(row: number, column: number, type: 'pointerdown' | 'pointermove' | 'pointerup' | 'pointercancel', pointerId = 1, pointerType = 'touch', size = 32): void {
    cy.get('[data-cy="minigame-board"]').scrollIntoView({ duration: 0 });
    cy.get('[data-cy="minigame-board"]').then(($board) => {
        const rect = $board[0].getBoundingClientRect();
        const x = (column + 0.5) * size;
        const y = (row + 0.5) * size;
        cy.wrap($board).trigger(type, x, y, { eventConstructor: 'PointerEvent', pointerId, pointerType, isPrimary: pointerId === 1, clientX: rect.left + x, clientY: rect.top + y, scrollBehavior: false });
    });
}
