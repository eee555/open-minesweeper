import { interceptFormData } from 'cypress-intercept-formdata';

import HistoryVideos from './HistoryVideos.vue';

import i18n from '@/i18n';
import { MS_State } from '@/utils/ms_const';

const importFailure = 'The history import operation failed. Please try again.';

describe('<GSC HistoryVideos />', () => {
    it('retries preparation after a lost response and uploads using the returned participant', () => {
        cy.intercept('POST', '**/api/tournament/gsc/history/prepare', { body: { id: 324, manual_scores: false } }).as('prepare');
        cy.intercept({ method: 'POST', pathname: '/api/tournament/gsc/history/prepare', times: 1 }, { forceNetworkError: true }).as('lostPrepare');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/324/identifier', { body: { identifier: 'selected', bound: true } }).as('bind');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/324/videos', { body: { id: 904, state: MS_State.Official } }).as('upload');
        cy.mount(HistoryVideos, { global: { plugins: [i18n] }, props: { order: 19, endTime: new Date('2020-01-01T00:00:00Z') } });
        cy.get('[data-cy=history-user-id]').type('101');
        cy.get('[data-cy=history-video-files]').selectFile('cypress/fixtures/standard_gsc.evf');
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 1);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@lostPrepare');
        cy.get('[role=alert]').should('contain.text', 'Retry the remaining steps');
        cy.get('@bind.all').should('have.length', 0);
        cy.get('@upload.all').should('have.length', 0);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepare').its('response.body.id').should('eq', 324);
        cy.wait('@bind');
        cy.wait('@upload');
        cy.get('[data-cy=history-video-results]').should('contain.text', 'Replay #904');
        cy.get('[role=alert]').should('not.exist');
    });

    it('deduplicates player identifiers, waits for binding and reuses the assigned timestamp when retrying uploads', () => {
        const anchor = '2020-01-01T00:00:00.000Z';
        const firstTime = new Date(new Date(anchor).getTime() - 41021).toISOString();
        let prepared = false;
        let bound = false;
        let uploadCount = 0;
        const times: string[] = [];
        cy.intercept('POST', '**/api/tournament/gsc/history/prepare', (request) => {
            const body = request.body as { order: number; user_id: number };
            expect(body.order).to.equal(19);
            expect(body.user_id).to.equal(101);
            expect(body).not.to.have.property('identifiers');
            request.on('before:response', () => {
                prepared = true;
            });
            request.reply({ delay: 100, body: { id: 321 } });
        }).as('prepare');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/321/identifier', (request) => {
            expect(prepared).to.equal(true);
            const body = request.body as { identifier: string };
            expect(body.identifier).to.be.a('string');
            request.on('before:response', () => {
                bound = true;
            });
            request.reply({ delay: 100, body: { identifier: body.identifier, bound: false } });
        }).as('bind');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/321/videos', (request) => {
            expect(bound).to.equal(true);
            const fields = interceptFormData(request);
            expect(fields.upload_time).to.equal(fields.file === 'first.evf' ? firstTime : anchor);
            times.push(String(fields.upload_time));
            request.reply(++uploadCount === 1 ? { statusCode: 500, body: { detail: 'Retry' } } : { body: { id: 901, state: MS_State.Identifier } });
        }).as('upload');
        cy.mount(HistoryVideos, { global: { plugins: [i18n] }, props: { order: 19, endTime: new Date(anchor) } });
        cy.get('[data-cy=history-user-id]').type('101');
        cy.fixture<Uint8Array>('standard_gsc.evf', null).then((content) => {
            cy.get('[data-cy=history-video-files]').selectFile([
                { contents: Cypress.Buffer.from(content), fileName: 'first.evf' },
                { contents: Cypress.Buffer.from(content), fileName: 'second.evf' },
            ]);
        });
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 1);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepare');
        cy.wait('@bind');
        cy.wait('@upload').its('response.statusCode').should('eq', 500);
        cy.wait('@upload');
        cy.get('[data-cy=history-binding-results]').should('contain.text', 'Ownership conflict');
        cy.get('[data-cy=history-video-results] table').getTable().should((rows) => {
            expect(rows[0].File).to.equal('first.evf');
            expect(rows[0]['Upload time']).to.equal(firstTime);
            expect(rows[0].Result).to.equal(importFailure);
        });
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@upload');
        cy.get('[data-cy=history-video-results]').should('contain.text', `Replay #901 / ${MS_State.Identifier}`).and('not.contain.text', importFailure);
        cy.get('@prepare.all').should('have.length', 1);
        cy.get('@bind.all').should('have.length', 1);
        cy.then(() => expect(times).to.deep.equal([firstTime, anchor, firstTime]));
    });

    it('uploads only selected identifiers and submits a custom anchor for the remaining single file', () => {
        const custom = new Date(2020, 0, 3, 12, 34, 56);
        cy.intercept('POST', '**/api/tournament/gsc/history/prepare', (request) => {
            expect(request.body).not.to.have.property('identifiers');
            request.reply({ body: { id: 322 } });
        }).as('prepare');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/322/identifier', (request) => {
            const body = request.body as { identifier: string };
            request.reply({ body: { identifier: body.identifier, bound: true } });
        }).as('bind');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/322/videos', (request) => {
            const fields = interceptFormData(request);
            expect(fields.file).to.equal('3819-Time-1616-NF-9469-32-20151031.rmv');
            expect(fields.upload_time).to.equal(custom.toISOString());
            request.reply({ body: { id: 902, state: MS_State.Official } });
        }).as('upload');
        cy.mount(HistoryVideos, { global: { plugins: [i18n] }, props: { order: 19, endTime: new Date('2020-01-01T00:00:00Z') } });
        cy.get('[data-cy=history-user-id]').type('101');
        cy.get('[data-cy=history-video-files]').selectFile(['cypress/fixtures/standard_gsc.evf', 'cypress/fixtures/3819-Time-1616-NF-9469-32-20151031.rmv']);
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 2);
        cy.get('[data-cy=history-identifiers] .el-tag__close').first().click();
        cy.get('[data-cy=history-upload-anchor] input').clear();
        cy.get('[data-cy=history-upload-anchor] input').type('2020-01-03 12:34:56{enter}');
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepare');
        cy.wait('@bind');
        cy.wait('@upload');
        cy.get('[data-cy=history-video-results] table').getTable().should('have.length', 1);
        cy.get('@upload.all').should('have.length', 1);
        cy.get('@bind.all').should('have.length', 1);
    });

    it('binds identifiers sequentially and resumes a failed binding without repeating completed steps', () => {
        const identifiers: string[] = [];
        let firstBindingFinished = false;
        let allBindingsFinished = false;
        cy.intercept('POST', '**/api/tournament/gsc/history/prepare', { body: { id: 323 } }).as('prepare');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/323/identifier', (request) => {
            const { identifier } = request.body as { identifier: string };
            identifiers.push(identifier);
            if (identifiers.length === 1) {
                request.on('before:response', () => {
                    firstBindingFinished = true;
                });
                request.reply({ delay: 100, body: { identifier, bound: true } });
            } else if (identifiers.length === 2) {
                expect(firstBindingFinished).to.equal(true);
                request.reply({ statusCode: 500 });
            } else {
                expect(identifier).to.equal(identifiers[1]);
                request.on('before:response', () => {
                    allBindingsFinished = true;
                });
                request.reply({ delay: 100, body: { identifier, bound: true } });
            }
        }).as('bind');
        cy.intercept('POST', '**/api/tournament/gsc/history/participants/323/videos', (request) => {
            expect(allBindingsFinished).to.equal(true);
            request.reply({ body: { id: 903, state: MS_State.Official } });
        }).as('upload');
        cy.mount(HistoryVideos, { global: { plugins: [i18n] }, props: { order: 19, endTime: new Date('2020-01-01T00:00:00Z') } });
        cy.get('[data-cy=history-user-id]').type('101');
        cy.get('[data-cy=history-video-files]').selectFile(['cypress/fixtures/standard_gsc.evf', 'cypress/fixtures/3819-Time-1616-NF-9469-32-20151031.rmv']);
        cy.get('[data-cy=history-identifiers] .el-tag').should('have.length', 2);
        cy.get('[data-cy=history-videos-submit]').click();
        cy.wait('@prepare');
        cy.wait('@bind');
        cy.wait('@bind').its('response.statusCode').should('eq', 500);
        cy.get('[role=alert]').should('contain.text', importFailure).and('contain.text', 'Completed steps were saved. Retry the remaining steps.').and('not.contain.text', '500');
        cy.get('@upload.all').should('have.length', 0);
        cy.get('[data-cy=history-videos-submit]').should('contain.text', 'Continue linking and upload').click();
        cy.wait('@bind');
        cy.wait('@upload');
        cy.wait('@upload');
        cy.get('[role=alert]').should('not.exist');
        cy.get('@prepare.all').should('have.length', 1);
        cy.get('@bind.all').should('have.length', 3);
        cy.then(() => {
            expect(identifiers[0]).not.to.equal(identifiers[1]);
            expect(identifiers[2]).to.equal(identifiers[1]);
        });
    });
});
