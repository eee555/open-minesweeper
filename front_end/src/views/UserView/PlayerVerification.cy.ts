import type { ComponentProps } from 'vue-component-type-helpers';

import PlayerVerification from './PlayerVerification.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { VerificationStatus } from '@/services/playerVerificationService';
import { pinia } from '@/store/create';

function verificationStatus(overrides: Partial<VerificationStatus> = {}): VerificationStatus {
    return {
        verified: false,
        can_submit_replays: false,
        has_relation: false,
        request_state: 'none',
        request_parent_id: null,
        created_at: null,
        expires_at: null,
        cooldown_until: null,
        can_request: true,
        processing_task_id: null,
        ...overrides,
    };
}

function mountVerification(initial: VerificationStatus) {
    cy.intercept('GET', '/api/userprofile/verification/request*', { body: initial }).as('status');
    const props: ComponentProps<typeof PlayerVerification> = { userId: 42 };
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
        cy.contains('Send request').should('be.visible');
        cy.get('[data-cy=verification-task]').should('not.exist');
    });

    it('shows an established relation and offers detach', () => {
        mountVerification(verificationStatus({ verified: true, can_submit_replays: true, has_relation: true, request_state: 'approved', can_request: false }));
        cy.get('[data-cy=verification-state]').should('contain.text', 'Verified');
        cy.contains('Granted').should('be.visible');
        cy.contains('Detach verification').should('be.visible');
        cy.contains('Send request').parent().find('button').should('be.disabled');
    });

    it('waits for the verification task before refreshing the session', () => {
        mountVerification(verificationStatus());
        cy.intercept('GET', '/api/common/loginauto*', { user: { id: 42, username: 'self', verified: true, can_submit_replays: true }, top_anchors: {} }).as('loginAuto');
        cy.intercept('POST', '/api/userprofile/verification/requests/9/approve', { statusCode: 202, body: { task_id: 'verification-task-1', existing: false } }).as('approve');
        cy.intercept('GET', '/api/userprofile/verification/tasks/verification-task-1', {
            statusCode: 200,
            body: {
                task_id: 'verification-task-1',
                status: 'SUCCESSFUL',
                finished_at: null,
                result: { status: 'applied', operation: 'approve', target_id: 9, affected: 1, verified: true, reason: null },
                error: null,
            },
        }).as('task');
        cy.intercept('GET', '/api/userprofile/verification/request*', {
            body: verificationStatus({ verified: true, can_submit_replays: true, request_state: 'approved', has_relation: true, can_request: false }),
        }).as('statusDone');

        cy.get('#verification-applicant-id').type('9');
        cy.contains('button', 'Verify').click();
        cy.wait('@approve');
        cy.get('[data-cy=verification-task]').should('contain.text', 'queued or running');
        cy.wait('@task');
        cy.wait('@loginAuto');
        cy.wait('@statusDone');
        cy.get('[data-cy=verification-task]').should('contain.text', 'completed');
        cy.get('[data-cy=verification-state]').should('contain.text', 'Verified');
    });
});
