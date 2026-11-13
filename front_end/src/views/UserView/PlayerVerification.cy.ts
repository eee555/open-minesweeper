import type { ComponentProps } from 'vue-component-type-helpers';

import PlayerVerification from './PlayerVerification.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { VerificationStatus } from '@/services/playerVerificationService';
import { store } from '@/store';
import { pinia } from '@/store/create';

function verificationStatus(overrides: Partial<VerificationStatus> = {}): VerificationStatus {
    return {
        verified: false,
        can_submit_replays: false,
        can_verify: false,
        maintenance_active: false,
        ...overrides,
    };
}

function mountVerification(initial: VerificationStatus) {
    cy.intercept('GET', '/api/userprofile/verification/status*', { body: initial }).as('status');
    const props: ComponentProps<typeof PlayerVerification> = { userId: 42 };
    cy.then(() => {
        store.login({ id: 42, username: 'self' });
    });
    cy.mount(PlayerVerification, {
        props,
        global: {
            plugins: [i18n, pinia],
            config: { globalProperties: { $axios } },
        },
    });
    cy.wait('@status');
}

describe('<PlayerVerification />', () => {
    it('shows the current verification state and the unified access state', () => {
        mountVerification(verificationStatus());
        cy.get('[data-cy=verification-state]').should('contain.text', 'Not verified');
        cy.contains('Blocked').should('be.visible');
        cy.contains('button', 'Verify user').should('be.disabled');
        cy.get('[data-cy=verification-result]').should('not.exist');
    });

    it('syncs a newly granted verification into the site-wide login session', () => {
        mountVerification(verificationStatus({ verified: true, can_submit_replays: true, can_verify: true }));
        cy.then(() => {
            expect(store.user.verified).to.eq(true);
            expect(store.user.can_submit_replays).to.eq(true);
        });
        cy.contains('Granted').should('be.visible');
    });

    it('lets a verified user verify another user by site ID', () => {
        mountVerification(verificationStatus({ verified: true, can_submit_replays: true, can_verify: true }));
        cy.get('[data-cy=verification-state]').should('contain.text', 'Verified');
        cy.contains('Granted').should('be.visible');
        cy.get('#verification-target-id').type('9');
        cy.contains('button', 'Verify user').should('not.be.disabled');
    });

    it('disables verification during superuser maintenance', () => {
        mountVerification(verificationStatus({ verified: true, can_verify: true, maintenance_active: true }));
        cy.get('[data-cy=verification-maintenance]').should('be.visible');
        cy.get('#verification-target-id').type('9');
        cy.contains('button', 'Verify user').should('be.disabled');
    });

    it('reports the synchronous verification result without task polling', () => {
        mountVerification(verificationStatus({ verified: true, can_verify: true }));
        cy.intercept('POST', '/api/userprofile/verification/verify', {
            statusCode: 200,
            body: { target_id: 9, verified: true, edge_created: true, nodes_updated: 1 },
        }).as('verify');
        cy.get('#verification-target-id').type('9');
        cy.contains('button', 'Verify user').click();
        cy.wait('@verify');
        cy.get('[data-cy=verification-result]').should('contain.text', 'The user is now verified.');
    });
});
