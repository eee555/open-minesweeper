export {};

const BACKEND = 'http://127.0.0.1:8000';
const STAFF = { id: 1, username: 'privacy-staff', password: 'privacy-password' };
const USERS = {
    initial: { id: 101, username: 'privacy-initial', password: 'privacy-password' },
    denied: { id: 102, username: 'privacy-denied', password: 'privacy-password' },
    cached: { id: 103, username: 'privacy-cached', password: 'privacy-password', realname: '缓存实名' },
    linked: { id: 104, username: 'privacy-linked', password: 'privacy-password', realname: '绑定实名' },
    existing: { id: 105, username: 'privacy-existing', password: 'privacy-password', realname: '既有实名' },
    toggle: { id: 106, username: 'privacy-toggle', password: 'privacy-password', realname: '开关测试姓名' },
};

interface Profile {
    id: number;
    realname: string;
    firstname: string;
    lastname: string;
    can_hide_realname: boolean;
    hide_realname: boolean;
}

interface ProfileUpdate {
    hide_realname: { type: 'success' | 'error' };
}

function self() {
    return cy.request<Profile>(`${BACKEND}/api/userprofile/info/0`);
}

function privacy(hide: boolean) {
    return cy.request<ProfileUpdate>({ method: 'POST', url: `${BACKEND}/api/userprofile/update_profile`, form: true, body: { hide_realname: hide } });
}

function publicNames(id: number, name: string) {
    return cy.request<Profile[]>({ url: `${BACKEND}/api/userprofile/infobulk`, qs: { ids: id } }).then(({ body }) => {
        expect(body).to.have.length(1);
        expect(body[0].realname).to.eq(name);
        expect(body[0]).not.to.have.property('has_realname');
        expect(body[0]).not.to.have.property('_realname');
        expect(body[0]).not.to.have.property('hide_realname');
        if (name === 'hidden') expect(body[0]).to.include({ firstname: 'hidden', lastname: 'hidden' });
    });
}

function staffPatch(id: number, body: object) {
    return cy.request<Profile>({ method: 'PATCH', url: `${BACKEND}/api/userprofile/admin/update/${id}`, form: true, body });
}

function editEligibility(id: number, eligible: boolean) {
    cy.login(STAFF.username, STAFF.password);
    cy.intercept('GET', `**/api/userprofile/admin/detail/${id}`).as('staffDetail');
    cy.intercept('PATCH', `**/api/userprofile/admin/update/${id}`).as('staffSave');
    cy.visit('/#/staff/userprofile');
    cy.get('.el-input-number input').clear();
    cy.get('.el-input-number input').type(String(id));
    cy.contains('button', '查询').click();
    cy.wait('@staffDetail').its('response.statusCode').should('eq', 200);
    cy.get('textarea[data-cy=staff-profile-json]').clear();
    cy.get('textarea[data-cy=staff-profile-json]').type(JSON.stringify({ can_hide_realname: eligible }), { parseSpecialCharSequences: false });
    cy.get('[data-cy=staff-save-profile]').click();
    cy.wait('@staffSave').its('response.body.can_hide_realname').should('eq', eligible);
    cy.closeElNotifications();
}

function navigate(hash: string) {
    cy.window().then((win) => {
        win.location.hash = hash;
    });
    cy.location('hash').should('eq', hash);
}

function cachedName(id: number) {
    return cy.window().then((win) => new Cypress.Promise<string>((resolve, reject) => {
        const open = win.indexedDB.open('saolei-cache');
        open.onerror = () => {
            reject(open.error);
        };
        open.onsuccess = () => {
            const db = open.result;
            const read = db.transaction('user-info').objectStore('user-info').get(id);
            read.onerror = () => {
                db.close(); reject(read.error);
            };
            read.onsuccess = () => {
                const row = read.result as { realname?: string } | undefined;
                db.close();
                resolve(row?.realname ?? '');
            };
        };
    }));
}

describe('Real name privacy against the backend', () => {
    before(() => {
        cy.flushDatabase();
        cy.registerUsers([STAFF, ...Object.values(USERS)]);
        cy.setStaff(STAFF.id);
        cy.dangerzonePost('prepare_msgames_privacy_fixture', { id: USERS.existing.id });
        for (const user of [USERS.initial, USERS.cached]) {
            cy.createVideo({ user_id: user.id, identifier: `privacy-${user.id}`, level: 'e', bv: 100, timems: 95000, state: 'c' });
        }
    });

    it('rejects unauthorized hiding without partially saving a real name', () => {
        const user = USERS.denied;
        cy.login(user.username, user.password);
        cy.visitUser(user.id, 'settings');
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
        cy.get('input[data-cy=name-realname]').type('拒绝测试姓名');
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
        cy.request({ method: 'POST', url: `${BACKEND}/api/userprofile/update_profile`, form: true, body: { realname: '拒绝测试姓名', hide_realname: true, can_hide_realname: true } }).its('body.realname.type').should('eq', 'error');
        self().its('body').should('include', { realname: '匿名', can_hide_realname: false, hide_realname: false });
    });

    it('grants through the staff page and saves a new name with hiding in one request', () => {
        const user = USERS.initial;
        editEligibility(user.id, true);
        cy.login(user.username, user.password);
        self().its('body').should('include', { can_hide_realname: true, hide_realname: false });
        cy.visitUser(user.id, 'settings');
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
        cy.get('input[data-cy=name-realname]').type('隐藏测试姓名');
        cy.get('[data-cy=real-name-section] [data-cy=hide-realname-toggle]').should('not.be.checked').check();
        cy.intercept('POST', '**/api/userprofile/update_profile').as('saveName');
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@saveName').interceptFormData((data) => {
            expect(data.realname).to.eq('隐藏测试姓名');
            expect(data.hide_realname).to.eq('true');
        });
        cy.get('[data-cy=real-name-section] [data-cy=hide-realname-toggle]').should('be.checked');
        self().its('body').should('include', { realname: '隐藏测试姓名', hide_realname: true });
        cy.get('.profile:visible').should('contain.text', `用户 #${user.id}`).and('not.contain.text', '隐藏测试姓名').and('not.contain.text', user.username);
        publicNames(user.id, 'hidden');
        cy.visitUser(user.id, 'upload');
        cy.contains('请修改为实名').should('not.exist');
        cy.get('input[type=file]').should('not.be.disabled');

        cy.clearCookies();
        cy.visitUser(user.id);
        cy.get('.profile:visible').should('contain.text', `用户 #${user.id}`).and('not.contain.text', '隐藏测试姓名');
        publicNames(user.id, 'hidden');
        cy.intercept('GET', '**/api/video/query*').as('videoQuery');
        cy.visit('/#/database/videos');
        cy.wait('@videoQuery').its('response.body.videos').should((rows: { player__id: number; player__realname: string }[]) => {
            expect(rows.find((row) => row.player__id === user.id)?.player__realname).to.eq('hidden');
        });
        cy.get(`.player-name a[href="#/player/${user.id}"]`).should('have.text', `用户 #${user.id}`).closest('.player-name').should('have.attr', 'title', `用户 #${user.id}`);
    });

    it('persists later toggles and lets an administrator revoke eligibility', () => {
        const user = USERS.toggle;
        cy.login(STAFF.username, STAFF.password);
        staffPatch(user.id, { can_hide_realname: true });
        cy.login(user.username, user.password);
        privacy(true);
        cy.visitUser(user.id, 'settings');
        cy.intercept('POST', '**/api/userprofile/update_profile').as('saveProfile');
        cy.get('[data-cy=hide-realname-toggle]').uncheck();
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@saveProfile').its('response.body.hide_realname.type').should('eq', 'success');
        publicNames(user.id, user.realname);
        cy.get('[data-cy=hide-realname-toggle]').check();
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@saveProfile').its('response.body.hide_realname.type').should('eq', 'success');
        cy.reload();
        cy.get('[data-cy=hide-realname-toggle]').should('be.checked');
        editEligibility(user.id, false);
        cy.request<Profile>(`${BACKEND}/api/userprofile/admin/detail/${user.id}`).its('body').should('include', { realname: user.realname, can_hide_realname: false, hide_realname: false });
        cy.visitUser(user.id);
        publicNames(user.id, user.realname);
        cy.login(user.username, user.password);
        cy.visitUser(user.id, 'settings');
        cy.get('[data-cy=hide-realname-toggle]').should('not.exist');
        privacy(true).its('body.hide_realname.type').should('eq', 'error');
    });

    it('invalidates the saved user at the normal cache interval and keeps hidden names after reload', () => {
        const user = USERS.cached;
        cy.login(STAFF.username, STAFF.password);
        staffPatch(user.id, { can_hide_realname: true });
        cy.login(user.username, user.password);
        cy.intercept({ method: 'GET', pathname: '/api/video/query' }).as('cachedUserVideos');
        cy.visit('/#/database/videos', {
            onBeforeLoad(win) {
                const config = JSON.parse(win.localStorage.getItem('service-config') ?? '{}') as Record<string, number>;
                win.localStorage.setItem('service-config', JSON.stringify({ ...config, userInfoUpdateInterval: 86400000, userInfoLastUpdate: Date.now() }));
            },
        });
        cy.wait('@cachedUserVideos').its('response.body.videos').should((rows: { player__id: number }[]) => {
            expect(rows.some((row) => row.player__id === user.id), 'the cached user has a visible video').to.eq(true);
        });
        cy.get(`.player-name a[href="#/player/${user.id}"]`).should('contain.text', user.username);
        cachedName(user.id).should('eq', user.realname);
        navigate(`#/player/${user.id}/settings`);
        cy.intercept('POST', '**/api/userprofile/update_profile').as('saveProfile');
        cy.intercept('GET', '**/api/userprofile/infobulk*').as('publicBatch');
        cy.get('[data-cy=hide-realname-toggle]').check();
        cy.get('[data-cy=save-profile]').click();
        cy.wait('@saveProfile').its('response.body.hide_realname.type').should('eq', 'success');
        navigate('#/database/videos');
        cy.wait('@publicBatch').its('response.statusCode').should('eq', 200);
        cy.get(`.player-name a[href="#/player/${user.id}"]`).should('have.text', `用户 #${user.id}`);
        cachedName(user.id).should('eq', 'hidden');
        cy.reload();
        cy.get(`.player-name a[href="#/player/${user.id}"]`).should('have.text', `用户 #${user.id}`);
        cachedName(user.id).should('eq', 'hidden');
    });

    it('grants only on a new MSGames verification, preserves eligibility on unlink, and does not regrant on retry', () => {
        const user = USERS.linked;
        const binding = { id: user.id, platform: 'a', identifier: '2147483000' };
        cy.login(user.username, user.password);
        cy.request({ method: 'POST', url: `${BACKEND}/api/accountlink/create/`, form: true, body: binding });
        self().its('body.can_hide_realname').should('eq', false);
        cy.login(STAFF.username, STAFF.password);
        cy.intercept('POST', '**/api/accountlink/verify/').as('verify');
        cy.visit('/#/staff/accountlink');
        cy.contains('.el-form-item__label', '用户 ID').next().find('input').clear();
        cy.contains('.el-form-item__label', '用户 ID').next().find('input').type(String(user.id));
        cy.contains('.el-form-item__label', /^平台$/).next().find('.el-select').click();
        cy.contains('.el-select-dropdown__item:visible', '国际网').click();
        cy.contains('.el-form-item__label', '平台 ID').next().find('input').type(binding.identifier);
        cy.contains('button', /^\s*绑定\s*$/).click();
        cy.wait('@verify').its('response').should('include', { statusCode: 200, body: '' });
        cy.login(user.username, user.password);
        self().its('body').should('include', { can_hide_realname: true, hide_realname: false });
        privacy(true);
        cy.request(`${BACKEND}/api/accountlink/${user.id}`).its('body.a').should('include', { name: 'MSGames Fixture', local_name: '关联姓名' });
        cy.login(STAFF.username, STAFF.password);
        staffPatch(user.id, { can_hide_realname: false });
        cy.request({ method: 'POST', url: `${BACKEND}/api/accountlink/verify/`, form: true, body: binding });
        cy.login(user.username, user.password);
        self().its('body').should('include', { can_hide_realname: false, hide_realname: false });
        cy.login(STAFF.username, STAFF.password);
        staffPatch(user.id, { can_hide_realname: true });
        cy.login(user.username, user.password);
        privacy(true);
        cy.request({ method: 'POST', url: `${BACKEND}/accountlink/delete/`, form: true, body: { platform: 'a' } });
        self().its('body').should('include', { can_hide_realname: true, hide_realname: true });
    });

    it('leaves existing MSGames users ungranted until an administrator manually grants eligibility', () => {
        const user = USERS.existing;
        cy.login(user.username, user.password);
        self().its('body').should('include', { can_hide_realname: false, hide_realname: false });
        cy.request({ method: 'POST', url: `${BACKEND}/accountlink/update/`, form: true, body: { platform: 'a' } });
        self().its('body.can_hide_realname').should('eq', false);
        editEligibility(user.id, true);
        cy.login(user.username, user.password);
        self().its('body').should('include', { can_hide_realname: true, hide_realname: false });
    });
});
