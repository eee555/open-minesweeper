import NewsQueueHost from './NewsQueueHost.vue';

import $axios from '@/http';
import i18n from '@/i18n';
import type { NewsEvent } from '@/services/newsService';
import { pinia } from '@/store/create';
import { hashRouter, installHashHistoryCleanup } from '@cy/support/hashHistory';
import { mockVideoInfo } from '@cy/support/videoInfo';

// NewsQueue 的根元素是 <ElTabPane>，强制要求父级为 <ElTabs>。这里用一个 .vue 包裹组件
// （模板 <ElTabs><NewsQueue/></ElTabs>，与生产 HomeView/App.vue 同结构，由 Vite 编译），
// 避免 runtime-only 构建下 .ts 模板字符串无法编译、以及运行时 slots 选项的不确定性。
// NewsQueue 渲染包含 <PlayerName>，其依赖链会读取 proxy.$axios.defaults.baseURL，
// 组件测试不执行 main.ts，必须显式注入 $axios 并用 mockPlayerNameFallback 拦截其 API；
// PlayerName 的 RouterLink 还需要 vue-router 实例，故用 hashRouter 注入并清理 history。

// VideoPreviewLink 默认开启软件图标，会批量拉取录像信息；这里按事件里出现的 video id
// 提供 mock，覆盖 PB 的前后两个成绩与 LSF 的多个共同提升录像。
function newsVideoRows(events: unknown[]): Record<string, unknown>[] {
    const ids = new Set<number>();
    const add = (value: unknown) => {
        if (typeof value === 'number' && value > 0) ids.add(value);
    };
    for (const event of events) {
        const { payload } = event as { payload?: Record<string, unknown> };
        if (payload === undefined) continue;
        for (const key of ['old', 'new']) {
            const record = payload[key];
            if (record !== null && typeof record === 'object') add((record as Record<string, unknown>).video_id);
        }
        add(payload.video_id);
        if (Array.isArray(payload.video_ids)) {
            for (const id of payload.video_ids as unknown[]) add(id);
        }
    }
    return [...ids].map((id) => ({ id, software: 'e' }));
}

function mountNews(events: unknown[]) {
    mockVideoInfo(newsVideoRows(events));
    cy.intercept('GET', '**/api/news/events**', { statusCode: 200, body: events }).as('news');
    cy.mockPlayerNameFallback();
    const router = hashRouter({ initialPath: '/' });
    cy.wrap(router.isReady()).then(() => {
        cy.mount(NewsQueueHost, {
            global: {
                plugins: [i18n, pinia, router],
                config: { globalProperties: { $axios } },
            },
        });
    });
    cy.wait('@news');
}

describe('<NewsQueue />', () => {
    installHashHistoryCleanup();

    beforeEach(() => {
        i18n.global.locale.value = 'en';
    });

    it('renders the Chinese sentence examples', () => {
        i18n.global.locale.value = 'zh-cn';
        const events: NewsEvent[] = [
            {
                id: 'pb-zh',
                occurred_at: 1_000_000,
                player_id: 9,
                category: 'pb',
                payload: {
                    field: 'std:e:170',
                    old: { timems: 100000, video_id: 101, rank: 7 },
                    new: { timems: 90000, video_id: 102, rank: 6 },
                },
            },
            {
                id: 'lsf-zh',
                occurred_at: 1_000_000,
                player_id: 42,
                category: 'lsf',
                payload: {
                    video_id: 12345,
                    video_ids: [12345],
                    old: { lsf: 1234, rank: 5 },
                    new: { lsf: 1235, rank: 4 },
                },
            },
        ];
        mountNews(events);
        cy.get('[data-cy=news-pb]').should('contain.text', '打破了高级170PB：100.000(7) → 90.000(6)');
        cy.get('[data-cy=news-lsf]').should('contain.text', '#12345提升了');
        cy.get('[data-cy=news-lsf]').should('contain.text', '的LSF：1234.00(5) → 1235.00(4)');
    });

    it('links every replay that jointly raised the LSF and formats values to two decimals', () => {
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
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').should('have.length', 3);
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').eq(0).
            should('contain.text', '#8001').
            and('have.attr', 'href', '#/video/8001');
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').eq(1).
            should('contain.text', '#8002').
            and('have.attr', 'href', '#/video/8002');
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').eq(2).
            should('contain.text', '#8003').
            and('have.attr', 'href', '#/video/8003');
        cy.get('[data-cy=news-lsf]').should('contain.text', '1.00(5) → 2.00(1)');
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
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').should('have.length', 1);
        cy.get('[data-cy=news-lsf] .news-sentence .video-preview-link').first().
            should('contain.text', '#555').
            and('have.attr', 'href', '#/video/555');
        cy.get('[data-cy=news-lsf]').should('contain.text', '2.00(1)');
    });

    it('links both PB times to their own replays', () => {
        const events: NewsEvent[] = [{
            id: 'pb-1',
            occurred_at: 1_000_000,
            player_id: 9,
            category: 'pb',
            payload: {
                field: 'std:b:10',
                old: { timems: 40000, video_id: 201, rank: 2 },
                new: { timems: 35000, video_id: 202, rank: 1 },
            },
        }];
        mountNews(events);
        cy.get('[data-cy=news-pb] .news-sentence .video-preview-link').should('have.length', 2);
        cy.get('[data-cy=news-pb] .news-sentence .video-preview-link').eq(0).
            should('contain.text', '40.000').
            and('have.attr', 'href', '#/video/201');
        cy.get('[data-cy=news-pb] .news-sentence .video-preview-link').eq(1).
            should('contain.text', '35.000').
            and('have.attr', 'href', '#/video/202');
        cy.get('[data-cy=news-pb]').should('contain.text', '40.000(2) → 35.000(1)');
    });

    it('renders efficiency news in the PB sentence shape with per-record replay links', () => {
        i18n.global.locale.value = 'zh-cn';
        const events: NewsEvent[] = [
            {
                id: 'eff-1',
                occurred_at: 1_000_000,
                player_id: 9,
                category: 'eff',
                payload: {
                    field: 'thrp:e',
                    old: { value: 0.8, video_id: 301, rank: 7 },
                    new: { value: 0.9, video_id: 302, rank: 6 },
                },
            },
            {
                id: 'eff-2',
                occurred_at: 1_000_000,
                player_id: 10,
                category: 'eff',
                payload: {
                    field: 'nf_ioe:sum',
                    old: null,
                    new: { value: 1.5, video_id: null, rank: 2 },
                },
            },
        ];
        mountNews(events);
        cy.get('[data-cy=news-eff]').eq(0).should('contain.text', '打破了ThrP高级纪录：0.800(7) → 0.900(6)');
        cy.get('[data-cy=news-eff]').eq(0).find('.video-preview-link').should('have.length', 2);
        cy.get('[data-cy=news-eff]').eq(0).find('.video-preview-link').eq(0).
            should('contain.text', '0.800').
            and('have.attr', 'href', '#/video/301');
        cy.get('[data-cy=news-eff]').eq(0).find('.video-preview-link').eq(1).
            should('contain.text', '0.900').
            and('have.attr', 'href', '#/video/302');
        cy.get('[data-cy=news-eff]').eq(1).should('contain.text', '首次取得NF IOE总计纪录：1.500(2)');
        cy.get('[data-cy=news-eff]').eq(1).find('.video-preview-link').should('not.exist');
    });

    it('formats efficiency field names in English', () => {
        const events: NewsEvent[] = [{
            id: 'eff-en',
            occurred_at: 1_000_000,
            player_id: 9,
            category: 'eff',
            payload: {
                field: 'thrp:e_nf',
                old: null,
                new: { value: 1.0, video_id: 401, rank: 1 },
            },
        }];
        mountNews(events);
        cy.get('[data-cy=news-eff]').should('contain.text', 'set their first ThrP Expert NF record: 1.000(1)');
    });

    it('shows software icons and aligns player names, replay links and text on one baseline', () => {
        // fetchVideoInfo 的 infoRequests / pending 是模块级缓存；用一个其它用例从未用过的 id，
        // 确保本用例真的发起 staticdetailbatch 请求，而不是复用上一用例挂起的 promise。
        const events: NewsEvent[] = [{
            id: 'pb-icons',
            occurred_at: 1_000_000,
            player_id: 9,
            category: 'pb',
            payload: {
                field: 'std:b:10',
                old: null,
                new: { timems: 35000, video_id: 91001, rank: 1 },
            },
        }];
        mountNews(events);
        cy.get('[data-cy=news-pb] .video-preview-software').should('have.length', 1);
        cy.get('[data-cy=news-pb] .video-preview-link').should('have.css', 'vertical-align', 'baseline');
        cy.get('[data-cy=news-pb] .player-name').parent().should('have.css', 'vertical-align', 'baseline');
        cy.get('[data-cy=news-pb] .player-name').should('have.css', 'vertical-align', 'baseline');
        cy.get('[data-cy=news-pb] .player-name a span').should('have.css', 'vertical-align', 'baseline');
        // 名称文字与句子里的普通文字应落在同一条基线上。
        cy.get('[data-cy=news-pb] .news-sentence').should(($sentence) => {
            const [root] = $sentence.toArray();
            const name = root.querySelector('.player-name a span');
            let plain: Text | undefined;
            for (const node of Array.from(root.childNodes)) {
                if (node.nodeType === Node.TEXT_NODE && (node.textContent ?? '').trim()) {
                    plain = node as Text;
                    break;
                }
            }
            if (name === null || plain === undefined) throw new Error('新闻句子缺少可比较的文本');
            const range = document.createRange();
            range.selectNodeContents(plain);
            const offset = Math.abs(range.getBoundingClientRect().bottom - name.getBoundingClientRect().bottom);
            expect(offset, '玩家名与普通文字的基线偏移').to.be.lessThan(2);
        });
    });

    it('shows the empty state when there are no events', () => {
        mountNews([]);
        cy.get('.news-empty').should('exist');
    });

    it('leaves refresh controls to the parent tab header', () => {
        mountNews([]);
        cy.get('.el-tabs__item button').should('not.exist');
        cy.get('.news-toolbar').should('not.exist');
    });
});
