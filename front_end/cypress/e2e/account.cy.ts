// 注册、登录、找回密码
function expectNotLoggedIn() {
    cy.get('[data-cy=app-header] [data-navigation-id=login]').should('be.visible');
    cy.get('[data-cy=app-header] [data-navigation-id=register]').should('be.visible');
    cy.get('[data-cy=app-header] [data-navigation-id=logout]').should('not.exist');
}

function expectLoggedIn() {
    cy.get('[data-cy=app-header] [data-navigation-id=logout]').should('be.visible');
    cy.get('[data-cy=app-header] [data-navigation-id=login]').should('not.exist');
    cy.get('[data-cy=app-header] [data-navigation-id=register]').should('not.exist');
}

describe('User Authentication', () => {
    before(() => {
        // 初始化数据库
        cy.flushDatabase();
    });

    it('Popup Functions', () => {
        // 初始状态
        cy.visit('/#/settings');
        expectNotLoggedIn();
        cy.contains('用户注册').should('not.exist');
        cy.contains('用户登录').should('not.exist');

        // 打开并关闭注册界面
        cy.contains('注册').click();
        cy.contains('用户注册').should('be.visible');
        cy.contains('用户注册').next().click();
        cy.shouldBeAbsentOrHidden('.el-dialog');

        // 打开并关闭登录界面
        cy.get('[data-cy=app-header] [data-navigation-id=login] .navigation-control').click();
        cy.contains('用户登录').should('be.visible');
        cy.contains('用户登录').next().click();
        cy.shouldBeAbsentOrHidden('.el-dialog');
    });

    it('Register', () => {
        // 打开注册界面
        cy.visit('/#/settings');
        cy.contains('注册').click();

        // 填写注册信息
        cy.get('.el-dialog:visible').within(() => {
            cy.contains('.el-form-item__label', /^\s*用户名\s*$/).next().find('input').type('testUser');
            cy.contains('.el-form-item__label', /^\s*邮箱\s*$/).next().find('input').type('testUser@example.com');
            cy.contains('.el-form-item__label', /^\s*图形验证码\s*$/).next().find('input').type('test');
            cy.contains('button', /^\s*发送\s*$/).click();
        });
        cy.contains('邮件发送成功');
        cy.closeElNotifications();
        cy.get('.el-dialog:visible').within(() => {
            cy.contains('.el-form-item__label', /^\s*邮箱验证码\s*$/).next().find('input').type('abcdef');
            cy.contains('.el-form-item__label', /^\s*密码\s*$/).next().find('input').type('testPassword');
            cy.contains('.el-form-item__label', /^\s*确认密码\s*$/).next().find('input').type('testPassword');
            cy.contains('label', '已阅读并同意').find('input').parent().click();
        });

        // 完成注册
        cy.get('.el-dialog:visible').contains('button', /^\s*注册\s*$/).click();
        cy.contains('注册成功');
        cy.shouldBeAbsentOrHidden('.el-dialog');

        // 退出登录
        expectLoggedIn();
        cy.closeElNotifications();
        cy.contains(/^退出$/).click();
        cy.get('.el-message-box__btns').contains('button', /^确认$/).click();
        expectNotLoggedIn();
    });

    it('Login & logout', () => {
        // 打开登录界面
        cy.visit('/#/settings');
        expectNotLoggedIn();
        cy.get('[data-cy=app-header] [data-navigation-id=login] .navigation-control').click();

        // 填写登录信息
        cy.get('.el-dialog:visible').then((dialog) => {
            cy.wrap(dialog).contains('用户名').next().find('input').type('testUser');
            cy.wrap(dialog).contains('密码').next().find('input').type('testPassword');
            cy.wrap(dialog).contains('验证码').next().find('input').type('test');

            cy.wrap(dialog).find('button').contains(/^\s*登录\s*$/).click();
        });

        cy.shouldBeAbsentOrHidden('.el-dialog');
        expectLoggedIn();

        // 刷新页面
        cy.reload();
        expectLoggedIn();

        // 退出登录
        cy.contains('退出').click();
        cy.get('.el-message-box__btns').contains('button', /^确认$/).click();
        expectNotLoggedIn();

        cy.reload();
        expectNotLoggedIn();
    });

    it('Incorrect password', () => {
        cy.visit('/#/settings');
        expectNotLoggedIn();

        // 尝试用错误密码登录
        cy.get('[data-cy=app-header] [data-navigation-id=login] .navigation-control').click();
        cy.get('.el-dialog:visible').then((dialog) => {
            cy.wrap(dialog).contains('用户名').next().find('input').type('testUser');
            cy.wrap(dialog).contains('密码').next().find('input').type('newPassword');
            cy.wrap(dialog).contains('验证码').next().find('input').type('test');
            cy.wrap(dialog).find('button').contains(/^\s*登录\s*$/).click();
        });

        cy.contains('用户名或密码不正确');
        expectNotLoggedIn();
    });

    it('Forget Password', () => {
        cy.visit('/#/settings');
        expectNotLoggedIn();

        cy.get('[data-cy=app-header] [data-navigation-id=login] .navigation-control').click();
        cy.get('.el-dialog:visible').then((dialog) => {
            cy.wrap(dialog).contains('忘记密码').click();
            cy.wrap(dialog).contains('修改密码').should('be.visible');
            cy.wrap(dialog).contains('用户登录').should('not.exist');

            cy.wrap(dialog).contains('邮箱').next().find('input').type('testUser@example.com');
            cy.wrap(dialog).contains('图形验证码').next().find('input').type('test');
            cy.wrap(dialog).contains('发送').click();
        });

        cy.contains('邮件发送成功');
        cy.closeElNotifications();

        cy.get('.el-dialog:visible').then((dialog) => {
            cy.wrap(dialog).contains('邮箱验证码').next().find('input').type('abcdef');
            cy.wrap(dialog).contains(/^密码$/).next().find('input').type('newPassword');
            cy.wrap(dialog).contains('确认密码').next().find('input').as('confirmPasswordInput').type('newPassword');
            cy.get('@confirmPasswordInput').blur();

            cy.wrap(dialog).find('button').contains('更新密码').click();
        });

        cy.contains('修改密码成功');
        cy.closeElNotifications();

        cy.shouldBeAbsentOrHidden('.el-dialog');
        expectLoggedIn();
    });
});
