import InputNumber from './InputNumber.vue';

function expectModelChange(index: number, value?: number) {
    if (value === undefined) {
        cy.get('@vue').then((wrapper: ComponentWrapper<typeof InputNumber>) => {
            expect(wrapper.emitted('update:modelValue')?.[index]).to.equal(undefined);
        });
    } else {
        cy.get('@vue').then((wrapper: ComponentWrapper<typeof InputNumber>) => {
            expect(wrapper.emitted('update:modelValue')?.[index]).to.deep.equal([value]);
        });
    }
}

function mountInputNumber(modelValue = 5, props: Record<string, unknown> = {}) {
    cy.mount(InputNumber, {
        props: {
            modelValue,
            class: 'custom-input',
            style: 'field-sizing: content;',
            ...props,
        },
    });
}

describe('<InputNumber />', () => {
    it('keeps fractional input pending in integer mode and rounds it when committed', () => {
        mountInputNumber(5, { min: 1, max: 100, integer: true });
        cy.get('input').invoke('val', '7.5').trigger('input');
        expectModelChange(0);
        cy.get('input').trigger('blur');
        cy.get('input').should('have.value', '8');
        expectModelChange(0, 8);
    });

    it('continues accepting fractional values by default', () => {
        mountInputNumber(5, { min: 1, max: 10, step: '0.1' });
        cy.get('input').invoke('val', '7.5').trigger('input');
        expectModelChange(0, 7.5);
    });

    it('renders a number input and forwards classes/styles', () => {
        mountInputNumber(5, { min: 1, max: 10, title: 'number setting' });

        cy.get('input').should('have.attr', 'type', 'number');
        cy.get('input').should('have.attr', 'min', '1');
        cy.get('input').should('have.attr', 'max', '10');
        cy.get('input').should('have.attr', 'title', 'number setting');
        cy.get('input').should('have.class', 'base-input-number');
        cy.get('input').should('have.class', 'text');
        cy.get('input').should('have.class', 'text-small');
        cy.get('input').should('have.class', 'custom-input');
        cy.get('input').should('have.css', 'field-sizing', 'content');
    });

    it('emit at the correct time', () => {
        mountInputNumber(5, { min: 5, max: 100 });

        // invalid input: too small
        cy.get('input').clear();
        cy.get('input').type('2');
        cy.get('input').should('have.value', '2');
        expectModelChange(0);

        // valid input: update value
        cy.get('input').type('0');
        cy.get('input').should('have.value', '20');
        expectModelChange(0, 20);

        // exit at valid input: don't update value
        cy.get('input').blur();
        expectModelChange(1);

        // invalid input: too large
        cy.get('input').type('0');
        cy.get('input').should('have.value', '200');
        expectModelChange(1);

        // exit at large input: update value
        cy.get('input').blur();
        cy.get('input').should('have.value', '100');
        expectModelChange(1, 100);
    });

    it('clamps empty input back to the current model value on commit', () => {
        mountInputNumber(5, { min: 1, max: 10 });

        cy.get('input').clear();
        cy.get('input').blur();

        cy.get('input').should('have.value', '5');
    });

    it('reflects modelValue prop updates from the parent', () => {
        mountInputNumber(5, { min: 1, max: 10 });

        cy.get('@vue').then((wrapper: ComponentWrapper<typeof InputNumber>) => {
            return wrapper.setProps({ modelValue: 8 });
        });

        cy.get('input').should('have.value', '8');
    });
});
