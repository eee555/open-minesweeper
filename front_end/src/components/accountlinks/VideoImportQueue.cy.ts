import { mockSaoleiImportSummary, mountAccountLink, resetAccountLinkStore } from './testUtils';
import VideoImportQueue from './VideoImportQueue.vue';

const source = { id: 7, remote_id: 1007, level: 'b', timems: 1000, bv: 4, nf: false, software: '元扫雷', status: 0, upload_time: '2026-11-01T00:00:00Z', import_video: null, import_rejected: false };
const controls = '[data-cy=saolei-refresh-full], [data-cy=saolei-refresh-incremental], [data-cy=saolei-import-all]';

describe('<VideoImportQueue />', () => {
    beforeEach(() => {
        resetAccountLinkStore();
        mockSaoleiImportSummary();
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [source], next_after: null } }).as('videos');
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
            mountAccountLink(VideoImportQueue, { saoleiId: 101, owner: true });
            cy.wait('@videos');
            cy.wait('@importSummary');
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
        mountAccountLink(VideoImportQueue, { saoleiId: 101, owner: true });
        cy.wait('@videos');
        cy.wait('@importSummary');
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
});
