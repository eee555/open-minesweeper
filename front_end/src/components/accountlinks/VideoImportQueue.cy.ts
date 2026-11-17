import { mockSaoleiImportSummary, mountAccountLink, resetAccountLinkStore } from './testUtils';
import VideoImportQueue from './VideoImportQueue.vue';

const source = { id: 7, remote_id: 1007, level: 'b', timems: 1000, bv: 4, nf: false, software: '元扫雷', status: 0, upload_time: '2026-11-01T00:00:00Z', import_video: null, import_rejected: false };
type QueueRow = typeof source;
const controls = '[data-cy=saolei-refresh-full], [data-cy=saolei-refresh-incremental], [data-cy=saolei-import-all]';
const TABLE = '[data-cy=saolei-import-table] table';
const PAGINATION = '[data-cy=saolei-import-pagination]';
const COLUMN_COUNT = 8;
const levels = ['b', 'e', 'i'] as const;

function row(overrides: Partial<QueueRow> = {}): QueueRow {
    return { ...source, ...overrides };
}

const manyRows: QueueRow[] = Array.from({ length: 12 }, (_, index) => row({
    id: index + 1,
    remote_id: index + 1,
    level: levels[index % levels.length] ?? 'b',
    timems: 1000 + index,
    bv: 10 - index,
    upload_time: `2026-01-${String(index + 1).padStart(2, '0')}T00:00:00Z`,
    software: index % 4 === 0 ? 'Unknown' : '元扫雷',
    import_rejected: index % 5 === 1,
}));
let videoItems: QueueRow[] = [source];

function mountQueue() {
    mountAccountLink(VideoImportQueue, { saoleiId: 101, owner: true });
    cy.wait('@videos');
    cy.wait('@importSummary');
}

function tableIds(rows: string[][]): string[] {
    return rows.slice(1).filter((cells) => cells.length === COLUMN_COUNT).map((cells) => cells[0]);
}

function expectIds(expected: string[]) {
    cy.get(TABLE).extractTableData().should((rows: string[][]) => {
        expect(tableIds(rows)).to.deep.equal(expected);
    });
}

function chooseFilter(trigger: string, listbox: string, value: string) {
    cy.get(`[data-cy=${trigger}]`).click();
    cy.get(`[data-cy=${listbox}] input[data-listbox-value=${value}]`).check();
}

describe('<VideoImportQueue />', () => {
    beforeEach(() => {
        resetAccountLinkStore();
        mockSaoleiImportSummary();
        videoItems = [source];
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', (req) => {
            req.reply({ body: { items: videoItems, next_after: null } });
        }).as('videos');
    });

    for (const full of [true, false]) {
        it(`${full ? 'fully' : 'incrementally'} refreshes the list without importing and disables other actions until complete`, () => {
            let release!: () => void;
            const gate = new Promise<void>((resolve) => {
                release = resolve;
            });
            const cursor = full ? 0 : 1000;
            cy.intercept('POST', '**/api/accountlink/saolei/101/sync/start', { body: { cursor, upper_bound: 1007 } }).as('start');
            cy.intercept('POST', '**/api/accountlink/saolei/101/sync/page', (req) => gate.then(() => {
                req.reply({ body: { cursor: 1007, has_more: false } });
            })).as('page');
            cy.intercept('POST', '**/api/accountlink/saolei/videos/*/import', { body: {} }).as('import');
            mountQueue();
            cy.get(`[data-cy=saolei-refresh-${full ? 'full' : 'incremental'}]`).should('have.attr', 'title').and('include', full ? 'from the beginning' : 'saved cursor');
            cy.get(`[data-cy=saolei-refresh-${full ? 'full' : 'incremental'}]`).click();
            cy.wait('@start').its('request.body').should('deep.equal', { full });
            cy.get(controls).each(($button) => {
                cy.wrap($button).should('be.disabled');
            });
            cy.then(() => {
                release();
            });
            cy.wait('@page').its('request.body').should('deep.equal', { cursor, upper_bound: 1007 });
            cy.wait('@videos');
            cy.wait('@importSummary');
            cy.get('[data-cy=saolei-import-all]').should('be.enabled');
            cy.get('@import.all').should('have.length', 0);
            cy.contains('Refreshed 1 list pages').should('be.visible');
        });
    }

    it('imports pending replays without refreshing the catalogue and reports rejected files', () => {
        cy.intercept({ method: 'GET', pathname: '/api/accountlink/saolei/101/videos', query: { pending: 'true' } }, { body: { items: [source], next_after: null } }).as('pending');
        cy.intercept('POST', '**/api/accountlink/saolei/101/sync/start', { body: {} }).as('start');
        cy.intercept('POST', '**/api/accountlink/saolei/videos/7/import', { statusCode: 400, body: { object: 'file', category: 'review' } }).as('import');
        mountQueue();
        cy.get('[data-cy=saolei-import-all]').should('have.attr', 'title').and('include', 'eligible pending replays');
        cy.get('[data-cy=saolei-import-all]').click();
        cy.wait('@pending');
        cy.wait('@import');
        cy.wait('@videos');
        cy.wait('@importSummary');
        cy.get('[data-cy=saolei-import-all]').should('be.enabled');
        cy.get('@start.all').should('have.length', 0);
        cy.contains('Processed 1 replays; 1 failed').should('be.visible');
        cy.contains('file/review').should('be.visible');
    });

    it('shows the empty state without queue rows', () => {
        videoItems = [];
        mountQueue();
        cy.get(TABLE).extractTableData().should((rows: string[][]) => {
            expect(rows[1]).to.deep.equal(['No replays']);
        });
    });

    it('sorts locally and cycles the three-state header', () => {
        videoItems = manyRows;
        mountQueue();
        const sortHeader = () => cy.get('[data-cy=sort-remote-id]').closest('th');
        expectIds(['12', '11', '10', '9', '8', '7', '6', '5', '4', '3']);
        sortHeader().should('have.attr', 'aria-sort', 'none');
        cy.get('[data-cy=sort-remote-id]').click();
        sortHeader().should('have.attr', 'aria-sort', 'ascending');
        expectIds(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
        cy.get('[data-cy=sort-remote-id]').click();
        sortHeader().should('have.attr', 'aria-sort', 'descending');
        expectIds(['12', '11', '10', '9', '8', '7', '6', '5', '4', '3']);
        cy.get('[data-cy=sort-remote-id]').click();
        sortHeader().should('have.attr', 'aria-sort', 'none');
        expectIds(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']);
    });

    it('keeps both filters inside their own headers', () => {
        mountQueue();
        cy.get('[data-cy=filter-level-trigger]').closest('th').should('contain.text', 'Level');
        cy.get('[data-cy=filter-import-status-trigger]').closest('th').should('contain.text', 'State');
        cy.get(`${TABLE} thead th`).should('have.length', COLUMN_COUNT);
        cy.get('[data-cy=filter-level-trigger] i').should('have.class', 'pi-filter');
        cy.get('[data-cy=filter-import-status-trigger] i').should('have.class', 'pi-filter');
    });

    it('localizes the level options inside the header filter', () => {
        mountQueue();
        cy.get('[data-cy=filter-level-trigger]').click();
        cy.get('[data-cy=filter-level]').should('contain.text', 'Beginner').and('contain.text', 'Intermediate').and('contain.text', 'Expert');
    });

    it('filters by level and import status, paginates and resets the start index', () => {
        videoItems = manyRows;
        mountQueue();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-10 / 12');
        expectIds(['12', '11', '10', '9', '8', '7', '6', '5', '4', '3']);
        cy.get(`${PAGINATION} [data-cy=next]`).click();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '11-12 / 12');
        expectIds(['2', '1']);
        chooseFilter('filter-level-trigger', 'filter-level', 'b');
        cy.get('[data-cy=filter-level-trigger] i').should('have.class', 'pi-filter-fill');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-4 / 4');
        expectIds(['10', '7', '4', '1']);
        chooseFilter('filter-import-status-trigger', 'filter-import-status', 'rejected');
        cy.get('[data-cy=filter-import-status-trigger] i').should('have.class', 'pi-filter-fill');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-1 / 1');
        expectIds(['7']);
        cy.get(`${PAGINATION} [data-cy=page-size]`).select('5');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-1 / 1');
        chooseFilter('filter-level-trigger', 'filter-level', 'null');
        chooseFilter('filter-import-status-trigger', 'filter-import-status', 'null');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-5 / 12');
        expectIds(['12', '11', '10', '9', '8']);
        cy.get(`${PAGINATION} [data-cy=jump]`).clear();
        cy.get(`${PAGINATION} [data-cy=jump]`).type('6{enter}');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '6-10 / 12');
        expectIds(['7', '6', '5', '4', '3']);
    });

    it('imports one replay from the row action without a catalogue refresh', () => {
        cy.intercept('POST', '**/api/accountlink/saolei/videos/7/import', { body: { status: 'imported', import_video: 7 } }).as('importOne');
        cy.intercept('POST', '**/api/accountlink/saolei/101/sync/start', { body: {} }).as('start');
        mountQueue();
        cy.get('[data-cy=saolei-import-row]').click();
        cy.wait('@importOne');
        cy.wait('@videos');
        cy.wait('@importSummary');
        cy.get('@start.all').should('have.length', 0);
    });
});
