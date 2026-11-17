import { createMemoryHistory, createRouter } from 'vue-router';

import ResourcesView from './App.vue';
import { resourceRoutes } from './routes';

import i18n from '@/i18n';
import { pinia } from '@/store/create';
import { getDocsUrl } from '@/utils/docs';

const TABS = [
    { id: 'metasweeper', en: 'Metasweeper', zh: '元扫雷' },
    { id: 'arbiter', en: 'Arbiter', zh: '阿比特' },
    { id: 'vienna', en: 'ViennaSweeper', zh: '维也纳扫雷' },
    { id: 'classic95', en: '95 Classic', zh: '95经典扫雷' },
    { id: 'analyzer', en: 'Video Analyzer', zh: '录像分析器' },
    { id: 'yuanshen', en: 'Yuanshen Toolbox', zh: '元神工具箱' },
    { id: 'browser-extension', en: 'Browser Extension', zh: '浏览器扩展' },
] as const;
const FIRST_PATH = '/resources/metasweeper';
const BROWSER_EXTENSION_PANEL = '[data-cy=resource-browser-extension]';

// 路由表与站点一致：/resources 重定向到第一项，未知子路径也回到第一项。
function mountResources(path = FIRST_PATH, language: 'en' | 'zh-cn' = 'en') {
    i18n.global.locale.value = language;
    const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/resources', redirect: FIRST_PATH }, ...resourceRoutes, { path: '/', component: ResourcesView }],
    });
    void router.push(path);
    cy.wrap(router.isReady()).then(() => {
        cy.mount(ResourcesView, { global: { plugins: [pinia, router, i18n] } });
    });
    return router;
}

const originalLocale = i18n.global.locale.value;
afterEach(() => {
    i18n.global.locale.value = originalLocale;
});

function tabOf(label: string) {
    return cy.contains('.resources-tabs .el-tabs__item', label);
}

describe('<ResourcesView /> routing', () => {
    it('redirects the bare path to the first resource', () => {
        const router = mountResources('/resources');
        // 组件测试跑在 Cypress 的 iframe 里，内存路由不改 window.location，只能读路由实例。
        cy.wrap(router).its('currentRoute.value.path').should('eq', FIRST_PATH);
        cy.get('[data-cy=resource-metasweeper]').should('be.visible').and('contain.text', 'Metasweeper');
        cy.get('[data-cy=resource-arbiter]').should('not.exist');
        tabOf('Metasweeper').should('have.attr', 'aria-selected', 'true');
    });

    it('switches tabs through the router and keeps the URL in sync', () => {
        const router = mountResources();
        for (const tab of TABS) {
            tabOf(tab.en).click();
            cy.wrap(router).its('currentRoute.value.path').should('eq', `/resources/${tab.id}`);
            cy.get(`[data-cy=resource-${tab.id}]`).should('be.visible');
            tabOf(tab.en).should('have.attr', 'aria-selected', 'true');
        }
        // 标签内容按需渲染：未访问的标签不进入 DOM，访问过的保留但只有一个可见。
        cy.get('.resources-panel:visible').should('have.length', 1);
    });

    it('localizes tab labels and uses 元扫雷 for Metasweeper in Chinese', () => {
        mountResources(FIRST_PATH, 'zh-cn');
        cy.get('.resources-tabs .el-tabs__item').should('have.length', TABS.length);
        for (const tab of TABS) {
            tabOf(tab.zh).should('exist');
        }
        tabOf('元扫雷').should('have.attr', 'aria-selected', 'true');
    });

    it('opens a deep link and falls back to the first resource for unknown paths', () => {
        const router = mountResources('/resources/analyzer');
        // 只断言结构与路由，不绑定面板里的具体文案。
        cy.get('[data-cy=resource-analyzer]').should('be.visible');
        cy.get('[data-cy=resource-analyzer] a[download]').should('exist');
        tabOf('Video Analyzer').should('have.attr', 'aria-selected', 'true');

        cy.then(() => router.push('/resources/not-a-resource'));
        cy.wrap(router).its('currentRoute.value.path').should('eq', FIRST_PATH);
        cy.get('[data-cy=resource-metasweeper]').should('be.visible');
        tabOf('Metasweeper').should('have.attr', 'aria-selected', 'true');
    });

    it('renders panel content without a card title or border', () => {
        mountResources('/resources/analyzer');
        cy.get('[data-cy=resource-analyzer]').should('not.have.class', 'card');
        cy.get('[data-cy=resource-analyzer] h2').should('not.exist');
        cy.get('[data-cy=resource-analyzer] a[download]').first().should(($link) => {
            const filename = $link.attr('download');
            expect(filename).to.match(/^OpenMinesweeperVideoAnalyzer-\d+\.\d+\.\d+\.zip$/u);
            expect($link.attr('href')).to.eq(`${import.meta.env.BASE_URL}assets/${filename}`);
        });

        tabOf('Arbiter').click();
        cy.get('[data-cy=resource-arbiter]').should('contain.text', 'Arbiter').and('contain.text', 'Windows');
    });
});

describe('<ResourcesView /> browser extension', () => {
    it('opens the browser extension and links its project, release and Chinese guide', () => {
        const router = mountResources('/resources/browser-extension');
        cy.wrap(router).its('currentRoute.value.path').should('eq', '/resources/browser-extension');
        tabOf('Browser Extension').should('have.attr', 'aria-selected', 'true');
        cy.get(BROWSER_EXTENSION_PANEL).should('be.visible').and('contain.text', 'third-party').and('contain.text', 'automatic replay upload');

        const links = [
            ['Project', 'https://github.com/LockhartANR/yuanshen-helper'],
            ['GitHub Releases', 'https://github.com/LockhartANR/yuanshen-helper/releases/latest'],
            ['Guide (Chinese)', getDocsUrl('zh/guide/tools/browser-extension')],
        ] as const;
        for (const [label, href] of links) {
            cy.contains(`${BROWSER_EXTENSION_PANEL} a`, label).should(($link) => {
                expect($link.attr('href')).to.eq(href);
                expect($link.attr('target')).to.eq('_blank');
                expect($link.attr('rel')).to.eq('noopener noreferrer');
            });
        }
    });

    it('shows the Chinese extension description and guide', () => {
        mountResources('/resources/browser-extension', 'zh-cn');
        cy.get(BROWSER_EXTENSION_PANEL).should('contain.text', '第三方').and('contain.text', '自动上传录像');
        cy.contains(`${BROWSER_EXTENSION_PANEL} a`, '使用说明').should('have.attr', 'href', getDocsUrl('zh/guide/tools/browser-extension'));
    });
});
