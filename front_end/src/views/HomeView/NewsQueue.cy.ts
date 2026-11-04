import { defineComponent } from 'vue';
import { ElTabs } from 'element-plus';

import NewsQueue from './NewsQueue.vue';

import i18n from '@/i18n';
import { pinia } from '@/store/create';
import type { NewsEvent } from '@/services/newsService';

// NewsQueue 的根元素是 <ElTabPane>，而 ElTabPane 强制要求父级为 <ElTabs>；
// 直接用模板复刻 HomeView 的包裹结构，并显式 v-model 强制激活 news pane，
// 避免 Cypress 下经 slots 传入时 ElTabs 未能激活该 pane 的问题。
const Wrapper = defineComponent({
    components: { ElTabs, NewsQueue },
    data: () => ({ tab: 'news' }),
    template: '<el-tabs v-model="tab" type="border-card"><news-queue /></el-tabs>',
});

function mountNews(events: unknown[]) {
    cy.intercept('GET', '**/api/news/events**', events).as('news');
    cy.mount(Wrapper, { global: { plugins: [i18n, pinia] } });
    cy.wait('@news');
}

describe('<NewsQueue />', () => {
    it('renders every related replay for an LSF event with multiple triggers', () => {
        const events: NewsEvent[] = [{
            id: 'lsf-1', occurred_at: 1_000_000, player_id: 42, category: 'lsf',
            payload: {
                video_id: 8001,
                video_ids: [8001, 8002, 8003],
                old: { lsf: 1.0, rank: 5 },
                new: { lsf: 2.0, rank: 1 },
            },
        }];
        mountNews(events as unknown[]);
        cy.get('[data-cy=news-lsf]').should('exist');
        cy.get('[data-cy=news-lsf] a').should('have.length', 3);
        cy.get('[data-cy=news-lsf] a').eq(0).should('have.attr', 'href', '#/video/8001');
        cy.get('[data-cy=news-lsf] a').eq(1).should('have.attr', 'href', '#/video/8002');
        cy.get('[data-cy=news-lsf] a').eq(2).should('have.attr', 'href', '#/video/8003');
        cy.get('[data-cy=news-lsf]').should('contain.text', '→');
    });

    it('falls back to a single video_id for legacy LSF events without video_ids', () => {
        const legacy = {
            id: 'lsf-legacy', occurred_at: 1_000_000, player_id: 7, category: 'lsf',
            payload: { video_id: 555, old: null, new: { lsf: 2.0, rank: 1 } },
        };
        mountNews([legacy]);
        cy.get('[data-cy=news-lsf] a').should('have.length', 1);
        cy.get('[data-cy=news-lsf] a').first().should('have.attr', 'href', '#/video/555');
    });

    it('renders old and new replays for a PB event', () => {
        const events: NewsEvent[] = [{
            id: 'pb-1', occurred_at: 1_000_000, player_id: 9, category: 'pb',
            payload: {
                field: 'std:bt',
                old: { timems: 40000, video_id: 101, rank: 2 },
                new: { timems: 35000, video_id: 102, rank: 1 },
            },
        }];
        mountNews(events as unknown[]);
        cy.get('[data-cy=news-pb] a').should('have.length', 2);
        cy.get('[data-cy=news-pb] a').eq(0).should('have.attr', 'href', '#/video/101');
        cy.get('[data-cy=news-pb] a').eq(1).should('have.attr', 'href', '#/video/102');
    });

    it('shows the empty state when there are no events', () => {
        mountNews([]);
        cy.get('.news-empty').should('exist');
    });
});
