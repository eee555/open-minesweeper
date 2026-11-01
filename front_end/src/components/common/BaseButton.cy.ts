import { defineComponent, h, ref } from 'vue';

import BaseButton from './BaseButton.vue';
import BaseButtonBack from './BaseButtonBack.vue';
import BaseButtonCancel from './BaseButtonCancel.vue';
import BaseButtonConfirm from './BaseButtonConfirm.vue';
import BaseTextButton from './BaseTextButton.vue';

import i18n from '@/i18n';

describe('Native base buttons', () => {
    it('only submits a form when explicitly configured and preserves click modifiers', () => {
        const clicked = cy.spy().as('clicked');
        const submitted = cy.stub().as('submitted');
        cy.mount(defineComponent({
            expose: [],
            render: () => h('form', {
                onSubmit: (event: SubmitEvent) => {
                    event.preventDefault();
                    submitted();
                },
            }, [
                h(BaseButton, { type: 'primary', onClick: clicked }, () => 'Action'),
                h(BaseButton, { nativeType: 'submit' }, () => 'Submit'),
                h(BaseButton, {
                    nativeType: 'submit',
                    onClick: (event: MouseEvent) => {
                        event.preventDefault();
                    },
                }, () => 'Prevent submit'),
            ]),
        }));

        cy.contains('button', /^Action$/).should('have.attr', 'type', 'button').click();
        cy.get('@clicked').should('have.been.calledOnce');
        cy.get('@submitted').should('not.have.been.called');
        cy.contains('button', /^Submit$/).click();
        cy.get('@submitted').should('have.been.calledOnce');
        cy.contains('button', 'Prevent submit').click();
        cy.get('@submitted').should('have.been.calledOnce');
    });

    it('forwards confirmation state and attributes, blocks repeat clicks and allows retrying', () => {
        const loading = ref(false);
        const disabled = ref(false);
        const clicked = cy.spy().as('clicked');
        cy.mount(defineComponent({
            expose: [],
            render: () => h(BaseButtonConfirm, {
                loading: loading.value,
                disabled: disabled.value,
                class: 'custom-confirm',
                style: 'width: 150px;',
                'data-cy': 'confirm',
                'aria-label': 'Confirm action',
                onClick: () => {
                    clicked();
                    loading.value = true;
                },
            }),
        }), { global: { plugins: [i18n] } });

        cy.get('[data-cy=confirm]').should('contain', 'Confirm').and('have.class', 'custom-confirm').
            and('have.attr', 'aria-label', 'Confirm action');
        cy.get('[data-cy=confirm]').should('have.css', 'width', '150px').click();
        cy.get('@clicked').should('have.been.calledOnce');
        cy.get('[data-cy=confirm]').should('be.disabled').and('have.attr', 'aria-busy', 'true');
        cy.get('[data-cy=confirm] .pi-spinner').should('be.visible');
        // A dispatched event also exercises the guard beyond native disabled handling.
        cy.get('[data-cy=confirm]').trigger('click', { force: true });
        cy.get('@clicked').should('have.been.calledOnce');
        cy.then(() => {
            loading.value = false;
            disabled.value = true;
        });
        cy.get('[data-cy=confirm]').should('be.disabled').and('not.have.attr', 'aria-busy');
        cy.get('[data-cy=confirm]').trigger('click', { force: true });
        cy.get('@clicked').should('have.been.calledOnce');
        cy.then(() => {
            disabled.value = false;
        });
        cy.get('[data-cy=confirm]').should('be.enabled').click();
        cy.get('@clicked').should('have.been.calledTwice');
    });

    it('supports keyboard activation and forwards wheel events on text buttons', () => {
        const clicked = cy.spy().as('clicked');
        const wheel = cy.spy().as('wheel');
        cy.mount(defineComponent({
            expose: [],
            render: () => h(BaseTextButton, {
                size: 'small', 'data-cy': 'text-action', onClick: clicked, onWheel: wheel,
            }, () => 'Zoom'),
        }));

        cy.get('[data-cy=text-action]').should('match', 'button').focus();
        cy.realPress('Enter');
        cy.get('@clicked').should('have.been.calledOnce');
        cy.realPress('Space');
        cy.get('@clicked').should('have.been.calledTwice');
        cy.get('[data-cy=text-action]').trigger('wheel', { deltaY: 100 });
        cy.get('@wheel').should('have.been.calledOnce');
    });

    it('keeps cancel and back labels, icons and click handlers', () => {
        const cancel = cy.spy().as('cancel');
        const back = cy.spy().as('back');
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [
                h(BaseButtonCancel, { onClick: cancel }),
                h(BaseButtonBack, { onClick: back }),
            ]),
        }), { global: { plugins: [i18n] } });

        cy.contains('button', 'Cancel').click();
        cy.get('@cancel').should('have.been.calledOnce');
        cy.contains('button', 'Back').find('.pi-angle-left').should('be.visible');
        cy.contains('button', 'Back').click();
        cy.get('@back').should('have.been.calledOnce');
    });
});
