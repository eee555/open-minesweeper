import { Key, Lock, Message, User } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { defineComponent, h, ref } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import Menu from './Menu.vue';
import Appearance from './SettingView/Appearance.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { local, store } from '@/store';
import { pinia } from '@/store/create';

const user = { id: 42, username: 'tester', realname: 'Tester', is_staff: true };
const csrfToken = 'menu-csrf-token';
const PageState = defineComponent({
    setup() {
        const counter = ref(0);
        return () => h('button', { 'data-cy': 'page-counter',
            onClick: () => {
                counter.value++;
            } }, `${counter.value}`);
    },
});

function mountMenu(width: number, options: { layout?: 'top' | 'sidebar'; settings?: boolean; loggedOut?: boolean } = {}) {
    cy.viewport(width, 720);
    cy.clearCookie('csrftoken');
    cy.intercept({ method: 'GET', pathname: '/api/userprofile/admin/csrf' }, { csrf_token: csrfToken }).as('adminCsrf');
    cy.intercept({ method: 'GET', pathname: '/api/common/loginauto' }, { user: options.loggedOut === true ? null : user, top_anchors: { 'std:et': { value: 30000, sample_count: 20 } } }).as('fetchUser');
    local.value.language = 'en';
    local.value.navigation_layout = options.layout ?? 'top';
    if (options.loggedOut === true) store.logout();
    else store.login(user);
    const { sessionRevision } = store;
    const router = createRouter({
        history: createMemoryHistory(),
        routes: ['/', '/ranking', '/ranking/pb', '/database', '/database/identifiers', '/video/:id', '/tournament', '/minigame/left-click', '/server', '/resources', '/player/:id', '/staff', '/settings'].
            map((path) => ({ path, component: PageState })),
    });
    void router.push('/');
    cy.wrap(router.isReady()).then(() => {
        cy.mount(Menu, {
            slots: { default: () => h('main', { class: 'common-layout' }, [h(PageState), ...options.settings === true ? [h(Appearance)] : []]) },
            global: {
                plugins: [pinia, router, i18n],
                components: { Key, Lock, Message, User },
                // ElDrawer commits its closed model and destroys content in transition hooks.
                stubs: { transition: false },
                config: { globalProperties: { $axios } },
            },
        });
    });
    cy.wait('@fetchUser');
    // Management sessions are published only after the lazy CSRF interceptor is installed.
    cy.wrap(store).its('sessionRevision').should('be.greaterThan', sessionRevision);
    return router;
}

function openMore() {
    cy.get('.site-menu > .el-menu > .el-sub-menu:not([data-navigation-id]) > .el-sub-menu__title').click();
}

function expectDrawerClosed() {
    // destroy-on-close removes the links after the closing transition and model update finish.
    cy.get('.site-navigation-drawer .navigation-links').should('not.exist');
    cy.shouldBeAbsentOrHidden('.site-navigation-drawer');
    cy.get('body').should('not.have.class', 'el-popup-parent--hidden');
}

describe('<Menu /> navigation layouts', () => {
    afterEach(() => {
        cy.get('@vue').invoke('unmount');
        // Service-created overlays outlive the mounted component, including after a failed assertion.
        cy.then(() => {
            ElMessageBox.close();
            ElMessage.closeAll();
        });
        cy.shouldBeAbsentOrHidden('.el-message-box');
        cy.get('body').should('not.have.class', 'el-popup-parent--hidden');
    });

    it('places the official QQ login badge immediately before the guest login item', () => {
        mountMenu(1920, { loggedOut: true });
        cy.get('.site-menu--top [data-navigation-id=qq-login] img').should('have.attr', 'src', `${import.meta.env.BASE_URL}img/qq_login_16x16.png`).and('have.attr', 'width', '16').and('have.attr', 'height', '16');
        cy.get('.site-menu--top [data-navigation-id=qq-login] .qq-login-entry').should('have.class', 'navigation-control').and('have.class', 'qq-login-entry--compact');
        cy.get('.site-menu--top [data-navigation-id=qq-login]').then(($item) => {
            cy.get('.site-menu--top [data-navigation-id=qq-login] .qq-login-entry').should(($entry) => {
                expect($entry.height()).to.equal($item.height());
            });
        });
        cy.get('.site-menu--top [data-navigation-id=qq-login] .qq-login-label').should('have.text', 'QQ登录').parents('[data-navigation-id=qq-login]').next().should('have.attr', 'data-navigation-id', 'login');
        cy.get('.site-menu--top [data-navigation-id=qq-login] .qq-login-entry').click();
        cy.contains('.el-message', 'QQ 登录尚未开放').should('be.visible');
    });

    it('activates the QQ login entry with Enter and Space', () => {
        mountMenu(1920, { loggedOut: true });
        const entry = () => cy.get('.site-menu--top [data-navigation-id=qq-login] .qq-login-entry');
        entry().focus();
        entry().type('{enter}');
        cy.contains('.el-message', 'QQ 登录尚未开放').should('be.visible');
        cy.then(() => {
            ElMessage.closeAll();
        });
        entry().focus();
        entry().type(' ');
        cy.contains('.el-message', 'QQ 登录尚未开放').should('be.visible');
    });

    it('tracks the parent section of nested routes and returns home through the logo', () => {
        const router = mountMenu(1440);
        cy.title().should('eq', 'OpenMS - Home');
        cy.then(() => {
            expect(store.topAnchors?.['std:et']?.value).to.equal(30000);
        });
        cy.then(() => router.push('/ranking/pb'));
        cy.get('.site-menu--top [data-navigation-id=ranking]').should('have.class', 'is-active');
        cy.title().should('eq', 'OpenMS - Ranking');
        cy.then(() => router.push('/video/123'));
        cy.get('.site-menu--top [data-navigation-id=database]').should('have.class', 'is-active');
        cy.title().should('eq', 'OpenMS - Database');
        cy.then(() => router.push('/database/identifiers'));
        cy.get('.site-menu--top [data-navigation-id=database]').should('have.class', 'is-active');
        cy.get('.site-menu--top [data-navigation-id=minigame] a').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/minigame/left-click');
        cy.get('.site-menu--top [data-navigation-id=minigame]').should('have.class', 'is-active');
        cy.title().should('eq', 'OpenMS - Minigames');
        cy.get('[data-cy=navigation-home]').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/');
        cy.title().should('eq', 'OpenMS - Home');
    });

    it('collects overflowing navigation and tools into one menu and restores them when the container grows', () => {
        const router = mountMenu(260);
        openMore();
        cy.get('.site-navigation-popper:visible').contains('a', 'Server').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/server');
        cy.viewport(1440, 720);
        cy.get('.site-menu--top [data-navigation-id=server]').should('be.visible').and('have.class', 'is-active');
        cy.get('.site-menu--top > .el-menu > .el-sub-menu:not([data-navigation-id])').should('not.exist');
    });

    it('requires confirmation before logout through overflow and keeps authentication mounted once', () => {
        cy.intercept('POST', '**/userprofile/logout/', {}).as('logout');
        cy.mockCaptchaRefresh();
        mountMenu(210);
        openMore();
        cy.get('.site-navigation-popper:visible').contains('.navigation-label__text', 'Color theme').should('be.visible');
        cy.get('.site-navigation-popper:visible').contains('button', 'Logout').focus();
        cy.realPress('Space');
        cy.get('.el-message-box').should('be.visible').and('contain.text', 'Log out of the current account?');
        cy.get('.el-message-box:visible .el-message-box__btns').contains('button', /^Cancel$/).click();
        cy.shouldBeAbsentOrHidden('.el-message-box');
        cy.get('body').should('not.have.class', 'el-popup-parent--hidden');
        cy.wrap(store).its('user.id').should('eq', user.id);
        cy.get('@logout.all').should('have.length', 0);
        cy.get('@adminCsrf.all').should('have.length', 0);
        openMore();
        cy.get('.site-navigation-popper:visible').contains('button', 'Logout').click();
        cy.get('.el-message-box:visible .el-message-box__btns').contains('button', /^Confirm$/).click();
        cy.wait('@adminCsrf');
        cy.wait('@logout').its('request.headers.x-csrftoken').should('eq', csrfToken);
        cy.get('@logout.all').should('have.length', 1);
        openMore();
        cy.get('.site-navigation-popper:visible').contains('button', /^Login$/).click();
        cy.get('.el-dialog').should('be.visible');
        cy.get('@fetchUser.all').should('have.length', 1);
    });

    it('keeps the account logged in when the toolbar logout confirmation is dismissed with Escape', () => {
        cy.intercept('POST', '**/userprofile/logout/', {}).as('logout');
        mountMenu(1440);
        cy.get('.site-menu [data-navigation-id=logout] button').click();
        cy.get('.el-message-box').should('be.visible');
        cy.realPress('Escape');
        cy.shouldBeAbsentOrHidden('.el-message-box');
        cy.get('.site-menu [data-navigation-id=profile]').should('be.visible');
        cy.get('@logout.all').should('have.length', 0);
        cy.get('@adminCsrf.all').should('have.length', 0);
    });

    it('navigates through the drawer and releases it when the sidebar becomes visible', () => {
        const router = mountMenu(500, { layout: 'sidebar' });
        cy.get('[data-cy=navigation-sidebar]').should('not.exist');
        cy.get('[data-cy=navigation-toggle]').should('have.attr', 'aria-expanded', 'false').click();
        cy.get('.site-navigation-drawer').should('be.visible');
        cy.get('.site-navigation-drawer').contains('a', 'Database').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/database');
        expectDrawerClosed();
        cy.get('[data-cy=navigation-toggle]').should('be.focused').click();
        cy.get('.site-navigation-drawer').should('be.visible');
        cy.realPress('Escape');
        expectDrawerClosed();
        cy.get('[data-cy=navigation-toggle]').should('be.focused').click();
        cy.get('.site-navigation-drawer').contains('a', 'Home').click();
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/');
        expectDrawerClosed();
        cy.get('[data-cy=navigation-toggle]').click();
        cy.get('.site-navigation-drawer').should('be.visible');
        cy.viewport(1200, 720);
        cy.get('[data-cy=navigation-sidebar]').should('be.visible');
        expectDrawerClosed();
        cy.get('[data-cy=navigation-home]').should('be.focused');
    });

    it('switches layouts without resetting page state, route or authentication', () => {
        const router = mountMenu(1200, { settings: true });
        cy.then(() => router.push('/ranking/pb'));
        cy.get('[data-cy=page-counter]').click();
        cy.get('[data-cy=navigation-layout]').select('sidebar');
        cy.get('[data-cy=navigation-sidebar]').should('be.visible');
        cy.get('[data-cy=navigation-layout]').select('top');
        cy.get('.site-menu--top').should('be.visible');
        cy.get('[data-cy=page-counter]').should('have.text', '1');
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/ranking/pb');
        cy.get('@fetchUser.all').should('have.length', 1);
    });

    it('keeps the documentation URL unchanged when switching the interface language', () => {
        mountMenu(1440);
        cy.get('[data-cy=languagePicker]').click();
        cy.get('[data-navigation-id=language-en] button:visible').should('have.attr', 'aria-pressed', 'true');
        cy.get('[data-navigation-id=language-zh-cn] button:visible').click();
        cy.title().should('eq', '开源扫雷网 - 首页');
        cy.get('[data-navigation-id=docs] a').should('have.attr', 'href').and('match', /\/docs\/$/);
        cy.get('[data-cy=languagePicker]').click();
        cy.get('[data-navigation-id=language-en] button:visible').click();
        cy.title().should('eq', 'OpenMS - Home');
        cy.get('[data-navigation-id=docs] a').should('have.attr', 'href').and('match', /\/docs\/$/);
    });

    it('opens Team from About and preserves Contact links in a dropdown', () => {
        cy.mockPlayerNameFallback();
        mountMenu(1440);
        cy.get('.site-menu > .el-menu').should(($menu) => {
            const ids = [...$menu[0].children].map((element) => element.getAttribute('data-navigation-id'));
            expect(ids.slice(-2)).to.deep.equal(['about', 'contact']);
        });
        cy.get('[data-navigation-id=about] > .el-sub-menu__title').click();
        cy.get('[data-navigation-id=team] button:visible').click();
        cy.get('.el-dialog').should('be.visible').and('contain.text', 'Owner');
        cy.realPress('Escape');
        cy.shouldBeAbsentOrHidden('.el-dialog');
        cy.get('[data-navigation-id=contact] > .el-sub-menu__title').click();
        for (const [label, href] of [
            ['GitHub', 'https://github.com/eee555/saolei_website'],
            ['Gitee', 'https://gitee.com/ee55/saolei_website'],
            ['Discord', 'https://discord.gg/ks8ngPX5bT'],
            ['QQ', 'https://qm.qq.com/q/hNShGUQkJG'],
        ] as const) {
            cy.get('.site-navigation-popper:visible').contains('a', label).should('have.attr', 'href', href).
                and('have.attr', 'target', '_blank').and('have.attr', 'rel', 'noopener noreferrer');
        }
    });

    it('keeps software downloads out of About now that Resources is a page', () => {
        mountMenu(1600);
        cy.get('[data-navigation-id=about] > .el-sub-menu__title').click();
        cy.get('.site-navigation-popper:visible [data-navigation-id=downloads]').should('not.exist');
        cy.get('body').click(0, 0);
        cy.get('[data-navigation-id=resources] a').should('have.attr', 'href').and('match', /\/resources$/);
    });
});
