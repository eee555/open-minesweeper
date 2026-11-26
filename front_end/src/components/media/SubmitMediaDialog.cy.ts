import SubmitMediaDialog from './SubmitMediaDialog.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const submitted = {
    id: 7,
    title: '',
    language: 'zh-cn',
    created_at: '2026-01-01T00:00:00Z',
    submitted_at: '2026-01-02T00:00:00Z',
    format: 'B_v',
    status: 'pending',
    rejected_at: null,
    reject_reason: '',
    refunded_likes: 0,
    likes: 0,
    hot_value: 0,
    hot_value_updated_at: '2026-01-01T00:00:00Z',
    metadata_pending: true,
    user_id: 42,
    rejected_by: null,
    suffix: 'BV1xx411c7mD',
    hot_now: 0,
};

describe('<SubmitMediaDialog />', () => {
    it('changes platform defaults and preserves an explicit language choice', () => {
        cy.mount(SubmitMediaDialog, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('[data-cy=submit-language]').should('contain.text', '简体中文');
        cy.get('[data-cy=submit-format]').select('g_r');
        cy.get('[data-cy=submit-language]').should('contain.text', 'English').click();
        cy.get('.el-select-dropdown:visible').contains('.el-select-dropdown__item', 'Español').click();
        cy.get('[data-cy=submit-format]').select('c_p');
        cy.get('[data-cy=submit-language]').should('contain.text', 'Español');
    });

    it('submits a custom language', () => {
        cy.intercept('POST', '/api/media/submit', { body: { ...submitted, language: 'Klingon' } }).as('customSubmit');
        cy.mount(SubmitMediaDialog, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('[data-cy=submit-suffix]').type('BV1xx411c7mD');
        cy.get('[data-cy=submit-language] input').type('Klingon{enter}');
        cy.get('form button[type=submit]').click();
        cy.wait('@customSubmit').its('request.body.language').should('equal', 'Klingon');
    });

    it('offers GitHub repositories with a locator and no degraded-submission promise', () => {
        cy.intercept('POST', '/api/media/submit', { body: { ...submitted, format: 'g_r', suffix: '1296269', metadata_pending: false } }).as('githubSubmit');
        cy.mount(SubmitMediaDialog, { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
        cy.get('[data-cy=submit-format]').select('g_r');
        cy.get('[data-cy=submit-suffix]').should('have.attr', 'placeholder', 'OWNER/REPO').type('owner/project');
        cy.contains('Only your public, non-fork personal repositories are accepted').should('exist');
        cy.get('form button[type=submit]').click();
        cy.wait('@githubSubmit').its('request.body').should('deep.equal', { format: 'g_r', suffix: 'owner/project', language: 'en' });
    });

    it('posts the selected format, suffix and free-text language', () => {
        cy.intercept('POST', '/api/media/submit', (request) => {
            request.reply(submitted);
        }).as('submit');
        const onSubmitted = cy.spy().as('submittedSpy');
        cy.mount(SubmitMediaDialog, {
            props: { onSubmitted },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('form [data-cy=submit-format]').should('have.value', 'B_v');
        cy.get('form [data-cy=submit-suffix]').type('BV1xx411c7mD');
        cy.get('form [data-cy=submit-language]').should('contain.text', '简体中文');
        cy.get('form button[type=submit]').click();
        cy.wait('@submit').its('request.body').should('deep.equal', {
            format: 'B_v',
            suffix: 'BV1xx411c7mD',
            language: 'zh-cn',
        });
        cy.get('@submittedSpy').should('have.been.calledOnce');
    });
});
