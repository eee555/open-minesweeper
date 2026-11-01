import { mockSaoleiImportSummary, mountAccountLink, resetAccountLinkStore } from './testUtils';
import VideoImportQueue from './VideoImportQueue.vue';

describe('<VideoImportQueue />', () => {
    beforeEach(() => {
        resetAccountLinkStore(); mockSaoleiImportSummary();
    });

    it('synchronizes one page at a time before importing pending files', () => {
        const source = { id: 7, remote_id: 1007, level: 'b', timems: 1000, bv: 4, nf: false, software: '元扫雷', status: 0, upload_time: '2026-11-01T00:00:00Z', import_video: null, import_rejected: false };
        cy.intercept('GET', '**/api/accountlink/saolei/101/videos*', { body: { items: [source], next_after: null } }).as('videos');
        cy.intercept('POST', '**/api/accountlink/saolei/101/sync/start', { body: { cursor: 0, upper_bound: 1007 } }).as('start');
        cy.intercept('POST', '**/api/accountlink/saolei/101/sync/page', { body: { cursor: 1007, has_more: false } }).as('page');
        cy.intercept('POST', '**/api/accountlink/saolei/videos/7/import', { statusCode: 400, body: { object: 'file', category: 'review' } }).as('import');
        mountAccountLink(VideoImportQueue, { saoleiId: 101, owner: true });
        cy.wait('@videos');
        cy.get('[data-cy=saolei-sync]').click();
        cy.wait('@start');
        cy.wait('@page').its('request.body').should('deep.equal', { cursor: 0, upper_bound: 1007 });
        cy.wait('@import');
        cy.contains('processed 1 replays; 1 failed');
        cy.contains('file/review');
    });
});
