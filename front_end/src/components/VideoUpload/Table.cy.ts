import PrimeVue from 'primevue/config';
import { defineComponent, h, ref } from 'vue';

import Table from './Table.vue';
import type { UploadEntry } from './utils';

import i18n from '@/i18n';

function mountTable() {
    const data = ref<UploadEntry[]>(Array.from({ length: 27 }, (_, index) => ({
        hash: String(index), file: new File([], `video-${index}.avf`), status: index < 2 ? 'pass' : 'quota',
    })));
    const selected = ref<UploadEntry[]>([]);
    cy.mount(defineComponent({
        expose: [],
        render: () => h(Table, {
            data: data.value,
            'selected-rows': selected.value,
            'onUpdate:selected-rows': (value: UploadEntry[]) => {
                selected.value = value;
            },
        }),
    }), { global: { plugins: [i18n, PrimeVue] } });
    cy.get('tbody .checkbox-input').should('have.length', 25);
    return { data, selected };
}

function filterStatus(label: string) {
    cy.contains('th', 'Status').find('button').click();
    cy.contains('[data-cy=filter-status] .radio-button-content:visible', label).click();
}

describe('<VideoUpload Table /> selection', () => {
    it('selects across pages and clears a partial selection with Space', () => {
        const { selected } = mountTable();
        cy.get('thead .checkbox-input').parent('label').click();
        cy.wrap(selected).its('value').should('have.length', 27);
        cy.get('table .checkbox-input').shouldHaveState(Array<boolean>(26).fill(true));

        cy.get('.p-paginator-next').click();
        cy.get('tbody .checkbox-input').should('have.length', 2);
        cy.get('table .checkbox-input').shouldHaveState([true, true, true]);
        cy.get('tbody .checkbox-input').first().click();
        cy.wrap(selected).its('value').should('have.length', 26);
        cy.get('table .checkbox-input').shouldHaveState([null, false, true]);

        cy.get('thead .checkbox-input').focus();
        cy.realPress('Space');
        cy.get('table .checkbox-input').shouldHaveState([false, false, false]);
        cy.wrap(selected).its('value').should('have.length', 0);
        cy.get('thead .checkbox-input').parent('label').click();
        cy.wrap(selected).its('value').should('have.length', 27);
    });

    it('prunes filtered selections and restores an unchecked header for empty results', () => {
        const { data, selected } = mountTable();
        cy.get('thead .checkbox-input').click();
        cy.wrap(selected).its('value').should('have.length', 27);
        filterStatus('Pass');
        cy.get('table .checkbox-input').shouldHaveState([true, true, true]);
        cy.wrap(selected).its('value').should((entries: UploadEntry[]) => {
            expect(entries.map((entry) => entry.hash)).to.deep.equal(['0', '1']);
        });
        cy.get('tbody .checkbox-input').first().parent('label').click();
        cy.get('table .checkbox-input').shouldHaveState([null, false, true]);
        filterStatus('Video quota reached');
        cy.get('thead .checkbox-input').shouldHaveState([false]);
        cy.wrap(selected).its('value').should('have.length', 0);

        // No quota entries remain while the active quota filter is retained.
        cy.then(() => {
            data.value = data.value.slice(0, 2);
        });
        cy.get('tbody .checkbox-input').should('not.exist');
        cy.get('thead .checkbox-input').shouldHaveState([false]);
        cy.get('thead .checkbox-input').parent('label').click();
        cy.get('thead .checkbox-input').shouldHaveState([false]);
        cy.wrap(selected).its('value').should('have.length', 0);
    });
});
