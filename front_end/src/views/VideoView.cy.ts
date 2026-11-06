import VideoView from './VideoView.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import { videofilter } from '@/store';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';

describe('<VideoView />', () => {
    installHashHistoryCleanup();

    it('sorts the STNB column through iqg in both directions', () => {
        cy.viewport(600, 500);
        cy.intercept({ method: 'GET', pathname: '/api/video/query' }, { body: { count: 0, videos: [] } }).as('videos');
        cy.mount(VideoView, { global: { plugins: [i18n, pinia, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait('@videos').its('request.query').should('include', { o: 'timems' });

        cy.contains('th', 'STNB').click();
        cy.wait('@videos').its('request.query').should('include', { o: 'iqg', r: 'true' });
        cy.contains('th', 'STNB').click();
        cy.wait('@videos').its('request.query').should('include', { o: 'iqg', r: 'false' });
    });

    it('requests the updated state filter once for each checkbox activation', () => {
        videofilter.value.filter_state = ['a', 'b', 'c', 'd'];
        cy.intercept({ method: 'GET', pathname: '/api/video/query' }, { body: { count: 0, videos: [] } }).as('videos');
        cy.mount(VideoView, { global: { plugins: [i18n, pinia, hashRouter()], config: { globalProperties: { $axios } } } });
        cy.wait('@videos');
        cy.contains('label', 'Valid').click();
        cy.wait('@videos').its('request.url').should((url: string) => {
            expect(new URL(url).searchParams.getAll('s[]')).to.deep.equal(['a', 'b', 'd']);
        });
        cy.get('@videos.all').should('have.length', 2);
        cy.contains('label', 'Valid').find('input').should('not.be.checked').focus();
        cy.realPress('Space');
        cy.wait('@videos').its('request.url').should((url: string) => {
            expect(new URL(url).searchParams.has('s[]')).to.equal(false);
        });
        cy.get('@videos.all').should('have.length', 3);
    });

    it('requests the updated NF filter once per mouse or keyboard activation and only then resets pagination', () => {
        videofilter.value.pagesize = 20;
        cy.intercept({ method: 'GET', pathname: '/api/video/query' }, {
            body: { count: 21, videos: [] },
        }).as('videos');
        cy.mount(VideoView, { global: { plugins: [i18n, pinia, hashRouter()], config: { globalProperties: { $axios } } } });

        cy.wait('@videos').its('request.query').should('include', { nf: 'false', page: '1' });
        cy.get('[data-cy=nf-only] input').should('not.be.checked');
        cy.get('.el-pagination .btn-next').click();
        cy.wait('@videos').its('request.query').should('include', { nf: 'false', page: '2' });

        cy.get<{ vm: { nfOnly: boolean } }>('@vue').then((wrapper) => {
            const { vm } = wrapper;
            vm.nfOnly = true;
        });
        cy.get('[data-cy=nf-only] input').should('be.checked');
        cy.get('.el-pagination .el-pager .is-active').should(($page) => {
            expect($page.text().trim()).to.equal('2');
        });
        cy.get('@videos.all').should('have.length', 2);

        cy.get('[data-cy=nf-only]').click();
        cy.wait('@videos').its('request.query').should('include', { nf: 'false', page: '1' });
        cy.get('[data-cy=nf-only] input').should('not.be.checked');
        cy.get('@videos.all').should('have.length', 3);
        cy.get('.el-pagination .btn-next').click();
        cy.wait('@videos').its('request.query').should('include', { nf: 'false', page: '2' });

        cy.get('[data-cy=nf-only] input').focus();
        cy.realPress('Space');
        cy.wait('@videos').its('request.query').should('include', { nf: 'true', page: '1' });
        cy.get('[data-cy=nf-only] input').should('be.checked');
        cy.get('.el-pagination .el-pager .is-active').should(($page) => {
            expect($page.text().trim()).to.equal('1');
        });
        cy.get('@videos.all').should('have.length', 5);
    });
});
