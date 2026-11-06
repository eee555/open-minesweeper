import { defineComponent, h, nextTick, ref } from 'vue';

import MSStatSelect from './MSStatSelect.vue';

import i18n from '@/i18n';

describe('<MSStatSelect />', () => {
    it('keeps the prefix outside options, forwards control attributes and emits selected values once', () => {
        const change = cy.spy().as('change');
        const metric = ref('time');
        cy.mount(defineComponent({
            expose: [],
            render: () => h(MSStatSelect, {
                label: 'x',
                options: ['time', 'bv'],
                modelValue: metric.value,
                onChange: change,
                'onUpdate:modelValue': (value: string) => {
                    metric.value = value;
                },
                id: 'x-metric',
                class: 'axis-control',
                'aria-label': 'Horizontal metric',
                title: 'Choose an axis metric',
            }),
        }), { global: { plugins: [i18n] } });

        cy.get('.ms-stat-select > span').should('have.text', 'x:');
        cy.get('select#x-metric.axis-control').should('have.attr', 'aria-label', 'Horizontal metric').and('have.attr', 'title', 'Choose an axis metric');
        cy.get('#x-metric option[value=time]').should('have.text', i18n.global.t('prop.time'));
        cy.get('#x-metric').select('bv');
        cy.then(() => nextTick());
        cy.get('#x-metric').should('have.value', 'bv');
        cy.get('@change').should('have.been.calledOnce').and('have.been.calledWithExactly', 'bv');

        cy.then(() => {
            expect(metric.value).to.equal('bv');
            metric.value = 'time';
            return nextTick();
        });
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
