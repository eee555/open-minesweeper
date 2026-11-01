import CardAdd from './CardAdd.vue';
import { mockSaoleiResponse, mountAccountLink, resetAccountLinkStore } from './testUtils';

import { AccountLinkPlatform, AccountLinks } from '@/utils/accountlinks';

describe('<CardAdd />', () => {
    beforeEach(() => {
        resetAccountLinkStore();
    });

    it('disables already linked platforms and validates numeric identifiers', () => {
        const accountlinks = new AccountLinks({
            summary: [
                { id: 1, platform: AccountLinkPlatform.Saolei, identifier: '101', userprofile: 1, verified: true },
            ],
            B: null,
            m: null,
            c: mockSaoleiResponse(),
            a: null,
            w: null,
            q: null,
        });

        mountAccountLink(CardAdd, { accountlinks });

        cy.get('.el-button').first().click();
        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Saolei.wang').should('have.class', 'is-disabled');
        cy.contains('.el-select-dropdown__item', 'Bilibili').click();

        cy.contains('button', 'Confirm').should('be.disabled');
        cy.get('.el-input input').type('abc');
        cy.contains('button', 'Confirm').should('be.disabled');
        cy.get('.el-input input').clear();
        cy.get('.el-input input').type('404');
        cy.contains('button', 'Confirm').should('not.be.disabled');
    });

    it('clears the form when the dialog is closed', () => {
        mountAccountLink(CardAdd);

        cy.get('.el-button').first().click();
        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Bilibili').click();
        cy.get('.el-input input').type('404');
        cy.contains('button', 'Cancel').click();
        cy.get('.el-dialog').should('not.be.visible');

        cy.get('.el-button').first().click();
        cy.get('.el-input input').should('have.value', '');
    });

    it('renders the account link guide for each platform', () => {
        mountAccountLink(CardAdd);

        cy.get('.el-button').first().click();
        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Saolei.wang').click();
        cy.contains('How to locate the ID');
        cy.contains('Go to your profile page on');

        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Authoritative Minesweeper').click();
        cy.contains('Find yourself on the');
        cy.contains('The number at the end of the url is your ID');

        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Minesweeper.Online').click();
        cy.contains('Go to your profile page on');

        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Tencent QQ').click();
        cy.contains('The QQ number is accessible from site moderators');

        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Discord').click();
        cy.contains('Copy User ID');
        cy.contains('contact a moderator for verification');

        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Bilibili').click();
        cy.contains('space.bilibili.com');
        cy.contains('Privacy notice');
        cy.contains('Linking Bilibili may allow others');
    });

    it('submits a Discord snowflake unchanged for moderator verification', () => {
        mountAccountLink(CardAdd, { onAddLink: cy.spy().as('addLink') });
        cy.get('.el-button').first().click();
        cy.get('.el-select').click();
        cy.contains('.el-select-dropdown__item', 'Discord').click();
        cy.contains('Enable Developer Mode');
        for (const id of ['player', '0', '01', '1'.repeat(21)]) {
            cy.get('.el-input input').clear();
            cy.get('.el-input input').type(id);
            cy.contains('button', 'Confirm').should('be.disabled');
        }
        cy.get('.el-input input').clear();
        cy.get('.el-input input').type('18446744073709551615');
        cy.contains('button', 'Confirm').should('be.enabled').click();
        cy.get('@addLink').should('have.been.calledOnceWith', 'd', '18446744073709551615');
    });
});
