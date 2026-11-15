import { defineComponent, h, ref } from 'vue';

import Table from './Table.vue';
import type { UploadEntry } from './utils';

import i18n from '@/i18n';
import { VideoAbstract } from '@/utils/videoabstract';

const TABLE = '[data-cy=upload-table] table';
const PAGINATION = '[data-cy=upload-pagination]';

function mountTable(firstRowStat?: VideoAbstract) {
    const data = ref<UploadEntry[]>(Array.from({ length: 27 }, (_, index) => {
        const entry: UploadEntry = {
            hash: String(index), file: new File([], `video-${index}.avf`), status: index < 2 ? 'pass' : 'quota',
        };
        if (index === 0 && firstRowStat !== undefined) entry.stat = firstRowStat;
        return entry;
    }));
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
    }), { global: { plugins: [i18n] } });
    cy.get('tbody .checkbox-input').should('have.length', 25);
    return { data, selected };
}

function filterStatus(label: string) {
    cy.get('[data-cy=filter-status-trigger]').click();
    cy.get(`[data-cy=filter-status] input[aria-label="${label}"]`).parent().click();
    cy.shouldBeAbsentOrHidden('[data-cy=filter-status]');
}

describe('<VideoUpload Table /> icon buttons', () => {
    it('inherits the header font and color for sort and filter icons', () => {
        mountTable();
        cy.get(`${TABLE} thead th`).eq(3).then(($th) => {
            const headerFontSize = $th.css('font-size');
            const headerColor = $th.css('color');
            for (const trigger of ['[data-cy=sort-end-time]', '[data-cy=filter-status-trigger]']) {
                cy.get(`${TABLE} thead ${trigger}`).should('have.css', 'font-size', headerFontSize).and('have.css', 'color', headerColor);
                cy.get(`${TABLE} thead ${trigger} .pi`).should('have.css', 'font-size', headerFontSize).and('have.css', 'color', headerColor);
            }
        });
    });

    it('inherits the same table font and the row color for the expand icon', () => {
        mountTable();
        cy.get(`${TABLE} thead [data-cy=sort-end-time]`).then(($sort) => {
            const headerFontSize = $sort.css('font-size');
            cy.get(`${TABLE} tbody td`).first().then(($td) => {
                const cellColor = $td.css('color');
                cy.get(`${TABLE} tbody [data-cy=expand-row]`).first().should('have.css', 'font-size', headerFontSize).and('have.css', 'color', cellColor);
                cy.get(`${TABLE} tbody [data-cy=expand-row] .pi`).first().should('have.css', 'font-size', headerFontSize).and('have.css', 'color', cellColor);
            });
        });
    });
});

describe('<VideoUpload Table /> selection', () => {
    it('selects across pages and clears a partial selection with Space', () => {
        const { selected } = mountTable();
        cy.get('thead .checkbox-input').parent('label').click();
        cy.wrap(selected).its('value').should('have.length', 27);
        cy.get('table .checkbox-input').shouldHaveState(Array<boolean>(26).fill(true));

        cy.get(`${PAGINATION} [data-cy=next]`).click();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '26-27 / 27');
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

    it('changes page size, jumps to an arbitrary start index and resets the start after filtering', () => {
        mountTable();
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-25 / 27');
        cy.get(`${PAGINATION} [data-cy=page-size]`).select('5');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-5 / 27');
        cy.get('tbody .checkbox-input').should('have.length', 5);
        cy.get(`${PAGINATION} [data-cy=jump]`).clear();
        cy.get(`${PAGINATION} [data-cy=jump]`).type('26{enter}');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '26-27 / 27');
        cy.get('tbody .checkbox-input').should('have.length', 2);
        filterStatus('Pass');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-2 / 2');
        cy.get('tbody .checkbox-input').should('have.length', 2);
    });

    it('keeps a single active sort column and toggles its direction', () => {
        mountTable();
        cy.get('[data-cy=sort-time]').closest('th').should('have.attr', 'aria-sort', 'none');
        cy.get('[data-cy=sort-time]').click();
        cy.get('[data-cy=sort-time]').closest('th').should('have.attr', 'aria-sort', 'ascending');
        cy.get('[data-cy=sort-time]').click();
        cy.get('[data-cy=sort-time]').closest('th').should('have.attr', 'aria-sort', 'descending');
        cy.get('[data-cy=sort-bv]').click();
        cy.get('[data-cy=sort-bv]').closest('th').should('have.attr', 'aria-sort', 'ascending');
        cy.get('[data-cy=sort-time]').closest('th').should('have.attr', 'aria-sort', 'none');
    });

    it('keeps filter icons in their headers and renders software, pLuck and thrp', () => {
        mountTable(new VideoAbstract({ level: 'b', mode: '00', timems: 1000, bv: 10, software: 'a', cl: 10, ce: 20, pluck: 1.25 }));
        cy.get('[data-cy=filter-status-trigger]').closest('th').should('contain.text', 'Status');
        cy.get('[data-cy=filter-level-trigger]').closest('th').should('contain.text', 'Level');
        cy.get('[data-cy=filter-mode-trigger]').closest('th').should('contain.text', 'Mode');
        cy.get(`${TABLE} thead th`).should('have.length', 12);
        cy.get(`${TABLE} colgroup col`).should('have.length', 2);

        cy.get(`${TABLE} tbody tr`).first().find('td').should(($cells) => {
            expect($cells.eq(10).text().trim()).to.equal('1.250');
            expect($cells.eq(11).text().trim()).to.equal('0.500');
            expect($cells.eq(9).text().trim()).to.equal('Avf');
        });
    });

    it('expands one row into a description list and collapses it again', () => {
        mountTable();
        cy.get(`${TABLE} tbody tr`).should('have.length', 25);
        cy.get('[data-cy=expand-row]').first().click();
        cy.get('[data-cy=upload-expansion]').should('have.length', 1).and('contain.text', 'video-0.avf');
        cy.get('[data-cy=expand-row]').first().click();
        cy.get('[data-cy=upload-expansion]').should('not.exist');
    });

    it('clears a filter and keeps one empty row when nothing matches', () => {
        const { data } = mountTable();
        filterStatus('Pass');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-2 / 2');
        cy.get('[data-cy=filter-status-trigger]').click();
        cy.get('[data-cy=filter-status-clear]').click();
        cy.shouldBeAbsentOrHidden('[data-cy=filter-status]');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '1-25 / 27');

        cy.then(() => {
            data.value = data.value.slice(0, 2);
        });
        filterStatus('Video quota reached');
        cy.get(`${TABLE} tbody tr`).should('have.length', 1);
        cy.get(`${TABLE} tbody .checkbox-input`).should('not.exist');
        cy.get(TABLE).should('contain.text', 'No matching videos');
        cy.get(`${PAGINATION} [data-cy=report]`).should('have.text', '0-0 / 0');
        cy.get(`${PAGINATION} [data-cy=next]`).should('be.disabled');
    });
});
