import { defineComponent, h, ref } from 'vue';
import type { ComponentProps } from 'vue-component-type-helpers';

import BaseFileInput from './BaseFileInput.vue';

import i18n from '@/i18n';

function mountFileInput(props: () => ComponentProps<typeof BaseFileInput> = () => ({})) {
    cy.mount(defineComponent({
        expose: [],
        render: () => h(BaseFileInput, props()),
    }), { global: { plugins: [i18n] } });
}

describe('<BaseFileInput />', () => {
    it('opens the picker with Enter, Space and a click on the empty area', () => {
        mountFileInput();
        cy.get('input[type=file]').then(($input) => {
            cy.stub($input[0] as HTMLInputElement, 'click').as('pick');
        });
        cy.get('button').should('have.attr', 'type', 'button').focus();
        cy.realPress('Enter');
        cy.get('@pick').should('have.been.calledOnce');
        cy.realPress('Space');
        cy.get('@pick').should('have.been.calledTwice');
        cy.get('.base-file-input').click('topLeft');
        cy.get('@pick').should('have.been.calledThrice');
    });

    it('emits multiple selected files and accepts the same file again', () => {
        const onAdd = cy.spy().as('add');
        mountFileInput(() => ({ accept: '.avf,.evf', onAdd }));
        const first = { contents: Cypress.Buffer.from('first'), fileName: 'first.avf' };
        const second = { contents: Cypress.Buffer.from('second'), fileName: 'second.evf' };
        cy.get('input[type=file]').should('have.attr', 'accept', '.avf,.evf').and('have.attr', 'multiple');
        cy.get('input[type=file]').selectFile([first, second], { force: true });
        cy.get('input[type=file]').should('have.value', '');
        cy.get('@add').should('have.been.calledOnce');
        cy.get('@add').its('firstCall.args.0').then((files) => {
            expect((files as File[]).map((file) => file.name)).to.deep.equal(['first.avf', 'second.evf']);
        });
        cy.get('input[type=file]').selectFile(first, { force: true });
        cy.get('input[type=file]').should('have.value', '');
        cy.get('@add').should('have.been.calledTwice');
    });

    it('accepts drops and blocks both picker and drop events while disabled', () => {
        const disabled = ref(false);
        const onAdd = cy.spy().as('add');
        mountFileInput(() => ({ disabled: disabled.value, onAdd }));
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(new File(['video'], 'video.avf'));
        cy.get('.base-file-input').trigger('dragover');
        cy.get('.base-file-input').should('have.class', 'base-file-input--dragover');
        cy.get('.base-file-input').trigger('drop', { dataTransfer });
        cy.get('.base-file-input').should('not.have.class', 'base-file-input--dragover');
        cy.get('@add').should('have.been.calledOnce');
        cy.then(() => {
            disabled.value = true;
        });
        cy.get('input[type=file]').should('be.disabled').then(($input) => {
            cy.stub($input[0] as HTMLInputElement, 'click').as('pick');
        });
        cy.get('button').should('be.disabled');
        cy.get('.base-file-input').click('topLeft');
        cy.get('.base-file-input').trigger('dragover');
        cy.get('.base-file-input').trigger('drop', { dataTransfer });
        cy.get('@pick').should('not.have.been.called');
        cy.get('input[type=file]').selectFile({ contents: Cypress.Buffer.from('video'), fileName: 'video.avf' }, { force: true });
        cy.get('@add').should('have.been.calledOnce');
    });
});
