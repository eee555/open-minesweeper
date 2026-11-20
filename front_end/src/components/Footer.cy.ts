import Footer from './Footer.vue';

import i18n from '@/i18n';

const mountOptions = { global: { plugins: [i18n] } };

describe('<Footer />', () => {
    it('renders friendly links', () => {
        cy.mount(Footer, mountOptions);

        for (const [label, href] of [
            ['扫雷网 saolei.wang', 'http://saolei.wang'],
            ['Authoritative Minesweeper', 'https://minesweepergame.com'],
            ['Minesweeper.Online', 'https://minesweeper.online'],
            ['扫雷联萌 League of Minesweeper', 'http://tapsss.com'],
            ['Scoreganizer', 'https://scoreganizer.net'],
        ] as const) {
            cy.contains('a', label).should('have.attr', 'href', href).and('have.attr', 'target', '_blank');
        }
    });

    it('renders copyright section', () => {
        cy.mount(Footer, mountOptions);

        cy.contains('Copyright @ 2023');
        cy.contains('footer', 'All rights reserved');
        cy.contains('开源扫雷网 openms.top').should('have.attr', 'href', 'http://openms.top');
        cy.contains('苏ICP备2023056839号-1').should('have.attr', 'href', 'https://beian.miit.gov.cn/');
        cy.contains('苏公网安备32020602001691').should('have.attr', 'href', 'https://beian.mps.gov.cn/#/query/webSearch?code=32020602001691').and('have.attr', 'target', '_blank');
    });
});
