import { defineComponent, h } from 'vue';

import VideoInfoProgress from './VideoInfoProgress.vue';

import i18n from '@/i18n';
import { serviceConfig } from '@/services/store';
import { fetchVideoInfos } from '@/services/videoInfoService';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';
import { mockVideoInfo } from '@cy/support/videoInfo';

describe('<VideoInfoProgress />', () => {
    installHashHistoryCleanup();

    it('allows navigation during background downloads and hides progress on cache hits', () => {
        cy.clock(0, ['setTimeout', 'clearTimeout']);
        serviceConfig.value.videoInfoBatchSize = 1;
        serviceConfig.value.videoInfoBatchDelay = 500;
        const metadata = mockVideoInfo([{ id: 91001 }, { id: 91002 }]);
        const router = hashRouter({ initialPath: '/player/7/videos' });
        cy.mount(defineComponent({
            expose: [],
            render: () => h('div', [
                h('button', { onClick: () => {
                    void fetchVideoInfos(metadata);
                } }, 'Load'),
                h('button', { onClick: () => {
                    void router.push('/ranking');
                } }, 'Other page'),
                h('button', { onClick: () => {
                    void router.push('/player/7/videos');
                } }, 'Videos'),
                h(VideoInfoProgress),
            ]),
        }), { global: { plugins: [i18n, router] } });
        cy.contains('button', 'Load').click();
        cy.get('[role=status]').should('be.visible').and('contain.text', '0 / 2');
        cy.get('[role=dialog], .el-overlay').should('not.exist');
        cy.contains('button', 'Other page').click();
        cy.get('[role=status]').should('not.exist');
        cy.tick(500);
        cy.wait('@parsedVideoInfo');
        cy.contains('button', 'Videos').click();
        cy.get('[role=status]').should('contain.text', '1 / 2');
        cy.get('progress').should('have.attr', 'value', '1').and('have.attr', 'max', '2');
        cy.tick(500);
        cy.wait('@parsedVideoInfo');
        cy.get('[role=status]').should('not.exist');
        cy.contains('button', 'Load').click();
        cy.get('[role=status]').should('not.exist');
        cy.get('@parsedVideoInfo.all').should('have.length', 2);
    });

    afterEach(() => {
        serviceConfig.value.videoInfoBatchSize = 100;
        serviceConfig.value.videoInfoBatchDelay = 250;
    });
});
