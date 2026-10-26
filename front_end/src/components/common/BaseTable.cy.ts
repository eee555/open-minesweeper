/* eslint-disable vue/one-component-per-file -- Each test mounts its own render-only fixture. */
import { defineComponent, h, nextTick, ref } from 'vue';

import BaseTable from './BaseTable.vue';

describe('<BaseTable />', () => {
    it('renders grouped native headers and switches between rows and an empty state', () => {
        const empty = ref(false);
        cy.mount(defineComponent({
            expose: [],
            render: () => h(BaseTable, { empty: empty.value, columnCount: 3, emptyText: 'No records', 'data-cy': 'display-table' }, {
                head: () => [
                    h('tr', [h('th', { rowspan: 2, scope: 'col' }, 'Player'), h('th', { colspan: 2, scope: 'colgroup' }, 'Results')]),
                    h('tr', [h('th', { scope: 'col' }, 'Time'), h('th', { scope: 'col' }, 'Bvs')]),
                ],
                default: () => h('tr', [h('th', { scope: 'row' }, 'Player A'), h('td', '1.234'), h('td', '4.567')]),
            }),
        }));

        cy.get('[data-cy=display-table] thead tr').should('have.length', 2);
        cy.contains('th', 'Results').should('have.attr', 'colspan', '2').and('have.attr', 'scope', 'colgroup');
        cy.get('[data-cy=display-table] tbody').extractTableData().should('deep.equal', [['Player A', '1.234', '4.567']]);
        cy.then(() => {
            empty.value = true;
            return nextTick();
        });
        cy.get('[data-cy=display-table] tbody td').should('have.length', 1).and('have.attr', 'colspan', '3').and('have.text', 'No records');
        cy.contains('tbody', 'Player A').should('not.exist');
        cy.then(() => {
            empty.value = false;
            return nextTick();
        });
        cy.get('[data-cy=display-table] tbody').extractTableData().should('deep.equal', [['Player A', '1.234', '4.567']]);
    });

    it('keeps cell links and actions usable inside a narrow scroll container', () => {
        const clicked = cy.spy().as('cellAction');
        cy.mount(defineComponent({
            expose: [],
            render: () => h(BaseTable, { tableStyle: { width: '600px' }, style: 'width: 200px;', 'data-cy': 'display-table' }, {
                default: () => h('tr', [
                    h('td', h('a', { href: '#/player/42' }, 'Player')),
                    h('td', h('button', { type: 'button', onClick: clicked }, 'Preview')),
                ]),
            }),
        }));

        cy.get('[data-cy=display-table]').should(($container) => {
            expect($container[0].scrollWidth).to.be.greaterThan($container[0].clientWidth);
        });
        cy.contains('a', 'Player').should('have.attr', 'href', '#/player/42');
        cy.contains('button', 'Preview').click();
        cy.get('@cellAction').should('have.been.calledOnce');
    });
});
