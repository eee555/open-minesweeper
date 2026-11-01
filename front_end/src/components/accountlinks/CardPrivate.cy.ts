import CardPrivate from './CardPrivate.vue';
import { mountAccountLink, resetAccountLinkStore } from './testUtils';

describe('<CardPrivate />', () => {
    beforeEach(() => {
        resetAccountLinkStore();
    });

    for (const [platform, label, id] of [['d', 'Discord', '18446744073709551615'], ['q', 'Tencent QQ', '12345678']]) {
        it(`shows a private pending ${label} identity without authorization controls`, () => {
            mountAccountLink(CardPrivate, { platform, id });
            cy.contains(`${label} #${id}`);
            cy.contains('Private link, visible only to you and site moderators.');
            cy.contains('This account has not been verified.');
            cy.get('button, img').should('not.exist');
        });

        it(`shows verified ${label} identity`, () => {
            mountAccountLink(CardPrivate, { platform, id, verified: true });
            cy.contains(`${label} #${id}`);
            cy.contains('This account has not been verified.').should('not.exist');
            cy.contains('Verified');
        });
    }
});
