import BilibiliPanel from './BilibiliPanel.vue';
import MsgamesPanel from './MsgamesPanel.vue';
import PrivatePanel from './PrivatePanel.vue';
import SaoleiPanel from './SaoleiPanel.vue';
import WoMPanel from './WoMPanel.vue';

import { mockBilibiliResponse, mockMSGamesResponse, mockWoMResponse, mountAccountLink, resetAccountLinkStore } from '@/components/accountlinks/testUtils';
import { store } from '@/store';
import { AccountBilibili, AccountMSGames, AccountWoM } from '@/utils/accountlinks';

describe('linked account profile panels', () => {
    beforeEach(() => {
        resetAccountLinkStore();
    });

    it('renders Bilibili public profile fields', () => {
        mountAccountLink(BilibiliPanel, { verified: true, info: new AccountBilibili(mockBilibiliResponse()) });
        for (const text of ['Bili Player', 'Official Miner', 'Keep mining', '33']) cy.contains(text).should('be.visible');
    });

    it('renders the international profile and its joined date', () => {
        mountAccountLink(MsgamesPanel, { verified: true, info: new AccountMSGames(mockMSGamesResponse()) });
        for (const text of ['AM Player', 'Local AM', 'China', 'Example region', 'Example mouse', '2024-01-01 08:00:00']) cy.contains(text).should('be.visible');
    });

    it('keeps the international account verified when remote profile details are unavailable', () => {
        mountAccountLink(MsgamesPanel, { verified: true, info: new AccountMSGames(mockMSGamesResponse({ name: '', local_name: '' })) });
        cy.contains('Account linked. Profile details are unavailable; try refreshing later.').should('be.visible');
        cy.contains('This account has not been verified.').should('not.exist');
    });

    it('renders all WoM record and lifetime-statistics groups', () => {
        mountAccountLink(WoMPanel, { verified: true, info: new AccountWoM(mockWoMResponse()) });
        for (const text of ['12.000 | 45.000 | 99.000', '1.23 | 2.34 | 3.45', '88 | 77 | 66', '1.282 | 16.720 | 48.877', '00:09:42 | 00:43:11 | 03:51:28']) cy.contains(text).should('be.visible');
        for (const [label, value] of [['Games', '111645'], ['NF Wins', '16207'], ['Lifetime Minecoins Earned', '2000'], ['Lifetime Arena Coins Earned', '0'], ['Total Play Time', '02:00:00']]) {
            cy.contains('.description-item', label).should('contain', value);
        }
    });

    it('renders missing WoM no-guess records and the default endurance duration', () => {
        mountAccountLink(WoMPanel, { verified: true, info: new AccountWoM(mockWoMResponse({ b_ng_t_ms: null, i_ng_t_ms: null, e_ng_t_ms: null, b_endurance_ms: 86400000, i_endurance_ms: 86400000, e_endurance_ms: 86400000 })) });
        cy.contains('.description-item', 'NG Time (B/I/E)').should('contain', '- | - | -');
        cy.contains('.description-item', 'Endurance Time (B/I/E)').should('contain', '24:00:00 | 24:00:00 | 24:00:00');
    });

    it('shows a readable WoM parse error without requesting an account refresh', () => {
        const refresh = cy.spy().as('refresh');
        cy.intercept('POST', '**/api/accountlink/update/', { body: { type: 'error', object: 'import', category: 'indexerror' } }).as('updateAccountLink');
        mountAccountLink(WoMPanel, { verified: true, owner: true, info: new AccountWoM(mockWoMResponse()), onRefresh: refresh });
        cy.contains('button', 'Synchronize').click();
        cy.wait('@updateAccountLink').its('request.body').should('equal', 'platform=w');
        cy.contains('Update failed: The third-party page structure changed, so data extraction failed').should('be.visible');
        cy.get('@refresh').should('not.have.been.called');
    });

    it('offers the MSGames import queue to a moderator on a memorial account', () => {
        resetAccountLinkStore(2, 1);
        store.user.is_staff = true;
        store.player.is_memorial = true;
        mountAccountLink(MsgamesPanel, { verified: true, info: new AccountMSGames(mockMSGamesResponse({ parent: 1 })) });
        cy.contains('button', 'Videos and import').should('be.visible');
    });

    it('hides the MSGames import queue from visitors', () => {
        resetAccountLinkStore(2, 1);
        mountAccountLink(MsgamesPanel, { verified: true, info: new AccountMSGames(mockMSGamesResponse({ parent: 1 })) });
        cy.contains('button', 'Videos and import').should('not.exist');
    });

    for (const [name, component] of [['Bilibili', BilibiliPanel], ['MSGames', MsgamesPanel], ['WoM', WoMPanel], ['Saolei', SaoleiPanel], ['Private', PrivatePanel]] as const) {
        it(`shows the ${name} unverified notice without account details or sync controls`, () => {
            mountAccountLink(component, { verified: false });
            cy.contains('This account has not been verified.').should('be.visible');
            cy.get('.descriptions, button, img').should('not.exist');
        });
    }

    it('shows a verified private link without offering authorization actions', () => {
        mountAccountLink(PrivatePanel, { verified: true });
        cy.contains('Private link, visible only to you and site moderators.').should('be.visible');
        cy.contains('Verified').should('be.visible');
        cy.contains('This account has not been verified.').should('not.exist');
        cy.get('button, img').should('not.exist');
    });
});
