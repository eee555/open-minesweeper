import MSStatSelect from './MSStatSelect.vue';

import i18n from '@/i18n';

describe('<MSStatSelect />', () => {
    it('keeps the prefix outside options, forwards control attributes and emits selected values once', () => {
        const change = cy.spy().as('change');
        cy.mount(MSStatSelect, {
            props: { label: 'x', options: ['time', 'bv'], modelValue: 'time', onChange: change },
            attrs: { id: 'x-metric', class: 'axis-control', 'aria-label': 'Horizontal metric', title: 'Choose an axis metric' },
            global: { plugins: [i18n] },
        }).then(({ wrapper }) => wrapper.setProps({
            'onUpdate:modelValue': (value: string) => {
                void wrapper.setProps({ modelValue: value });
            },
        }));

        cy.get('.ms-stat-select > span').should('have.text', 'x:');
        cy.get('select#x-metric.axis-control').should('have.attr', 'aria-label', 'Horizontal metric').and('have.attr', 'title', 'Choose an axis metric');
        cy.get('#x-metric option[value=time]').should('have.text', i18n.global.t('prop.time'));
        cy.get('#x-metric').select('bv');
        cy.get('@change').should('have.been.calledOnce').and('have.been.calledWithExactly', 'bv');

        cy.get<ComponentWrapper<typeof MSStatSelect>>('@vue').then((wrapper) => wrapper.setProps({ modelValue: 'time' }));
        cy.get('#x-metric').should('have.value', 'time');
        cy.get('@change').should('have.been.calledOnce');
    });

    it('keeps disabled controls and provides an accessible name without a visible prefix', () => {
        cy.mount(MSStatSelect, {
            props: { modelValue: 'time' },
            attrs: { disabled: true },
            global: { plugins: [i18n] },
        });
        cy.get('.ms-stat-select > span').should('not.exist');
        cy.get('select').should('be.disabled').and('have.attr', 'aria-label', 'Metric').and('have.value', 'time');
    });
});
