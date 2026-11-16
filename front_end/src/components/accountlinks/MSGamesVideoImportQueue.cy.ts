import MSGamesVideoImportQueue from './MSGamesVideoImportQueue.vue';
import { mountAccountLink } from './testUtils';

import type { MSGamesVideo } from '@/utils/accountlinks';

const source: MSGamesVideo = {
    id: 1,
    user: 42,
    url: 'https://minesweepergame.com/member/file/42/example.avf',
    filename: 'example.avf',
    upload_date: '2020-02-29',
    category: 'Time / beginner, beginner_nf / NF / Official',
    score: 'Time: 0.490; 3BV: 3; 3BVS: 6.122',
    import_video: null,
};
const summary = { total: 2, imported: 0, video_update_time: null };
const TABLE = '[data-cy=msgames-import-table] table';
const PAGINATION = '[data-cy=msgames-import-pagination]';

function catalogueVideo(id: number, overrides: Partial<MSGamesVideo> = {}): MSGamesVideo {
    const filename = overrides.filename ?? `video-${id}.avf`;
    return { ...source, id, ...overrides, filename, url: new URL(filename, source.url).href };
}

describe('<MSGamesVideoImportQueue />', () => {
    it('shows an API failure and retries synchronously to a local video link', () => {
        let attempts = 0;
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', (request) => {
            request.reply({ body: [{ ...source, import_video: attempts > 1 ? 77 : null }] });
        }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        cy.intercept('POST', '**/api/accountlink/msgames/videos/1/import', (request) => {
            attempts++;
            if (attempts === 1) request.reply({ statusCode: 502, body: { type: 'error', object: 'import', category: 'timeout' } });
            else request.reply({ status: 'IMPORTED', import_video_id: 77, video_state: 'o' });
        }).as('import');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: true });
        cy.wait(['@videos', '@summary']);
        cy.contains('tbody button', 'Import').click();
        cy.wait('@import');
        cy.wait('@videos');
        cy.contains('tbody', 'import/timeout');
        cy.get('select[aria-label="Filter import status"]').select('failed');
        cy.get('tbody tr').should('have.length', 1).and('contain', 'import/timeout');
        cy.get('select[aria-label="Filter import status"]').select('All statuses');
        cy.contains('tbody button', 'Retry').click();
        cy.wait('@import');
        cy.wait('@videos');
        cy.contains('a', '#77').should('have.attr', 'href', '#/video/77');
        cy.get('tbody button').should('not.exist');
    });

    it('shows the visitor catalogue and paginates locally after one request', () => {
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', {
            body: Array.from({ length: 21 }, (_, index) => catalogueVideo(index + 1, index === 20 ? { filename: 'legacy.mvr' } : {})),
        }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: false });
        cy.wait(['@videos', '@summary']);
        cy.contains('video-1.avf');
        cy.contains('2020-02-29');
        cy.contains('Time: 0.490');
        cy.contains('beginner_nf');
        cy.contains('tbody a', 'video-1.avf').should('have.attr', 'href', 'https://minesweepergame.com/member/file/42/video-1.avf');
        cy.get('tbody button').should('not.exist');
        cy.contains('button', 'Sync video list').should('not.exist');
        cy.contains('button', 'Import remaining videos').should('not.exist');
        cy.get('tbody tr').should('have.length', 10);
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-10 / 21');
        cy.get(`${PAGINATION} [data-cy=next]`).click();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '11-20 / 21');
        cy.contains('video-11.avf');
        cy.get(`${PAGINATION} [data-cy=segment]`).last().click();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '21-21 / 21');
        cy.contains('tbody a', 'legacy.mvr').should('have.attr', 'href', 'https://minesweepergame.com/member/file/42/legacy.mvr');
        cy.contains('tbody', 'Unsupported board or format');
        cy.get(`${PAGINATION} [data-cy=next]`).should('be.disabled');
        cy.get('@videos.all').should('have.length', 1);
    });

    it('shows the empty state and resets the start index after filters or page size changes', () => {
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', {
            body: Array.from({ length: 21 }, (_, index) => catalogueVideo(index + 1, {
                category: index % 2 === 0 ? 'Time / beginner' : 'Density / 8x8',
            })),
        }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: false });
        cy.wait(['@videos', '@summary']);
        cy.get(`${PAGINATION} [data-cy=jump]`).clear();
        cy.get(`${PAGINATION} [data-cy=jump]`).type('21{enter}');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '21-21 / 21');
        cy.get('[data-cy=filter-category]').type('Density');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-10 / 10');
        cy.get(TABLE).extractTableData().should((rows: string[][]) => {
            expect(rows).to.have.length(11);
            expect(rows[1]).to.contain('Density / 8x8');
        });
        cy.get(`${PAGINATION} [data-cy=page-size]`).select('25');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-10 / 10');
        cy.get('[data-cy=filter-category]').clear();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-21 / 21');
        cy.get('@videos.all').should('have.length', 1);
    });

    it('keeps one empty row and a zero report when the catalogue is empty', () => {
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', { body: [] }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: false });
        cy.wait(['@videos', '@summary']);
        cy.get(TABLE).extractTableData().should((rows: string[][]) => {
            expect(rows[1]).to.deep.equal(['No synced videos']);
        });
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '0-0 / 0');
        cy.get(`${PAGINATION} [data-cy=next]`).should('be.disabled');
    });

    it('sorts upload dates and combines category and import status controls in one header row', () => {
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', { body: [
            source,
            catalogueVideo(2, { filename: 'density-imported.avf', category: 'Density / 16x16', score: 'Density: Mines: 100', upload_date: '2024-01-01', import_video: 77 }),
            catalogueVideo(3, { filename: 'density-unsupported.avf', category: 'Density / 8x8', score: 'Density: Mines: 41', upload_date: '2023-01-01' }),
            catalogueVideo(4, { filename: 'oldest.avf', upload_date: '2019-01-01' }),
        ] }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: true });
        cy.wait(['@videos', '@summary']);
        cy.contains('tbody tr', 'example.avf').within(() => {
            cy.contains('button', 'Import').should('be.enabled');
        });
        cy.contains('tbody tr', 'density-unsupported.avf').within(() => {
            cy.get('a').should('have.attr', 'href', 'https://minesweepergame.com/member/file/42/density-unsupported.avf');
            cy.contains('Mines: 41');
            cy.contains('Unsupported board or format');
            cy.get('button').should('not.exist');
        });
        cy.get('thead tr').should('have.length', 1);
        cy.get('thead input[aria-label="Search category"]').should('exist');
        cy.get('thead select[aria-label="Filter import status"]').should('exist');
        cy.get('tbody tr').first().should('contain', 'density-imported.avf');
        cy.get('[data-cy=sort-upload-date]').closest('th').should('have.attr', 'aria-sort', 'descending');
        cy.get('[data-cy=sort-upload-date]').click();
        cy.get('[data-cy=sort-upload-date]').closest('th').should('have.attr', 'aria-sort', 'ascending');
        cy.get('tbody tr').first().should('contain', 'oldest.avf');
        cy.get('[data-cy=sort-upload-date]').click();
        cy.get('[data-cy=sort-upload-date]').closest('th').should('have.attr', 'aria-sort', 'descending');
        cy.get('tbody tr').first().should('contain', 'density-imported.avf');
        cy.get('input[aria-label="Search category"]').type('Density');
        cy.get('tbody tr').should('have.length', 2);
        cy.get('select[aria-label="Filter import status"]').select('imported');
        cy.get('tbody tr').should('have.length', 1).and('contain', 'density-imported.avf');
        cy.get('select[aria-label="Filter import status"]').select('unsupported');
        cy.get('tbody tr').should('have.length', 1).and('contain', 'density-unsupported.avf');
        cy.get('input[aria-label="Search category"]').clear();
        cy.get('select[aria-label="Filter import status"]').select('pending');
        cy.get('tbody tr').should('have.length', 2);
    });

    it('waits for each batch response and skips unsupported or imported rows in the full catalogue', () => {
        const requested: number[] = [];
        let releaseFirst: (() => void) | undefined;
        let synced = false;
        cy.intercept('POST', '**/api/accountlink/msgames/42/sync', (request) => {
            synced = true;
            request.reply({ status: 'SYNCED', count: 5, video_update_time: '2026-10-14T00:00:00Z' });
        }).as('sync');
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', { body: [
            source, catalogueVideo(2, { filename: 'legacy.mvr' }), catalogueVideo(3, { import_video: 76 }),
            catalogueVideo(4, { filename: 'another.avf' }), catalogueVideo(5),
        ] }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        cy.intercept('POST', '**/api/accountlink/msgames/videos/*/import', (request) => {
            const id = Number(request.url.split('/').at(-2));
            requested.push(id);
            expect(synced).to.equal(true);
            if (id === 1) {
                return new Promise<void>((resolve) => {
                    releaseFirst = () => {
                        request.reply({ status: 'IMPORTED', import_video_id: 77, video_state: 'o' });
                        resolve();
                    };
                });
            }
            if (id === 4) request.reply({ statusCode: 400, body: { type: 'error', object: 'file', category: 'review' } });
            else request.reply({ status: 'IMPORTED', import_video_id: 78, video_state: 'o' });
        }).as('import');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: true });
        cy.wait(['@videos', '@summary']);
        cy.contains('button', 'Import remaining videos').click();
        cy.wait('@sync');
        cy.contains('tbody', 'Importing').should('be.visible');
        cy.wrap(requested).should('deep.equal', [1]).then(() => {
            releaseFirst?.();
        });
        cy.wait('@import');
        cy.wait('@import');
        cy.wait('@import');
        cy.contains('3/3 processed, 1 failed').should('be.visible');
        cy.contains('button', 'Stop further imports').should('not.exist').then(() => {
            expect(requested).to.deep.equal([1, 4, 5]);
        });
    });

    it('stops a batch after its current request finishes', () => {
        const requested: number[] = [];
        let releaseFirst: (() => void) | undefined;
        cy.intercept('GET', '**/api/accountlink/msgames/videos?*', { body: [source, catalogueVideo(2)] }).as('videos');
        cy.intercept('GET', '**/api/accountlink/msgames/summary?*', summary).as('summary');
        cy.intercept('POST', '**/api/accountlink/msgames/42/sync', { status: 'SYNCED', count: 2, video_update_time: '2026-10-14T00:00:00Z' });
        cy.intercept('POST', '**/api/accountlink/msgames/videos/*/import', (request) => {
            requested.push(Number(request.url.split('/').at(-2)));
            return new Promise<void>((resolve) => {
                releaseFirst = () => {
                    request.reply({ status: 'IMPORTED', import_video_id: 77, video_state: 'o' });
                    resolve();
                };
            });
        }).as('import');
        mountAccountLink(MSGamesVideoImportQueue, { msgamesId: 42, owner: true });
        cy.wait(['@videos', '@summary']);
        cy.contains('button', 'Import remaining videos').click();
        cy.contains('tbody', 'Importing').should('be.visible');
        cy.wrap(requested).should('deep.equal', [1]);
        cy.contains('button', 'Stop further imports').click();
        cy.then(() => releaseFirst?.());
        cy.wait('@import');
        cy.contains('1/2 processed, 0 failed').should('be.visible');
        cy.contains('button', 'Stop further imports').should('not.exist').then(() => {
            expect(requested).to.deep.equal([1]);
        });
    });
});
