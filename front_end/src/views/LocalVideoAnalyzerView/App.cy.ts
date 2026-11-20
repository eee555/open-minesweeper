import { h } from 'vue';

import offlineCopyright from '../../../local-analyzer/COPYRIGHT.txt?raw';
import offlineReadme from '../../../local-analyzer/README.txt?raw';
import analyzerVersion from '../../../local-analyzer/version.json';

import App from './App.vue';

import i18n from '@/i18n';
import { local } from '@/store/local';

function mountLocalAnalyzer() {
    // Match local-analyzer/main.ts: the percentage-based splitter has a viewport-height parent.
    cy.mount({ render: () => h('div', { style: { height: '100vh' } }, [h(App)]) }, { global: { plugins: [i18n] } });
}

describe('<LocalVideoAnalyzerView />', () => {
    let originalLocale: typeof i18n.global.locale.value;
    let originalLanguage: string;
    let originalDocumentLanguage: string;
    beforeEach(() => {
        originalLocale = i18n.global.locale.value;
        originalLanguage = local.value.language;
        i18n.global.locale.value = 'en';
        local.value.language = 'en';
        cy.document().then((doc) => {
            originalDocumentLanguage = doc.documentElement.lang;
        });
    });
    afterEach(() => {
        i18n.global.locale.value = originalLocale;
        local.value.language = originalLanguage;
        cy.document().then((doc) => {
            doc.documentElement.lang = originalDocumentLanguage;
        });
    });

    it('switches the whole interface language, persists the choice and retains the loaded replay position', () => {
        mountLocalAnalyzer();
        cy.get('.local-analyzer__file input').selectFile('cypress/fixtures/52200.evf', { force: true });
        cy.get('.analyzer-progress-bar__slider', { timeout: 10000 }).should('have.attr', 'max', '10732').invoke('val', 5000).trigger('input');
        cy.get('.video-analyzer-info .local-analyzer__language').select('zh-cn');
        cy.get('.local-analyzer__file').should('contain.text', '选择或拖入');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', '播放');
        cy.get('.local-analyzer__readme summary').should('contain.text', '使用说明');
        cy.get('.local-analyzer__version').should('have.text', `版本 v${analyzerVersion.version}`);
        cy.document().its('documentElement.lang').should('eq', 'zh-cn');
        cy.window().should((win) => {
            expect(JSON.parse(win.localStorage.getItem('local') ?? '{}')).to.have.property('language', 'zh-cn');
        });
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.local-analyzer__language').select('es');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Reproducir');
        cy.get('.local-analyzer__version').should('have.text', `Versión v${analyzerVersion.version}`);
        cy.document().its('documentElement.lang').should('eq', 'es');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.local-analyzer__language').select('en');
        cy.get('.local-analyzer__file').should('contain.text', 'Choose or drop');
        cy.get('.local-analyzer__version').should('have.text', `Version v${analyzerVersion.version}`);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        cy.document().its('documentElement.lang').should('eq', 'en');
        cy.window().should((win) => {
            expect(JSON.parse(win.localStorage.getItem('local') ?? '{}')).to.have.property('language', 'en');
        });
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
    });

    it('shows the packaged README and COPYRIGHT in two initially collapsed details inside the info slot', () => {
        mountLocalAnalyzer();
        cy.get('.video-analyzer-info .local-analyzer__notices details').should('have.length', 2).each(($details) => {
            cy.wrap($details).should('not.have.attr', 'open');
        });
        cy.get('.video-analyzer-info .local-analyzer__version').should('be.visible').and('have.text', `Version v${analyzerVersion.version}`);
        cy.get<HTMLImageElement>('.video-analyzer-info .local-analyzer__icon').should('be.visible').and('have.attr', 'alt', '').and(($icon) => {
            expect($icon.attr('src')).to.match(/^data:image\/svg\+xml[;,]/u);
            expect($icon[0].complete).to.eq(true);
            expect($icon[0].naturalWidth).to.be.greaterThan(0);
        });
        cy.get('.local-analyzer__notices pre').should(($text) => {
            for (const element of $text) expect(element.checkVisibility()).to.eq(false);
        });
        cy.get('.local-analyzer__readme summary').click();
        cy.get('.local-analyzer__readme pre').should('be.visible').and(($text) => {
            expect($text.text().trim()).to.eq(offlineReadme.trim());
        });
        cy.get('.local-analyzer__copyright').should('not.have.attr', 'open');
        cy.get('.local-analyzer__copyright summary').click();
        cy.get('.local-analyzer__copyright pre').scrollIntoView();
        cy.get('.local-analyzer__copyright pre').should('be.visible').and(($text) => {
            expect($text.text().trim()).to.eq(offlineCopyright.trim());
        });
        cy.get('.local-analyzer__readme summary').click();
        cy.get('.local-analyzer__readme').should('not.have.attr', 'open');
        cy.get('.local-analyzer__copyright').should('have.attr', 'open');
        cy.get('.local-analyzer__file').should('be.visible');
    });

    it('places a single-file selector in the info slot, loads real local bytes without API requests and resets when the file changes', () => {
        cy.viewport(1100, 800);
        cy.intercept('GET', '**/api/**', { statusCode: 500 }).as('websiteApi');
        cy.intercept('GET', '**/api/video/**', { statusCode: 500 }).as('softwareApi');
        mountLocalAnalyzer();
        cy.get('.local-analyzer__file').should('be.visible');
        cy.get('.website-replay-info').should('not.exist');
        cy.get('.local-analyzer__file input').should('not.have.attr', 'multiple');
        cy.get('.local-analyzer__file input').selectFile('cypress/fixtures/52200.evf', { force: true });
        cy.get('.analyzer-progress-bar__slider', { timeout: 10000 }).should('have.attr', 'max', '10732').and('not.be.disabled');
        cy.get('.local-analyzer__filename').should('have.text', '52200.evf');
        cy.get('.analyzer-progress-bar__slider').invoke('val', 5000).trigger('input');
        cy.get('.local-analyzer__file input').selectFile('cypress/fixtures/52200.evf', { force: true });
        cy.get('.analyzer-progress-bar__slider').should('have.attr', 'max', '10732').and('not.be.disabled').and('have.value', '0');
        cy.get('@websiteApi.all').should('have.length', 0);
        cy.get('@softwareApi.all').should('have.length', 0);
    });

    it('reports unsupported files and can recover by selecting a supported replay', () => {
        mountLocalAnalyzer();
        cy.get('.local-analyzer__file input').selectFile({ contents: Cypress.Buffer.from('invalid'), fileName: 'invalid.zip' }, { force: true });
        cy.get('.video-analyzer-board__error').should('contain.text', 'Unsupported replay format');
        cy.get('.local-analyzer__file input').selectFile('cypress/fixtures/52200.evf', { force: true });
        cy.get('.analyzer-progress-bar__slider', { timeout: 10000 }).should('have.attr', 'max', '10732').and('not.be.disabled');
        cy.get('.video-analyzer-board__error').should('not.exist');
    });
});
