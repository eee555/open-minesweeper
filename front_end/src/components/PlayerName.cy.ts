import type { StaticResponse } from 'cypress/types/net-stubbing';
import { h } from 'vue';

import PlayerName from './PlayerName.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { getDatabase, USER_INFO_STORE_NAME } from '@/services/database';
import { syncMedalsAfterUpload } from '@/services/medalService';
import { setMedalOverride } from '@/services/staffMedalService';
import { serviceConfig } from '@/services/store';
import { local } from '@/store/local';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

const user = {
    id: 42,
    username: 'alice',
    realname: 'Alice',
    firstname: 'Alicia',
    lastname: 'Mines',
};

function mountPlayerName(userId: number, options: { interactive?: boolean; onParentClick?: () => void } = {}) {
    const router = hashRouter({ initialPath: '/' });
    cy.wrap(router.isReady()).then(() => {
        cy.mount({
            render: () => h('div', { onClick: options.onParentClick }, [
                h(PlayerName, { userId, interactive: options.interactive }),
            ]),
        }, {
            global: {
                plugins: [i18n, router],
                config: { globalProperties: { $axios } },
            },
        });
    });
}

function mockUserInfo(response: StaticResponse = { body: [user] }) {
    cy.intercept('GET', `/api/userprofile/infobulk?ids=${user.id}`, response).as('fetchUser');
}

function expectName(name: string, title?: string) {
    cy.get('.player-name').should(($name) => {
        expect($name.text().trim()).to.eq(name);
        if (title !== undefined) expect($name.attr('title')).to.eq(title);
    });
}

describe('PlayerName', () => {
    installHashHistoryCleanup();
    const originalSettings = { ...local.value };

    beforeEach(() => {
        cy.then(async () => {
            const db = await getDatabase();
            await db.clear(USER_INFO_STORE_NAME);
            Object.assign(local.value, { playerNameShowAvatar: false, playerNameFormat: 'name1', playerName1: 'username', playerName2: 'realname', nameFormat: 'first-last' });
        });
        cy.intercept('GET', '/api/userprofile/avatar/**', {
            statusCode: 404,
        });
        cy.intercept('GET', '**/api/medal/players/state*', { body: [] }).as('playerMedalState');
    });

    afterEach(() => {
        Object.assign(local.value, originalSettings);
    });

    it('shows the fallback name when server error', () => {
        cy.on('uncaught:exception', (error) => {
            expect(error.message).to.include('Request failed with status code 500');
            return false;
        });
        mockUserInfo({ statusCode: 500, body: {} });
        mountPlayerName(user.id);

        cy.wait('@fetchUser');
        cy.contains(`User#${user.id}`);
    });

    it('shows the fallback name when no user info', () => {
        mockUserInfo({ body: [] });
        mountPlayerName(user.id);

        cy.wait('@fetchUser');
        cy.contains(`User#${user.id}`);
    });

    it('uses the fallback fixture even when the player name was previously cached', () => {
        cy.then(async () => {
            const db = await getDatabase();
            await db.put(USER_INFO_STORE_NAME, user);
        });
        cy.mockPlayerNameFallback();
        mountPlayerName(user.id);

        cy.wait('@playerNameFallbackUserInfoBulk');
        expectName(`User#${user.id}`);
    });

    it('shows the username without an avatar by default, with all names in a multiline title', () => {
        mockUserInfo();
        mountPlayerName(user.id);

        expectName(user.username, 'alice#42\nAlice (Alicia Mines)');
        cy.get('.player-name img').should('not.exist');
    });

    it('hides the whole name and title regardless of name preferences', () => {
        mockUserInfo({ body: [{ ...user, realname: 'hidden', firstname: 'hidden', lastname: 'hidden' }] });
        mountPlayerName(user.id);
        expectName('User #42', 'User #42');
        cy.then(() => {
            local.value.playerNameFormat = 'name1 (name2)';
            local.value.playerName1 = 'international';
            local.value.playerName2 = 'username';
            local.value.nameFormat = 'last-first';
        });
        expectName('User #42', 'User #42');
        cy.get('.player-name a').should('have.attr', 'href', '#/player/42');
    });

    it('reacts to both name selections and the existing English-name order without refetching', () => {
        mockUserInfo();
        mountPlayerName(user.id);
        cy.contains('a', user.username);
        cy.then(() => {
            local.value.playerNameFormat = 'name1 (name2)';
            local.value.playerName1 = 'realname';
            local.value.playerName2 = 'international';
        });
        expectName('Alice (Alicia Mines)');
        cy.then(() => {
            local.value.nameFormat = 'last-first';
            local.value.playerName1 = 'international';
            local.value.playerName2 = 'username';
        });
        expectName('Mines, Alicia (alice)', 'alice#42\nAlice (Mines, Alicia)');
        cy.then(() => {
            local.value.playerNameFormat = 'name1';
        });
        expectName('Mines, Alicia');
        cy.get('@fetchUser.all').should('have.length', 1);
    });

    it('falls back to the username for a missing primary name and omits an empty secondary name', () => {
        mockUserInfo({ body: [{ ...user, realname: '匿名', firstname: '', lastname: '' }] });
        cy.then(() => {
            local.value.playerNameFormat = 'name1 (name2)';
            local.value.playerName1 = 'realname';
            local.value.playerName2 = 'international';
        });
        mountPlayerName(user.id);
        expectName(user.username, 'alice#42\n-- (--)');
    });

    it('hides avatars for noninteractive names without making an avatar request', () => {
        mockUserInfo();
        cy.intercept('GET', '/api/userprofile/avatar/**', { statusCode: 404 }).as('avatar');
        cy.then(() => {
            local.value.playerNameShowAvatar = false;
        });
        mountPlayerName(user.id, { interactive: false });
        expectName(user.username, 'alice#42\nAlice (Alicia Mines)');
        cy.get('.player-name img').should('not.exist');
        cy.get('.player-name a').should('not.exist');
        cy.get('@avatar.all').should('have.length', 0);
        cy.then(() => {
            local.value.playerNameShowAvatar = true;
        });
        cy.get('.player-name img').should('be.visible');
    });

    it('does not fetch user info when userId is zero', () => {
        cy.clock();
        cy.intercept('GET', '**/api/userprofile/infobulk?**').as('fetchUser');

        mountPlayerName(0);

        cy.contains('Anonymous');
        cy.tick(serviceConfig.value.userInfoBatchDelay + 50);
        cy.get('@fetchUser.all').should('have.length', 0);
        cy.get('@playerMedalState.all').should('have.length', 0);
        cy.clock().then((clock) => {
            clock.restore();
        });
    });

    it('links directly to the player page', () => {
        mockUserInfo();
        mountPlayerName(user.id);

        cy.contains('a', user.username).should('have.attr', 'href', `#/player/${user.id}`);
    });

    it('lets clicks bubble without opening a popover when not interactive', () => {
        cy.mockPlayerNameFallback();
        const onParentClick = cy.stub().as('parentClick');
        mountPlayerName(101, { interactive: false,
            onParentClick: () => {
                onParentClick();
            } });

        cy.contains('User#101').click();

        cy.get('@parentClick').should('have.been.calledOnce');
        cy.get('[id^=tippy-]').should('not.exist');
        cy.get('[data-cy-root] a').should('not.exist');
    });

    it('shows a granted medal icon when the name is hovered', () => {
        const player = { ...user, id: 770 + Cypress.currentRetry };
        cy.intercept('GET', '**/api/userprofile/infobulk*', (request) => {
            const ids = new URL(request.url).searchParams.get('ids') ?? '';
            request.reply({ body: ids.split(',').includes(String(player.id)) ? [player] : [] });
        }).as('fetchMedalUser');
        cy.intercept('GET', '**/api/medal/players/state*', {
            body: [{ user_id: player.id, grants: [{ code: 'ability.time.e', stage: 30000, timestamp: 1761123456, scope: '', tournament: null, rank: null }] }],
        }).as('grantedMedalState');
        cy.intercept('GET', /\/api\/medal\/players\/\d+/, { statusCode: 500, body: {} }).as('medalDetail');
        mountPlayerName(player.id);

        cy.get('@grantedMedalState.all').should('have.length', 0);
        cy.contains('a', player.username).realHover();
        cy.wait('@grantedMedalState').its('request.url').should((url) => {
            const ids = new URL(url).searchParams.get('ids') ?? '';
            expect(ids.split(',')).to.include(String(player.id));
        });
        cy.get('[id^=tippy-] img').should('be.visible').and('have.attr', 'src').and('include', 'breakthrough.webp');
        cy.get('[id^=tippy-] img').realHover();
        cy.get('[id^=tippy-]').should('contain', 'Expert Breakthrough · Sub30').and('contain', 'Expert best time reached 30s.');
        cy.get('@medalDetail.all').should('have.length', 0);
    });

    it('removes a revoked shareholder medal from an already mounted name tooltip', () => {
        const playerId = 142 + Cypress.currentRetry;
        let revoked = false;
        cy.intercept('GET', '**/api/userprofile/infobulk*', { body: [{ ...user, id: playerId }] });
        cy.intercept('GET', '**/api/medal/players/state*', (request) => {
            request.reply({ body: [{ user_id: playerId, grants: revoked ? [] : [{ code: 'shareholder.origin', stage: 1000, timestamp: 1, scope: '', tournament: null, rank: null }] }] });
        }).as('shareholderState');
        cy.intercept('POST', '**/api/medal/staff/overrides', (request) => {
            revoked = true;
            request.reply({ body: { grant_id: 49, mode: 'revoke', enqueued: false } });
        }).as('revokeShareholder');
        mountPlayerName(playerId);
        cy.get('.player-name').realHover();
        cy.wait('@shareholderState');
        cy.get('.player-name-medals:visible .medal-hit').should('have.length', 1);
        cy.then(() => setMedalOverride({ user_id: playerId, code: 'shareholder.origin', scope_key: '', mode: 'revoke', reason: 'Revoke test' }));
        cy.wait('@revokeShareholder');
        cy.wait('@shareholderState');
        cy.get('.player-name-medals:visible').should('not.exist');
    });

    it('refreshes an already mounted name tooltip when upload processing finishes', () => {
        const playerId = 790 + Cypress.currentRetry;
        cy.mockPlayerNameFallback();
        let stage = 4000;
        cy.intercept('GET', '**/api/medal/players/state*', {
            body: [{ user_id: playerId, grants: [{ code: 'ability.time.b', stage, timestamp: 1, scope: '', tournament: null, rank: null }] }],
        }).as('beforeUploadState');
        cy.intercept('GET', '**/api/medal/refresh-status', { body: { user_id: playerId, pending: false } }).as('refreshStatus');
        mountPlayerName(playerId);
        cy.get('@beforeUploadState.all').should('have.length', 0);
        cy.get('.player-name').realHover();
        cy.wait('@beforeUploadState');
        cy.get('[id^=tippy-]').should('contain', '4');
        cy.then(() => {
            stage = 3000;
        });
        cy.intercept('GET', '**/api/medal/players/state*', (request) => {
            request.reply({ body: [{ user_id: playerId, grants: [{ code: 'ability.time.b', stage, timestamp: 1, scope: '', tournament: null, rank: null }] }] });
        }).as('afterUploadState');
        cy.then(() => {
            syncMedalsAfterUpload();
        });
        cy.wait('@refreshStatus');
        cy.wait('@afterUploadState');
        cy.get('[id^=tippy-]').should('contain', '3').and('not.contain', '4');
    });
});
