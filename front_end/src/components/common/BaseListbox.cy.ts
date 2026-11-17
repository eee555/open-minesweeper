import { defineComponent, h } from 'vue';

import BaseListbox from './BaseListbox.vue';

const options = [
    { value: 'a', label: 'Alpha' },
    { value: 'b', label: 'Beta' },
    { value: 'c', label: 'Gamma' },
];

describe('<BaseListbox />', () => {
    it('renders one native row per option, marks the selected row and emits the chosen value', () => {
        const update = cy.spy().as('update');
        cy.mount(BaseListbox, {
            props: { modelValue: 'b', options, ariaLabel: 'Choices', 'onUpdate:modelValue': update },
        });
        cy.get('.base-listbox__table').should('exist');
        cy.get('.base-listbox__row').should('have.length', 3);
        cy.get('.base-listbox__row--selected').should('have.length', 1).and('contain.text', 'Beta');
        cy.get('.base-listbox').should('have.attr', 'role', 'radiogroup').and('have.attr', 'aria-label', 'Choices');
        cy.get('input[type=radio]').should('have.length', 3).and('have.prop', 'checked', false);
        cy.get('input[data-listbox-value=b]').should('be.checked');

        cy.get('.base-listbox__row').last().find('label').click();
        cy.get('@update').should('have.been.calledWith', 'c');
    });

    it('keeps native keyboard activation and honours disabled rows', () => {
        const update = cy.spy().as('update');
        cy.mount(BaseListbox, {
            props: {
                modelValue: 'a',
                options: [...options, { value: 'd', label: 'Disabled', disabled: true }],
                'onUpdate:modelValue': update,
            },
        });
        cy.get('.base-listbox__row--disabled').should('have.length', 1);
        cy.get('.base-listbox__row--disabled input').should('be.disabled');
        cy.get('.base-listbox__row').last().find('label').click();
        cy.get('@update').should('not.have.been.called');

        cy.get('input[data-listbox-value=b]').focus();
        cy.realPress('Space');
        cy.get('@update').should('have.been.calledWith', 'b');
    });

    it('emits the whole selection for a multiple listbox', () => {
        const update = cy.spy().as('update');
        cy.mount(BaseListbox, {
            props: {
                modelValue: [1],
                options: [{ value: 1, label: 'One' }, { value: 2, label: 'Two' }],
                multiple: true,
                'onUpdate:modelValue': update,
            },
        });
        cy.get('.base-listbox').should('have.attr', 'role', 'group');
        cy.get('input[type=checkbox]').should('have.length', 2);
        cy.get('input[data-listbox-value=1]').should('be.checked');
        cy.get('.base-listbox__row').last().find('label').click();
        cy.get('@update').should('have.been.calledWith', [1, 2]);
    });

    it('shows an empty row only when emptyText is supplied', () => {
        cy.mount(BaseListbox, { props: { modelValue: null, options: [], emptyText: 'No options' } });
        cy.get('.base-listbox__empty').should('have.text', 'No options');
    });

    it('lets the table shrink to its content instead of filling the container', () => {
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', { style: { width: '24rem' } }, [
                h(BaseListbox, { modelValue: null, options: [{ value: 's', label: 'A' }], 'data-cy': 'short' }),
                h(BaseListbox, { modelValue: null, options: [{ value: 'l', label: 'A much longer option label' }], 'data-cy': 'long' }),
            ]),
        }));
        cy.get('[data-cy=short] table').invoke('outerWidth').then((shortWidth) => {
            cy.get('[data-cy=long] table').should(($table) => {
                const longWidth = Number($table.outerWidth());
                expect(longWidth).to.be.greaterThan(Number(shortWidth));
                expect(longWidth).to.be.lessThan(384);
            });
        });
    });
});
