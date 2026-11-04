import NewsQueueHost from './NewsQueueHost.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { NewsEvent } from '@/services/newsService';
import { pinia } from '@/store/create';

// NewsQueue 的根元素是 <ElTabPane>，强制要求父级为 <ElTabs>。这里用一个 .vue 包裹组件
// （模板 <ElTabs><NewsQueue/></ElTabs>，与生产 HomeView/App.vue 同结构，由 Vite 编译），
// 避免 runtime-only 构建下 .ts 模板字符串无法编译、以及运行时 slots 选项的不确定性。
// NewsQueue 渲染包含 <PlayerName>，其依赖链会读取 proxy.$axios.defaults.baseURL，
// 组件测试不执行 main.ts，必须显式注入 $axios 并用 mockPlayerNameFallback 拦截其 API。
function mountNews(events: unknown[]) {
    cy.intercept('GET', '**/api/news/events**', { statusCode: 200, body: events }).as('news');
    cy.mockPlayerNameFallback();
    cy.mount(NewsQueueHost, {
        global: {
            plugins: [i18n, pinia],
            config: { globalProperties: { $axios } },
        },
    });
    cy.wait('@news');
}

describe('<NewsQueue />', () => {
    it('renders every related replay for an LSF event with multiple triggers', () => {
        const events: NewsEvent[] = [{
            id: 'lsf-1',
            occurred_at: 1_000_000,
            player_id: 42,
            category: 'lsf',
            payload: {
                video_id: 8001,
                video_ids: [8001, 8002, 8003],
                old: { lsf: 1.0, rank: 5 },
                new: { lsf: 2.0, rank: 1 },
            },
        }];
        mountNews(events);
        cy.get('[data-cy=news-lsf]').should('exist');
        cy.get('[data-cy=news-lsf] a').should('have.length', 3);
        cy.get('[data-cy=news-lsf] a').eq(0).should('have.attr', 'href', '#/video/8001');
        cy.get('[data-cy=news-lsf] a').eq(1).should('have.attr', 'href', '#/video/8002');
        cy.get('[data-cy=news-lsf] a').eq(2).should('have.attr', 'href', '#/video/8003');
        cy.get('[data-cy=news-lsf]').should('contain.text', '→');
    });

    it('falls back to a single video_id for legacy LSF events without video_ids', () => {
        const legacy = {
            id: 'lsf-legacy',
            occurred_at: 1_000_000,
            player_id: 7,
            category: 'lsf',
            payload: { video_id: 555, old: null, new: { lsf: 2.0, rank: 1 } },
        };
        mountNews([legacy]);
        cy.get('[data-cy=news-lsf] a').should('have.length', 1);
        cy.get('[data-cy=news-lsf] a').first().should('have.attr', 'href', '#/video/555');
    });

    it('renders old and new replays for a PB event', () => {
        const events: NewsEvent[] = [{
            id: 'pb-1',
            occurred_at: 1_000_000,
            player_id: 9,
            category: 'pb',
            payload: {
                field: 'std:bt',
                old: { timems: 40000, video_id: 101, rank: 2 },
                new: { timems: 35000, video_id: 102, rank: 1 },
            },
        }];
        mountNews(events);
        cy.get('[data-cy=news-pb] a').should('have.length', 2);
        cy.get('[data-cy=news-pb] a').eq(0).should('have.attr', 'href', '#/video/101');
        cy.get('[data-cy=news-pb] a').eq(1).should('have.attr', 'href', '#/video/102');
    });

    it('shows the empty state when there are no events', () => {
        mountNews([]);
        cy.get('.news-empty').should('exist');
    });
});
