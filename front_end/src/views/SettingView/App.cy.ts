import { nextTick } from 'vue';

import Settings from './App.vue';

import { videoColumnStore, videoDescriptionStore } from '@/components/VideoList/columnStore';
import { presetColumn, presetExpressionColumn, videoColumnPreview } from '@/components/VideoList/presets';
import $axios from '@/http';
import i18n from '@/i18n';
import { formatBytes } from '@/utils/strings';

function mountSettings() {
    cy.mockPlayerNameFallback();
    cy.intercept('GET', '**/api/video/preview*', { statusCode: 404 }).as('videoPreview');
    cy.mount(Settings, { global: {
        plugins: [i18n],
        stubs: { Appearance: true, PlayerBadgeSettings: true, Visualization: true, MiniGame: true, IDB: true },
        config: { globalProperties: { $axios } },
    } });
}

describe('<Settings /> replay configuration', () => {
    const player = videoColumnStore('fixed-player');
    const mixed = videoColumnStore('mixed-players');
    const originalPlayer = player.columns.value;
    const originalMixed = mixed.columns.value;
    const originalDescription = videoDescriptionStore.columns.value;

    afterEach(() => {
        cy.get<ComponentWrapper<typeof Settings>>('@vue').then(async (wrapper) => {
            wrapper.unmount();
            player.columns.value = originalPlayer;
            mixed.columns.value = originalMixed;
            videoDescriptionStore.columns.value = originalDescription;
            await nextTick();
        });
    });

    it('edits the two shared table groups and tooltip independently in settings cards', () => {
        let addedColumnId: string | undefined;
        player.columns.value = [presetColumn('time')];
        mixed.columns.value = [presetColumn('bv')];
        videoDescriptionStore.columns.value = [{ ...presetColumn('time'), width: 1 }];
        mountSettings();
        cy.get('[data-cy=video-columns-editor]').should('have.length', 3);
        cy.get('[data-cy=fixed-player-columns-preview] table').extractTableData().should('deep.equal', [['Time'], [(videoColumnPreview.timems / 1000).toFixed(3)]]);
        cy.get('[data-cy=mixed-players-columns-preview] table').extractTableData().should('deep.equal', [['Bv'], [String(videoColumnPreview.bv)]]);
        cy.get('[data-cy=fixed-player-columns-preview] tbody tr').should('not.have.attr', 'tabindex');
        cy.get('[data-cy=fixed-player-columns-preview] tbody td').click();
        cy.get('[data-cy=fixed-player-columns-settings]').within(() => {
            cy.get('h2.card-title').should('contain.text', 'Player profiles');
            cy.get('[data-cy=column-width]').should('not.exist');
            cy.get('[data-cy=column-add]').click();
            cy.then(() => {
                const [, column] = player.columns.value;
                if ('id' in column) addedColumnId = column.id;
            });
            cy.get('[data-cy=column-preset]').last().select('bvs');
            cy.get('[data-cy=column-insert]').eq(1).click();
            cy.get('[data-cy=column-item]').should('have.length', 3);
            cy.get('[data-cy=column-key]').eq(1).invoke('val', 'Time').trigger('input');
            cy.get('[role=alert]').should('be.visible');
            cy.then(() => {
                expect(player.columns.value[1]).to.have.property('key', 'custom1');
            });
            cy.get('[data-cy=column-delete]').eq(1).click();
            cy.get('[role=alert]').should('not.exist');
        });
        cy.get('[data-cy=fixed-player-columns-preview] table').extractTableData().should('deep.equal', [['Time', 'Bvs'], [(videoColumnPreview.timems / 1000).toFixed(3), (videoColumnPreview.bv / (videoColumnPreview.timems / 1000)).toFixed(3)]]);
        cy.get('[data-cy=mixed-players-columns-settings]').within(() => {
            cy.get('h2.card-title').should('contain.text', 'Database search');
            cy.get('[data-cy=column-item]').should('have.length', 1);
            cy.get('[data-cy=column-type]').select('bytes');
            cy.get('[data-cy=column-expr]').clear();
            cy.get('[data-cy=column-expr]').type('file_size');
        });
        cy.get('[data-cy=mixed-players-columns-preview] table').extractTableData().should('deep.equal', [['Bv'], [formatBytes(videoColumnPreview.file_size)]]);
        cy.get('[data-cy=mixed-players-columns-settings]').within(() => {
            cy.get('[data-cy=column-delete]').click();
        });
        cy.get('[data-cy=video-tooltip-settings]').within(() => {
            cy.get('h2.card-title').should('have.text', 'Replay tooltip');
            cy.get('[data-cy=column-item]').should('have.length', 1);
            cy.get('[data-cy=column-width]').select('3');
            cy.get('[data-cy=column-type]').select('bytes');
            cy.get('[data-cy=column-expr]').clear();
            cy.get('[data-cy=column-expr]').type('file_size');
        });
        cy.get('[data-cy=video-tooltip-preview] .description-width-3 dd').should('have.text', formatBytes(videoColumnPreview.file_size));
        cy.get('@videoPreview.all').should('have.length', 0);
        cy.then(() => {
            expect(addedColumnId).to.be.a('string').and.not.equal('bvs');
            expect(player.columns.value).to.deep.equal([presetColumn('time'), { ...presetExpressionColumn('bvs'), id: addedColumnId }]);
            expect(mixed.columns.value).to.deep.equal([]);
            expect(videoDescriptionStore.columns.value).to.deep.equal([{ ...presetColumn('time'), type: 'bytes', expr: 'file_size', width: 3 }]);
        });
    });

    it('limits string presets to tooltip expressions and renders their raw values', () => {
        player.columns.value = [presetColumn('time')];
        mixed.columns.value = [presetColumn('bv')];
        videoDescriptionStore.columns.value = [{ ...presetColumn('time'), width: 1 }];
        mountSettings();
        const stringFields = ['state', 'software', 'level', 'mode', 'rowKey'] as const;
        for (const scope of ['fixed-player', 'mixed-players']) {
            cy.get<HTMLOptionElement>(`[data-cy=${scope}-columns-settings] [data-cy=column-preset] option`).then((options) => {
                const values = [...options].map((option) => option.value);
                for (const field of stringFields) expect(values).not.to.include(field);
            });
        }
        for (const field of stringFields) {
            cy.get('[data-cy=video-tooltip-settings] [data-cy=column-preset]').select(field);
            cy.get('[data-cy=video-tooltip-settings] [data-cy=column-type]').should('have.value', 'data');
            cy.get('[data-cy=video-tooltip-preview] .description-width-1 dd').should('have.text', String(videoColumnPreview[field]));
        }
        cy.get('[data-cy=fixed-player-columns-settings] [data-cy=column-preset]').select('ongoing_tournament');
        cy.get('[data-cy=fixed-player-columns-settings] [data-cy=column-type]').should('have.value', 'bool');
        cy.get('[data-cy=fixed-player-columns-preview] [role=img][aria-label=false]').should('exist');
    });
});
