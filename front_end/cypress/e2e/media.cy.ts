import type { MediaItem } from '../../src/services/mediaService';

const BACKEND = 'http://127.0.0.1:8000';

const STAFF = {
    id: 1,
    username: 'staff',
    email: 'staff@email.com',
    password: 'staffPassword',
} as const;
const USER = {
    id: 2,
    username: 'user',
    email: 'user@email.com',
    password: 'userPassword',
} as const;
const NO_LINK = {
    id: 3,
    username: 'nolink',
    email: 'nolink@email.com',
    password: 'nolinkPassword',
} as const;

// BV1eB4y1F7Ao 的真实作者 mid；外站拉取失败时投稿降级，此时只要求存在任一已验证绑定。
const BVID = 'BV1eB4y1F7Ao';
const WORK_URL = `https://www.bilibili.com/video/${BVID}/`;
const AUTHOR_MID = '349467963';
// 外站拉取成功时由 B 站实时返回；视频改标题需同步此常量。
const EXPECTED_TITLE = '【扫雷比赛】巨佬群殴！史上最燃的扫雷大赛！第八届金羊杯总结视频';

function openSubmitDialog() {
    cy.get('[data-cy=open-submit]').click();
    cy.get('.el-dialog:visible form.media-submit-form').should('be.visible');
}

function fillAndSubmit() {
    cy.get('.el-dialog:visible form.media-submit-form [data-cy=submit-suffix]').type(BVID);
    cy.get('.el-dialog:visible form.media-submit-form [data-cy=submit-language]').type('zh-cn');
    cy.get('.el-dialog:visible form.media-submit-form button[type=submit]').click();
}

function createVerifiedBilibiliLink() {
    cy.login(USER.username, USER.password);
    cy.request({
        method: 'POST',
        url: `${BACKEND}/api/accountlink/create/`,
        form: true,
        body: { platform: 'B', identifier: AUTHOR_MID },
    }).its('status').should('eq', 200);

    cy.login(STAFF.username, STAFF.password);
    cy.adminRequest({
        method: 'POST',
        url: `${BACKEND}/api/accountlink/verify/`,
        form: true,
        body: { id: USER.id, platform: 'B', identifier: AUTHOR_MID },
    }).its('status').should('eq', 200);
}

describe('Media submission', () => {
    beforeEach(() => {
        cy.mockPlayerNameFallback();
    });

    it('Before All', () => {
        cy.flushDatabase();
        cy.registerUsers([STAFF, USER, NO_LINK]);
        cy.setStaff(STAFF.id);
        createVerifiedBilibiliLink();
    });

    it('requires a verified Bilibili account link', () => {
        cy.intercept('POST', '**/api/media/submit').as('submitWithoutLink');
        cy.login(NO_LINK.username, NO_LINK.password);
        cy.visit('/#/works');
        openSubmitDialog();
        fillAndSubmit();
        cy.wait('@submitWithoutLink').its('response.statusCode').should('eq', 403);
        cy.closeElNotifications();
    });

    it('submits BV1eB4y1F7Ao without listing it on the works table', () => {
        cy.intercept('POST', '**/api/media/submit').as('submit');
        cy.login(USER.username, USER.password);
        cy.visit('/#/works');
        openSubmitDialog();
        fillAndSubmit();
        cy.wait<unknown, MediaItem>('@submit').then(({ response }) => {
            expect(response?.statusCode).to.eq(200);
            const media = response?.body;
            expect(media, 'created media').to.not.equal(undefined);
            if (!media) return;
            expect(media.format).to.eq('B_v');
            expect(media.url).to.eq(WORK_URL);
            expect(media.status).to.eq('pending');
            expect(media.user_id).to.eq(USER.id);
            expect(media.language).to.eq('zh-cn');
            if (media.metadata_pending) {
                expect(media.title, 'degraded submission keeps an empty title').to.eq('');
            } else {
                expect(media.title, 'title fetched from Bilibili').to.eq(EXPECTED_TITLE);
            }
        });
        cy.contains('.el-notification', '投稿成功').should('be.visible');
        cy.closeElNotifications();
        cy.shouldBeAbsentOrHidden('.el-dialog');
        // 作品页表格只展示审核通过的作品；待审核作品仅在个人主页可见。
        cy.get(`.base-table a.link[href="${WORK_URL}"]`).should('not.exist');
    });

    it('rejects a duplicate submission of the same video', () => {
        cy.intercept('POST', '**/api/media/submit').as('duplicateSubmit');
        cy.login(USER.username, USER.password);
        cy.visit('/#/works');
        openSubmitDialog();
        fillAndSubmit();
        cy.wait('@duplicateSubmit').its('response.statusCode').should('eq', 409);
        cy.closeElNotifications();
    });

    it('shows the pending work on the author profile works tab', () => {
        cy.intercept('GET', '**/api/media/user/*').as('userWorks');
        cy.login(USER.username, USER.password);
        cy.visitUser(USER.id, 'works');
        cy.wait('@userWorks').its('response.statusCode').should('eq', 200);
        cy.get(`.base-table a.link[href="${WORK_URL}"]`).should('have.length', 1);
    });
});
