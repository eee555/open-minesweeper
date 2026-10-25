import DiskUsage from './DiskUsage.vue';
import TaskSummary from './TaskSummary.vue';
import VideoSummary from './VideoSummary.vue';

import $axios from '@/http';
import i18n from '@/i18n';

const global = {
    plugins: [i18n],
    config: { globalProperties: { $axios } },
};
const disk = { sampled_at: '2026-10-25T12:00:00Z', total: 8192, used: 6144, free: 2048, video: 3072, db: 1024 };
const tasks = { sampled_at: '2026-10-25T12:00:00Z', total: 1000, status: { READY: 100, RUNNING: 100, SUCCESSFUL: 700, FAILED: 100 } };
const videos = {
    sampled_at: '2026-10-25T12:00:00Z',
    total: 1000,
    software: { a: 100, e: 200, m: 300, r: 400 },
    level: { b: 200, i: 200, e: 200, c8_8_40: 400 },
    mode: { '00': 500, '01': 0, '04': 0, '05': 100, '07': 100, '08': 100, '09': 100, 10: 100, 11: 0 },
    state: { a: 100, b: 100, c: 700, d: 100, e: 0 },
};

function waitForChartLayout() {
    return cy.window().then((window) => new Cypress.Promise<void>((resolve) => {
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                resolve();
            });
        });
    }));
}

describe('Server statistics cards', () => {
    const originalLocale = i18n.global.locale.value;
    afterEach(() => {
        i18n.global.locale.value = originalLocale;
    });

    it('uses the same donut layout for disk space and counts free space only once', () => {
        cy.mount(DiskUsage, { global, props: { section: disk } });
        cy.get('.vue-data-ui-legend-item').should('have.length', 4);
        cy.contains('.vue-data-ui-legend-item', 'Videos').should('contain.text', '3.00 KB').and('contain.text', '37.5%');
        cy.contains('.vue-data-ui-legend-item', 'Database').should('contain.text', '1.00 KB').and('contain.text', '12.5%');
        cy.contains('.vue-data-ui-legend-item', 'Other').should('contain.text', '2.00 KB').invoke('text').should('match', /25(?:\.0)?%/);
        cy.contains('.vue-data-ui-legend-item', 'Free').should('contain.text', '2.00 KB').invoke('text').should('match', /25(?:\.0)?%/);
        cy.get('.statistics-total').should('contain.text', 'Total: 8.00 KB');
    });

    it('handles an empty video database and rejects overlapping disk categories', () => {
        cy.mount(DiskUsage, { global, props: { section: { ...disk, video: null, db: null } } });
        cy.contains('.vue-data-ui-legend-item', 'Videos').should('contain.text', '0 B');
        cy.contains('.vue-data-ui-legend-item', 'Other').should('contain.text', '6.00 KB');
        cy.get<ComponentWrapper<typeof DiskUsage>>('@vue').then((wrapper) => wrapper.setProps({ section: { ...disk, video: disk.total } }));
        cy.get('[role="alert"]').should('contain.text', 'last successful result');
        cy.contains('.vue-data-ui-legend-item', 'Other').should('contain.text', '6.00 KB');
        cy.contains('button', 'Refresh').should('not.be.disabled');
    });

    it('shows task counts without byte units and updates translated status labels', () => {
        cy.mount(TaskSummary, { global, props: { section: tasks } });
        cy.get('.statistics-total').should('contain.text', 'Total: 1,000').and('not.contain.text', 'KB');
        cy.contains('.vue-data-ui-legend-item', 'Successful').should('contain.text', '700').invoke('text').should('match', /70(?:\.0)?%/);
        cy.then(() => {
            i18n.global.locale.value = 'zh-cn';
        });
        cy.contains('h2', '后台任务').should('be.visible');
        cy.contains('.vue-data-ui-legend-item', '已完成').should('be.visible');
        cy.contains('.vue-data-ui-legend-item', '失败').should('be.visible');
    });

    it('shows an explicit zero task total', () => {
        cy.mount(TaskSummary, { global, props: { section: { ...tasks, total: 0, status: { READY: 0, RUNNING: 0, SUCCESSFUL: 0, FAILED: 0 } } } });
        cy.get('[role="status"]').should('contain.text', 'zero');
        cy.get('.statistics-total').should('contain.text', 'Total: 0');
        cy.get('.vue-ui-donut').should('not.exist');
    });

    it('shows all video dimensions and omits unsupported modes and verification states', () => {
        cy.mount(VideoSummary, { global, props: { section: videos } });
        cy.get('.statistics-total').should('contain.text', 'Total: 1,000');
        const activeLegend = '.video-panel[aria-hidden="false"] .vue-data-ui-legend-item';
        cy.get(activeLegend).should('have.length', 4);
        cy.contains(activeLegend, 'Avf:').should('contain.text', '100');
        cy.contains('.video-dimensions button', 'Level').click();
        cy.contains('.video-dimensions button', 'Level').should('have.attr', 'aria-pressed', 'true');
        cy.contains(activeLegend, '8x8/40').should('contain.text', '400').invoke('text').should('match', /40(?:\.0)?%/);
        cy.contains('.video-dimensions button', 'Mode').click();
        cy.get(activeLegend).should('have.length', 7).and('not.contain.text', 'UPK').and('not.contain.text', 'Win7').and('not.contain.text', 'Recursive');
        cy.contains(activeLegend, 'Strong Guessing').should('be.visible');
        cy.contains('.video-dimensions button', 'State').click();
        cy.get(activeLegend).should('have.length', 4);
        cy.contains(activeLegend, '700').should('be.visible');
    });

    for (const language of ['en', 'zh-cn'] as const) {
        for (const width of [420, 260]) {
            it(`keeps video card height stable across dimensions at ${width}px in ${language}`, () => {
                let deferredResizeNotifications = 0;
                // The browser can defer a resize notification to the next paint. Only tolerate this
                // exact notification here, and verify below that it stops once layout has settled.
                // https://developer.mozilla.org/en-US/docs/Web/API/ResizeObserver#observation_errors
                cy.on('uncaught:exception', (error) => {
                    if (error.message.includes('ResizeObserver loop completed with undelivered notifications.')) {
                        deferredResizeNotifications++;
                        return false;
                    }
                });
                cy.viewport(width, 1000);
                cy.then(() => {
                    i18n.global.locale.value = language;
                });
                cy.mount(VideoSummary, { global, props: { section: videos } });
                cy.get('.video-panel').should('have.length', 4);
                cy.get('.video-panel .vue-data-ui-legend').should('have.length', 4);
                cy.get('h2').should('contain.text', language === 'en' ? 'Video Statistics' : '录像统计');
                cy.get('.video-panel[data-dimension="mode"] .vue-data-ui-legend-item').should('have.length', 7);
                waitForChartLayout();
                cy.get('[data-statistic="videos"]').then(($card) => {
                    const { height } = $card[0].getBoundingClientRect();
                    for (const index of [0, 1, 2, 3, 0]) {
                        cy.get('.video-dimensions button').eq(index).click();
                        cy.get('.video-dimensions button').eq(index).should('have.attr', 'aria-pressed', 'true');
                        cy.get('.video-panel[aria-hidden="false"]').should('have.length', 1).and('be.visible').and('not.have.attr', 'inert');
                        cy.get('.video-panel[aria-hidden="true"]').should('have.length', 3).each(($panel) => {
                            expect($panel).to.have.css('visibility', 'hidden');
                            expect($panel).to.have.attr('inert');
                        });
                        waitForChartLayout();
                        cy.get('[data-statistic="videos"]').should(($current) => {
                            expect($current[0].getBoundingClientRect().height).to.be.closeTo(height, 0.5);
                        });
                    }
                });
                cy.then(() => {
                    const settledNotifications = deferredResizeNotifications;
                    waitForChartLayout().then(() => {
                        expect(deferredResizeNotifications, 'resize notifications stop after layout settles').to.equal(settledNotifications);
                    });
                });
            });
        }
    }
});
