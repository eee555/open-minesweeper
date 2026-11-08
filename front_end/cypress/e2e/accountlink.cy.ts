import type { AccountLinkQueueResponse } from '../../src/utils/accountlinks/common';

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
const LINKS = {
    bilibili: {
        platform: '哔哩哔哩',
        identifier: '208259',
    },
    wom: {
        platform: 'Minesweeper.Online',
        identifier: '1782682',
    },
    saolei: {
        platform: '扫雷网',
        identifier: '18290',
    },
    msgames: {
        platform: '国际网',
        identifier: '7872',
    },
    qq: {
        platform: '腾讯QQ',
        identifier: '123456789',
    },
    discord: {
        platform: 'Discord',
        identifier: '18446744073709551615',
    },
} as const;

function linkNewAccount(platform: string, identifier: string) {
    cy.intercept('POST', '/api/accountlink/create/').as('addAccountLink');
    cy.contains('.account-platform-grid button', platform).click();
    if (platform === LINKS.bilibili.platform) {
        cy.contains('隐私提醒');
        cy.contains('关联 Bilibili 后');
    }
    cy.get('[data-cy=account-link-form] input').type(identifier);
    cy.get('[data-cy=account-link-form] button[type=submit]').click();
    cy.wait('@addAccountLink').then(({ response }) => {
        expect(response?.statusCode).to.equal(200);
        expect(response?.body).to.include({
            identifier,
            userprofile: USER.id,
            verified: false,
        });
    });
    cy.get('[data-cy=account-link-form]').should('not.exist');
}

function expectUnverifiedAccount(platform: string, identifier: string) {
    cy.get('[data-cy=account-details]').within(() => {
        cy.contains(platform);
        cy.contains(`#${identifier}`);
        cy.contains('账号未验证');
    });
}

function waitForLoading() {
    cy.get('.el-loading-mask:visible').should('not.exist');
    cy.get('.account-links-page[aria-busy=true]').should('not.exist');
}

function visitStaffAccountLink() {
    cy.login(STAFF.username, STAFF.password);
    cy.visit('/#/staff/accountlink');
    cy.wait('@accountLinkQueue').its('response.statusCode').should('eq', 200);
    waitForLoading();
}

function expectAccountLinkTableRow(platform: string, identifier: string, verified: boolean) {
    cy.get('table:visible', { timeout: 10000 }).extractTableData().should((rows) => {
        expect(rows[0]).to.deep.equal(['用户 ID', '平台', '平台 ID', '已验证']);
        const row = rows.slice(1).find((item) => item[2] === identifier);

        expect(row, `account link row for ${platform} #${identifier}`).to.deep.equal([
            `${USER.id}`, platform, identifier, verified ? '已验证' : '未验证',
        ]);
    });
}

function expectAccountLinkTableData(expected: { platform: string; identifier: string; verified: boolean }[]) {
    cy.get('table:visible').extractTableData().should((rows) => {
        expect(rows[0]).to.deep.equal(['用户 ID', '平台', '平台 ID', '已验证']);
        const tableData = rows.slice(1);
        expect(tableData.length).to.equal(expected.length);
        expected.forEach((item) => {
            const row = tableData.find((tableRow) => tableRow[2] === item.identifier);
            expect(row).to.deep.equal([
                `${USER.id}`, item.platform, item.identifier, item.verified ? '已验证' : '未验证',
            ]);
        });
    });
}

function staffVerifyAccount(platform: string, identifier: string) {
    visitStaffAccountLink();
    expectAccountLinkTableRow(platform, identifier, false);

    cy.contains('.el-form-item__label', '用户 ID').next().find('input').clear();
    cy.contains('.el-form-item__label', '用户 ID').next().find('input').type(`${USER.id}{enter}`);
    cy.contains('.el-form-item__label', /^平台$/).next().find('select').select(platform);
    cy.contains('.el-form-item__label', '平台 ID').next().find('input').type(`${identifier}{enter}`);
    cy.contains('button', /^\s*绑定\s*$/).click();
    cy.wait('@verifyAccountLink').its('response.statusCode').should('eq', 200);
    cy.wait<unknown, AccountLinkQueueResponse[]>('@accountLinkQueue').then(({ response }) => {
        expect(response?.statusCode).to.equal(200);
        const link = response?.body.find((item) => item.userprofile === USER.id && item.identifier === identifier);
        expect(link?.verified, `refreshed queue for ${platform} #${identifier}`).to.equal(true);
    });
    waitForLoading();

    expectAccountLinkTableRow(platform, identifier, true);
}

describe('Account Link', () => {
    beforeEach(() => {
        // Register once per test: private account verification visits this page twice.
        cy.intercept('GET', '/api/accountlink/admin/queue').as('accountLinkQueue');
        cy.intercept('POST', '**/api/accountlink/verify/').as('verifyAccountLink');
    });

    it('Before All', () => {
        // 初始化数据库
        cy.flushDatabase();

        // 注册用户
        cy.registerUsers([STAFF, USER]);
        cy.setStaff(STAFF.id);
    });

    it('Guest View - No Account Links', () => {
        cy.visitUser(USER.id, 'accountlink');
        cy.get('.account-platform-grid button').should('have.length', 9);
        cy.contains('暂无可展示的关联').should('be.visible');
    });

    it('Link Public Accounts', () => {
        cy.login(USER.username, USER.password);
        cy.visitUser(USER.id, 'accountlink');

        linkNewAccount(LINKS.wom.platform, LINKS.wom.identifier);
        expectUnverifiedAccount(LINKS.wom.platform, LINKS.wom.identifier);

        linkNewAccount(LINKS.saolei.platform, LINKS.saolei.identifier);
        expectUnverifiedAccount(LINKS.saolei.platform, LINKS.saolei.identifier);

        linkNewAccount(LINKS.msgames.platform, LINKS.msgames.identifier);
        expectUnverifiedAccount(LINKS.msgames.platform, LINKS.msgames.identifier);

        linkNewAccount(LINKS.bilibili.platform, LINKS.bilibili.identifier);
        expectUnverifiedAccount(LINKS.bilibili.platform, LINKS.bilibili.identifier);
    });

    it('Guest View - Should Not See Unverified Accounts', () => {
        cy.visitUser(USER.id, 'accountlink');
        cy.contains('暂无可展示的关联').should('be.visible');
        cy.get('[data-cy=account-link-form]').should('not.exist');
    });

    it('Staff View - Should Not See The Add Button', () => {
        cy.login(STAFF.username, STAFF.password);
        cy.visitUser(USER.id, 'accountlink');
        cy.get('[data-cy=account-link-form]').should('not.exist');
    });

    it('Link Private Accounts', () => {
        cy.login(USER.username, USER.password);
        cy.visitUser(USER.id, 'accountlink');

        linkNewAccount(LINKS.qq.platform, LINKS.qq.identifier);
        expectUnverifiedAccount(LINKS.qq.platform, LINKS.qq.identifier);
        linkNewAccount(LINKS.discord.platform, LINKS.discord.identifier);
        expectUnverifiedAccount(LINKS.discord.platform, LINKS.discord.identifier);

        cy.get('[data-cy=account-link-form]').should('not.exist');
    });

    it('Staff View - Should Render Account Link Table', () => {
        visitStaffAccountLink();

        expectAccountLinkTableData([
            { platform: LINKS.wom.platform, identifier: LINKS.wom.identifier, verified: false },
            { platform: LINKS.saolei.platform, identifier: LINKS.saolei.identifier, verified: false },
            { platform: LINKS.msgames.platform, identifier: LINKS.msgames.identifier, verified: false },
            { platform: LINKS.bilibili.platform, identifier: LINKS.bilibili.identifier, verified: false },
            { platform: LINKS.qq.platform, identifier: LINKS.qq.identifier, verified: false },
            { platform: LINKS.discord.platform, identifier: LINKS.discord.identifier, verified: false },
        ]);
    });

    it('Verify WoM Account', () => {
        staffVerifyAccount(LINKS.wom.platform, LINKS.wom.identifier);
    });

    it('Verify Saolei Account', () => {
        staffVerifyAccount(LINKS.saolei.platform, LINKS.saolei.identifier);
    });

    it('Verify MSGames Account', () => {
        staffVerifyAccount(LINKS.msgames.platform, LINKS.msgames.identifier);
    });

    it('Verify Bilibili Account', () => {
        staffVerifyAccount(LINKS.bilibili.platform, LINKS.bilibili.identifier);
    });

    it('Verify Private Accounts', () => {
        staffVerifyAccount(LINKS.qq.platform, LINKS.qq.identifier);
        staffVerifyAccount(LINKS.discord.platform, LINKS.discord.identifier);
    });

    it('Guest View - Should Not See Private Accounts', () => {
        cy.intercept('GET', `/api/accountlink/${USER.id}`).as('fetchAccountLinks');
        cy.visitUser(USER.id, 'accountlink');
        cy.wait('@fetchAccountLinks').its('response.statusCode').should('eq', 200);
        waitForLoading();
        cy.get('.account-platform-grid button').should('have.length', 9);
        for (const link of [LINKS.saolei, LINKS.msgames, LINKS.wom, LINKS.bilibili]) {
            cy.contains('.account-platform-grid button', link.platform).click();
            cy.get('[data-cy=account-details] h2').should('contain', `#${link.identifier}`);
            cy.get('[data-cy=account-details] > .account-panel').should('have.length', 1);
        }
        for (const link of [LINKS.qq, LINKS.discord]) {
            cy.contains('.account-platform-grid button', link.platform).click();
            cy.get('[data-cy=account-details]').should('contain', '私密关联').and('not.contain', link.identifier);
        }
    });
});
