import CardMsgames from './CardMsgames.vue';
import { mockMSGamesResponse, mountAccountLink } from './testUtils';

import { AccountMSGames } from '@/utils/accountlinks';

describe('<CardMsgames />', () => {
    it('renders Authoritative Minesweeper account details', () => {
        mountAccountLink(CardMsgames, {
            id: '202',
            verified: true,
            info: new AccountMSGames(mockMSGamesResponse()),
        });

        cy.contains('Authoritative Minesweeper #202');
        cy.contains('AM Player');
        cy.contains('Local AM');
        cy.contains('China');
        cy.contains('Example region');
        cy.contains('Example mouse');
        cy.contains('2024-01-01 08:00:00');
    });

    it('renders the unverified state', () => {
        mountAccountLink(CardMsgames, {
            id: '202',
            verified: false,
        });

        cy.contains('This account has not been verified.');
        cy.contains('AM Player').should('not.exist');
    });

    it('keeps a verified account visible while remote profile details are unavailable', () => {
        mountAccountLink(CardMsgames, {
            id: '202',
            verified: true,
            info: new AccountMSGames({ ...mockMSGamesResponse(), name: '', local_name: '' }),
        });
        cy.contains('Account linked. Profile details are unavailable; try refreshing later.');
        cy.contains('This account has not been verified.').should('not.exist');
    });
});
