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
    url: 'https://www.bilibili.com/video/BV1xx411c7mD/',
    embed_url: null,
    hot_now: 0,
};

describe('<SubmitMediaDialog />', () => {
    it('posts only the URL and free-text language', () => {
        cy.intercept('POST', '/api/media/submit', (request) => {
            request.reply(submitted);
        }).as('submit');
        const onSubmitted = cy.spy().as('submittedSpy');
        cy.mount(SubmitMediaDialog, {
            props: { onSubmitted },
            global: { plugins: [i18n], config: { globalProperties: { $axios } } },
        });
        cy.get('form input[type=url]').type('https://www.bilibili.com/video/BV1xx411c7mD/');
        cy.get('form input[type=text]').type('zh-cn');
        cy.get('form button[type=submit]').click();
        cy.wait('@submit').its('request.body').should('deep.equal', {
            url: 'https://www.bilibili.com/video/BV1xx411c7mD/',
            language: 'zh-cn',
        });
        cy.get('@submittedSpy').should('have.been.calledOnce');
    });
});
