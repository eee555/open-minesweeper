// 个人主页
import 'cypress-if';
import { binaryStringToUint8Array } from '../support/stupidCypress';

const USER_ID = 2418 as const;
const USERNAME = 'testUser' as const;
const PASSWORD = 'testPassword' as const;
const REALNAME = 'testName' as const;

describe('Personal Profile', () => {
    it('Before All', () => {
        // 初始化数据库
        cy.flushDatabase();

        // 注册并登录用户
        cy.registerUser({
            id: USER_ID,
            username: USERNAME,
            email: 'test@email.com',
            password: PASSWORD,
        });
        cy.login(USERNAME, PASSWORD);
    });

    it('Profile section', () => {
        cy.visitUser(USER_ID);

        cy.get('.profile').contains(USERNAME);
        cy.get('.profile').contains(`#${USER_ID}`);
        cy.get('.profile').contains('匿名');

        cy.get('.avatar').find('img').should('have.attr', 'src').should('include', 'person.png');
    });

    it('Navigation', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/top`);

        cy.get('div.el-tabs__item').contains('纪录').click();
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/record`);
        cy.get('.saolei-record-table thead th').first().should('have.css', 'text-align', 'center');
        cy.get('.saolei-record-table tbody td').first().should('have.css', 'text-align', 'center');

        cy.get('div.el-tabs__item').contains('账号关联').click();
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/accountlink`);

        cy.get('div.el-tabs__item').contains('录像').click();
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/videos`);

        cy.get('div.el-tabs__item').contains('上传').click();
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/upload`);

        cy.get('div.el-tabs__item').contains('设置').click();
        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/settings`);
    });

    it('Cannot upload videos without real name', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);
        cy.get('div.el-tabs__item').contains('上传').click();
        cy.contains('请修改为实名');
    });

    it('Change local name', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);

        cy.get('.profile-section').contains('编辑信息').click();

        cy.url().should('include', `/player/${USER_ID}/settings`);
        cy.get('.user-settings').within(() => {
            cy.contains('本名').parent().next().find('input').type(REALNAME);
            cy.contains('button', '保存').click();
        });

        cy.get('.user-settings').contains('修改成功');
        cy.get('.profile').contains(REALNAME);
    });

    it('Upload video', function () {
        cy.intercept({ method: 'GET', pathname: '/api/common/loginauto' }).as('currentUser');
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID, 'upload');
        cy.wait('@currentUser').its('response.body.user.realname').should('eq', REALNAME);
        cy.get('.profile').contains(REALNAME);

        // 准备录像文件
        cy.fixture('Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', 'binary').then((fileContent) => {
            cy.wrap(binaryStringToUint8Array(fileContent)).as('videoFileExpAvf');
        });
        cy.fixture('3819-Time-1616-NF-9469-32-20151031.rmv', 'binary').then((fileContent) => {
            cy.wrap(binaryStringToUint8Array(fileContent)).as('videoFileIntRmv');
        });

        cy.get('.el-tabs__content').find('input[type=file]').should('not.be.disabled').selectFile([
            {
                contents: '@videoFileExpAvf',
                fileName: 'videoFileExp.avf',
            },
            {
                contents: '@videoFileIntRmv',
                fileName: 'videoFileInt.rmv',
            },
        ], { force: true });

        const expectedData = {
            ExpAvf: { '': '', Bv: '132', Bvs: '3.762', 状态: '通过', 用时: '35.090', 级别: '高级', 模式: '标准', 结束时间: '2023-10-05 21:25:57' },
            IntRmv: { '': '', Bv: '32', Bvs: '3.379', 状态: '通过', 用时: '9.469', 级别: '中级', 模式: '标准', 结束时间: '2015-10-31 22:53:35' },
        };

        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(2);
            expect(tableData[0]).to.deep.equal(expectedData.ExpAvf);
            expect(tableData[1]).to.deep.equal(expectedData.IntRmv);
        });

        cy.get('table:visible .checkbox-input').first().click(); // 全选
        cy.get('button').contains(/^\s*上传\s*$/).click();
        cy.get('.el-loading-spinner').should('exist');
        cy.get('.el-loading-spinner').should('not.exist');

        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(2);
            expect(tableData[0]).to.deep.equal({ ...expectedData.ExpAvf, 状态: '新标识' });
            expect(tableData[1]).to.deep.equal({ ...expectedData.IntRmv, 状态: '新标识' });
        });
    });

    it('Cannot update avatar or signature before sub200', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);

        cy.get('.avatar').find('img').should('have.attr', 'title', '高级sub200后才可以修改头像');
        cy.get('.profile-section').contains('编辑信息').click();

        cy.get('.user-settings').within(() => {
            cy.contains('个性签名').parent().next().find('textarea').should('be.disabled');
            cy.contains('高级sub200后才可以修改个性签名');
        });
    });

    it('Add identifier', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID, 'settings');

        cy.get('.user-settings table').then((table) => {
            cy.wrap(table).find('input').type('Pu Tian Yi(Hu Bei)');
            cy.wrap(table).find('.pi-plus').click();
        });

        cy.contains('添加标识成功');
        cy.closeElNotifications();
    });

    it('Loads PB records from its top-level tab without downloading all videos', () => {
        cy.intercept('GET', '/api/userprofile/videolist*').as('allVideos');
        cy.intercept('GET', `/api/speedranking/pb/player/${USER_ID}`).as('pbRecords');
        cy.visitUser(USER_ID);
        cy.get('[data-cy=profile-tabs] > .el-tabs__header .is-active').should('have.text', 'Top');
        cy.get('[data-cy=profile-tabs] > .el-tabs__header [role=tab]').contains('PB').click();
        cy.url().should('include', `/player/${USER_ID}/pb`);
        cy.wait('@pbRecords');
        cy.get('[data-cy=pb-summary]').should('be.visible');
        cy.get('[data-cy=pb-grid-e]').should('be.visible');
        cy.get('@allVideos.all').should('have.length', 0);
        cy.contains('扫雷标识').should('not.exist');
    });

    it('Auto load identifiers when visiting settings directly', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID, 'settings');

        cy.get('.user-settings').should('have.css', 'display', 'flex').and('have.css', 'flex-direction', 'column');
        cy.get('.user-settings table').contains('Pu Tian Yi(Hu Bei)');
    });

    it('Auto load videos when visiting videos', () => {
        cy.visitUser(USER_ID, 'videos');

        cy.get('table:visible').getTable().should((tableData) => {
            expect(tableData.length).to.equal(2);
        });
        cy.get('[data-cy=video-overview]').select('calendar');
        cy.contains('共2个录像');
        cy.get('[data-cy=video-overview]').select('bv');
        cy.contains('共1个Bv');
    });

    it('Update avatar', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);

        cy.get('.avatar').find('img').should('have.attr', 'title', '点击修改头像（剩余2次）');

        cy.get('.avatar').find('input[type=file]').selectFile('cypress/fixtures/test.png', { force: true });

        cy.get('.avatar').find('img').should('have.attr', 'src').and('include', `${USER_ID}?v=1`);

        cy.get('.avatar').find('img').should('have.attr', 'title', '点击修改头像（剩余1次）');
    });

    it('Update signature', () => {
        cy.login(USERNAME, PASSWORD);
        cy.visitUser(USER_ID);

        cy.get('.profile-section').contains('编辑信息').click();

        cy.get('.user-settings').within(() => {
            cy.contains('个性签名').parent().next().find('textarea').should('be.enabled').type('testSignature');
            cy.contains('button', '保存').click();
        });

        cy.get('.user-settings').contains('修改成功');
        cy.get('.profile-section').contains('testSignature');
    });

    it('Guest view', () => {
        cy.visitUser(USER_ID);

        cy.get('div.el-tabs__item').contains('上传').should('not.exist');
        cy.get('div.el-tabs__item').contains('设置').should('not.exist');
        cy.get('.profile-section').contains('编辑信息').should('not.exist');

        cy.visitUser(USER_ID, 'settings');
        cy.url().should('include', `/player/${USER_ID}/top`);
        cy.get('.user-settings').should('not.exist');
    });

    it('Public database lookup works in both directions', () => {
        cy.intercept('GET', '/api/userprofile/identifier*').as('playerIdentifiers');
        cy.intercept('GET', '/api/identifier/query/exact*').as('identifierOwner');
        cy.visit('/#/database/identifiers');
        cy.get('#identifier-player-id').type(`${USER_ID}{enter}`);
        cy.wait('@playerIdentifiers');
        cy.get('table').contains('Pu Tian Yi(Hu Bei)');
        cy.get(`table a[href="#/player/${USER_ID}"]`).should('be.visible');

        cy.get('#identifier-text').type('Pu Tian Yi(Hu Bei){enter}');
        cy.wait('@identifierOwner');
        cy.get('table').contains('Pu Tian Yi(Hu Bei)');
        cy.get(`table a[href="#/player/${USER_ID}"]`).should('be.visible');
    });

    it('Navigate from homepage', () => {
        cy.intercept({ method: 'GET', pathname: '/api/video/newest_queue' }).as('newestQueue');
        cy.visit('/');
        cy.wait('@newestQueue').its('response.statusCode').should('eq', 200);

        cy.get('#pane-newest').should('be.visible').find(`a[href="#/player/${USER_ID}"]`).first().should('be.visible').click();

        cy.url().should('eq', `http://localhost:8080/#/player/${USER_ID}/top`);

        cy.get('[data-cy=top-summary]').should('be.visible');
    });
});
