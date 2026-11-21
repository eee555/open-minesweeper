import VideoView from './VideoView.vue';

import { videoColumnStore } from '@/components/VideoList/columnStore';
import { presetColumn } from '@/components/VideoList/presets';
import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';

const DEFAULT_COLUMNS = ['state', 'upload_time', 'time', 'bv', 'bvs', 'stnb', 'file_size'].map(presetColumn);

function mountView(): void {
    cy.mockPlayerNameFallback();
    videoColumnStore('mixed-players').columns.value = [...DEFAULT_COLUMNS];
    cy.intercept({ method: 'GET', pathname: '/api/video/query' }, { videos: [] }).as('videos');
    cy.mount(VideoView, {
        global: {
            plugins: [pinia, i18n],
            config: { globalProperties: { $axios } },
        },
    });
}

describe('<VideoView />', () => {
    it('renders three decoupled panels and requests the API with the current conditions', () => {
        mountView();
        cy.contains('.card-title', 'Filter');
        cy.contains('.card-title', 'Sort');
        cy.get('section[aria-label=Pagination]').should('exist');
        cy.get('[data-cy=filter-tag]').should('have.length', 2);
        cy.get('[data-cy=sort-tag]').should('have.length', 2);
        cy.get('[data-cy=video-columns-editor]').should('not.exist');
        cy.get('[data-cy=video-list-table]').should('exist');
        cy.wait('@videos').its('request.query').should((query: Record<string, string>) => {
            expect(JSON.parse(query.filters)).to.deep.equal([
                { field: 'state', in: ['c', 'a'] },
                { field: 'bv', gte: 100 },
            ]);
            expect(JSON.parse(query.sorts)).to.deep.equal([
                { field: 'timems', direction: 'asc' },
                { field: 'bv', direction: 'desc' },
            ]);
        });
    });

    it('adds and removes filter tags', () => {
        mountView();
        cy.wait('@videos');
        cy.get('.video-query__table .el-loading-mask').should('not.exist');
        cy.get('[data-cy=add-filter]').click();
        cy.get('.video-query__table .el-loading-mask').should('exist');
        cy.get('[data-cy=filter-tag]').should('have.length', 3);
        cy.get('[data-cy=filter-tag]').last().find('[data-cy=remove-tag]').click();
        cy.get('[data-cy=filter-tag]').should('have.length', 2);
        cy.get('[data-cy=add-sort]').click();
        cy.get('[data-cy=sort-tag]').should('have.length', 3);
        cy.get('[data-cy=sort-tag]').last().find('[data-cy=remove-tag]').click();
        cy.get('[data-cy=sort-tag]').should('have.length', 2);
    });

    it('reorders sort tags and toggles direction with an icon button', () => {
        mountView();
        cy.get('[data-cy=sort-tag]').first().find('[data-cy=move-down]').click();
        cy.get('[data-cy=sort-tag]').first().find('.query-tag__index').should('have.text', '1');
        cy.get('[data-cy=sort-tag]').first().find('select').first().should('have.value', 'bv');
        cy.get('[data-cy=sort-tag]').first().find('[data-cy=sort-direction] i').should('have.class', 'pi-arrow-down');
        cy.get('[data-cy=sort-tag]').first().find('[data-cy=sort-direction]').click();
        cy.get('[data-cy=sort-tag]').first().find('[data-cy=sort-direction] i').should('have.class', 'pi-arrow-up');
        cy.get('[data-cy=sort-tag]').last().find('[data-cy=move-up]').click();
        cy.get('[data-cy=sort-tag]').first().find('select').first().should('have.value', 'timems');
    });

    it('uses multi-select for enums and interval bounds for numbers', () => {
        mountView();
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').should('have.length', 4);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option] input:checked').should('have.length', 2);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').eq(1).click();
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option] input:checked').should('have.length', 3);
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=lower-bound]').should('have.attr', 'placeholder', '-∞');
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=upper-bound]').should('have.attr', 'placeholder', '+∞');
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=lower-bracket]').should('contain.text', '[').click();
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=lower-bracket]').should('contain.text', '(');
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=upper-bracket]').should('contain.text', ')').click();
        cy.get('[data-cy=filter-tag]').eq(1).find('[data-cy=upper-bracket]').should('contain.text', ']');
    });

    it('uses icons for state and software, and code-free labels for mode', () => {
        mountView();
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').should('have.length', 4);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option] .el-icon').should('have.length', 4);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=field-select]').select('software');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option] img').should('have.length', 5);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=field-select]').select('mode');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').should('have.length', 4);
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').first().should('contain.text', 'Standard').and('not.contain.text', '00');
    });

    it('treats stnb as a derived numeric field and requires a single level', () => {
        mountView();
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=field-select]').select('stnb');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=derived]').should('exist');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=stnb-hint]').should('exist');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=lower-bound]').should('exist').and('be.disabled');
        cy.get('[data-cy=filter-tag]').first().find('[data-cy=enum-option]').should('not.exist');
    });

    it('uses changes to the shared column configuration', () => {
        mountView();
        cy.then(() => {
            videoColumnStore('mixed-players').columns.value = [presetColumn('bv')];
        });
        cy.get('[data-cy=video-list-table] table').extractTableData().should((rows) => {
            expect(rows[0]).to.deep.equal(['Bv']);
        });
    });

    it('pages with a full range button group', () => {
        mountView();
        cy.wait('@videos');
        cy.get('[data-cy=page-buttons] [data-cy=page-button]').should('have.length', 1);
        cy.get('[data-cy=page-buttons] [data-cy=page-button]').first().should('contain.text', '0-0');
        cy.get('[data-cy=page-buttons] [data-cy=page-button]').first().should('have.class', 'base-button--primary');
        cy.get('[data-cy=range-label]').should('not.exist');
        cy.get('[data-cy=page-first]').should('not.exist');
        cy.get('[data-cy=page-last]').should('not.exist');
        cy.get('.card-title [data-cy=page-size]').should('exist');
        cy.get('section[aria-label=Pagination] .card-title').should('not.contain.text', 'Pagination');
        cy.get('[data-cy=page-size]').select('50');
        cy.get('[data-cy=page-buttons] [data-cy=page-button]').should('have.length', 1);
        cy.get('[data-cy=cursor-filter]').should('not.exist');
    });
});
