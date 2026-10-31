import EditProfile from './EditProfile.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { UserProfile } from '@/utils/userprofile';

function mountOptions(props?: { user?: UserProfile; expTimeMs?: number; qualificationStatus?: 'idle' | 'loading' | 'ready' | 'error' }) {
    return {
        props: props,
        global: {
            plugins: [i18n, pinia],
            config: {
                globalProperties: {
                    $axios,
                },
            },
        },
    };
}

function findLocalNameInput() {
    return cy.contains('Local Name').parent().next().find('input');
}

function findFirstNameInput() {
    return cy.contains('International Name').parent().next().find('input').eq(0);
}

function findLastNameInput() {
    return cy.contains('International Name').parent().next().find('input').eq(1);
}

function findSignatureInput() {
    return cy.contains('Signature').parent().next().find('textarea');
}

function mockUpdateResponse(body: unknown) {
    cy.intercept('POST', '/api/userprofile/update_profile', {
        statusCode: 200,
        body: body,
    }).as('updateProfile');
}

describe('EditProfile', () => {
    beforeEach(() => {
        cy.clock(new Date('2025-01-01T00:00:00Z'));
    });

    it('offers an unchecked hide option only with eligibility and a valid new real name', () => {
        cy.mount(EditProfile, mountOptions({ user: new UserProfile({ can_hide_realname: true }) }));
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
        findLocalNameInput().type('Real Name');
        cy.get('[data-cy=real-name-section] [data-cy=hide-realname-toggle]').should('not.be.checked');
        findLocalNameInput().clear();
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
    });

    for (const hide of [true, false]) {
        it(`saves hide_realname=${String(hide)} with the profile Save button`, () => {
            const user = new UserProfile({ realname: 'Real Name', can_hide_realname: true, hide_realname: !hide });
            mockUpdateResponse({ realname: null, firstname: null, lastname: null, signature: null, hide_realname: { type: 'success' } });
            cy.mount(EditProfile, mountOptions({ user }));
            if (hide) cy.get('[data-cy=real-name-section] [data-cy=hide-realname-toggle]').check();
            else cy.get('[data-cy=real-name-section] [data-cy=hide-realname-toggle]').uncheck();
            cy.get('[data-cy=save-profile]').click();
            cy.wait('@updateProfile').interceptFormData((data) => {
                expect(data.hide_realname).to.eq(String(hide));
                expect(data.realname).to.be.undefined;
                expect(data.firstname).to.be.undefined;
                expect(data.lastname).to.be.undefined;
                expect(data.signature).to.be.undefined;
            });
            cy.then(() => {
                expect(user.hide_realname).to.eq(hide);
            });
        });
    }

    it('keeps the saved hiding state on failure and resets the draft with Cancel', () => {
        const user = new UserProfile({ realname: 'Real Name', can_hide_realname: true });
        mockUpdateResponse({ realname: null, firstname: null, lastname: null, signature: null, hide_realname: { type: 'error', object: 'privacy', category: 'not_authorized' } });
        cy.mount(EditProfile, mountOptions({ user }));
        cy.get('[data-cy=hide-realname-toggle]').check();
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@updateProfile');
        cy.contains('You are not authorized to hide your real name');
        cy.then(() => {
            expect(user.hide_realname).to.eq(false);
        });
        cy.get('[data-cy=hide-realname-toggle]').should('not.be.checked');
        cy.contains('button', 'Cancel').click();
        cy.get('[data-cy=hide-realname-toggle]').should('not.be.checked');
    });

    it('restores the saved privacy checkbox when the save is rate limited', () => {
        const user = new UserProfile({ realname: 'Real Name', can_hide_realname: true });
        cy.intercept('POST', '/api/userprofile/update_profile', { statusCode: 429 }).as('updateProfile');
        cy.mount(EditProfile, mountOptions({ user }));
        cy.get('[data-cy=hide-realname-toggle]').check();
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@updateProfile').its('response.statusCode').should('eq', 429);
        cy.get('[data-cy=hide-realname-toggle]').should('not.be.checked').and('not.be.disabled');
        cy.then(() => {
            expect(user.hide_realname).to.eq(false);
        });
    });

    it('rejects reserved names before posting', () => {
        cy.intercept('POST', '/api/userprofile/update_profile').as('save');
        cy.mount(EditProfile, mountOptions({ user: new UserProfile() }));
        findLocalNameInput().type('hidden');
        cy.get('[data-cy=save-profile]').click();
        cy.contains('A name cannot be the reserved value hidden');
        cy.get('@save.all').should('have.length', 0);
    });

    describe('Local name', () => {
        it('Disabled', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ realname: 'realname' }),
            }));

            findLocalNameInput().should('be.disabled');
        });

        it('Update', () => {
            const user = new UserProfile({
                firstname: 'firstname',
                lastname: 'lastname',
                signature: 'signature',
            });

            mockUpdateResponse({
                realname: { type: 'success' },
                signature: null,
                firstname: null,
                lastname: null,
            });

            cy.mount(EditProfile, mountOptions({
                user: user,
            }));

            findLocalNameInput().type('realname');
            cy.get('button').contains('Save').click();

            cy.wait('@updateProfile').interceptFormData((formData) => {
                expect(formData.realname).to.equal('realname');
                expect(formData.signature).to.be.undefined;
                expect(formData.firstname).to.be.undefined;
                expect(formData.lastname).to.be.undefined;
            });

            cy.then(() => {
                expect(user.realname).to.equal('realname');
            });
        });
    });

    describe('International name', () => {
        it('First name - disabled', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ firstname: 'firstname' }),
            }));

            findFirstNameInput().should('be.disabled');
        });

        it('First name - update', () => {
            const user = new UserProfile({
                realname: 'realname',
                lastname: 'lastname',
                signature: 'signature',
            });

            mockUpdateResponse({
                realname: null,
                signature: null,
                firstname: { type: 'success' },
                lastname: null,
            });

            cy.mount(EditProfile, mountOptions({
                user: user,
            }));

            findFirstNameInput().type('firstname');
            cy.get('button').contains('Save').click();

            cy.wait('@updateProfile').interceptFormData((formData) => {
                expect(formData.firstname).to.equal('firstname');
                expect(formData.realname).to.be.undefined;
                expect(formData.signature).to.be.undefined;
                expect(formData.lastname).to.be.undefined;
            });

            cy.then(() => {
                expect(user.firstname).to.equal('firstname');
            });
        });

        it('Last name - disabled', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ lastname: 'lastname' }),
            }));

            findLastNameInput().should('be.disabled');
        });

        it('Last name - update', () => {
            const user = new UserProfile({
                realname: 'realname',
                firstname: 'firstname',
                signature: 'signature',
            });

            mockUpdateResponse({
                realname: null,
                signature: null,
                firstname: null,
                lastname: { type: 'success' },
            });

            cy.mount(EditProfile, mountOptions({
                user: user,
            }));

            findLastNameInput().type('lastname');
            cy.get('button').contains('Save').click();

            cy.wait('@updateProfile').interceptFormData((formData) => {
                expect(formData.lastname).to.equal('lastname');
                expect(formData.realname).to.be.undefined;
                expect(formData.signature).to.be.undefined;
                expect(formData.firstname).to.be.undefined;
            });

            cy.then(() => {
                expect(user.lastname).to.equal('lastname');
            });
        });
    });

    describe('Signature', () => {
        it('Disabled - no budget', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ left_signature_n: 0 }),
                expTimeMs: 30000,
            }));

            findSignatureInput().should('be.disabled');
            cy.contains('You gain one chance to modify your signature each month. You have no chance remaining. Next available on: 2025-02-01 08:00:00');
        });

        it('Disabled - exp sup 200', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ left_signature_n: 1 }),
                expTimeMs: 999999,
            }));

            findSignatureInput().should('be.disabled');
            cy.contains('Achieve expert sub200 to change signature');
        });

        it('Update', () => {
            const user = new UserProfile({
                realname: 'realname',
                firstname: 'firstname',
                lastname: 'lastname',
                signature: 'signature',
                left_signature_n: 1,
            });

            mockUpdateResponse({
                realname: null,
                firstname: null,
                lastname: null,
                signature: { type: 'success' },
            });

            cy.mount(EditProfile, mountOptions({
                user: user,
                expTimeMs: 30000,
            }));

            findSignatureInput().clear();
            findSignatureInput().type('Updated signature');
            cy.get('button').contains('Save').click();

            cy.wait('@updateProfile').interceptFormData((formData) => {
                expect(formData.signature).to.equal('Updated signature');
                expect(formData.realname).to.be.undefined;
                expect(formData.firstname).to.be.undefined;
                expect(formData.lastname).to.be.undefined;
            });

            cy.then(() => {
                expect(user.signature).to.equal('Updated signature');
            });
        });

        it('Error - censorship.unknown', () => {
            mockUpdateResponse({
                realname: null,
                firstname: null,
                lastname: null,
                signature: {
                    type: 'error',
                    object: 'censorship',
                    category: 'unknown',
                },
            });

            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ left_signature_n: 1 }),
                expTimeMs: 30000,
            }));

            findSignatureInput().type('censorship.unknown');
            cy.get('button').contains('Save').click();

            cy.contains('Unknown error occurred in censorship. Please contact a moderator');
        });

        it('Error - censorship.illegal', () => {
            mockUpdateResponse({
                realname: null,
                firstname: null,
                lastname: null,
                signature: {
                    type: 'error',
                    object: 'censorship',
                    category: 'illegal',
                },
            });

            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ left_signature_n: 1 }),
                expTimeMs: 30000,
            }));

            findSignatureInput().type('censorship.illegal');
            cy.get('button').contains('Save').click();

            cy.contains('The content is blocked by censorship. Please change the text or contact a moderator for manual review');
        });
    });

    describe('Buttons', () => {
        it('Cancel', () => {
            cy.mount(EditProfile, mountOptions({
                user: new UserProfile({ signature: 'Original signature', left_signature_n: 1 }),
                expTimeMs: 30000,
            }));

            findSignatureInput().clear();
            findSignatureInput().type('Unsaved signature');
            cy.get('button').contains('Cancel').click();
            findSignatureInput().should('have.value', 'Original signature');
        });

        it('Save - nothing changed', () => {
            cy.intercept('POST', '/api/userprofile/update_profile', () => {
                throw new Error('Unexpected API call');
            }).as('updateProfile');

            cy.mount(EditProfile, mountOptions({
                user: new UserProfile(),
            }));

            cy.get('button').contains('Save').click();
            cy.get('@updateProfile.all').should('have.length', 0);
        });
    });
});
