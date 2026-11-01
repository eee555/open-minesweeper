import { defineComponent, h, ref, shallowRef } from 'vue';

import VideoAnalyzer from './App.vue';
import { defaultAnalyzerConfig } from './config';
import type { ReplaySource } from './replayParser';
import type { AnalyzerState } from './useAnalyzerState';

import i18n from '@/i18n';
import { captureAnalyzerState } from '@cy/support/analyzerState';

describe('<VideoAnalyzer /> raw-source interface', () => {
    it('keeps replay samples cached while changing layer visibility and opacity', () => {
        cy.viewport(1280, 1000);
        const config = ref(defaultAnalyzerConfig());
        const originalConfig = config.value;
        let state: AnalyzerState;
        cy.fixture('52200.evf', 'binary').then((binary: string) => {
            const source: ReplaySource = { data: Uint8Array.from(binary, (character) => character.charCodeAt(0)).buffer, filename: 'local.evf', software: 'e' };
            cy.mount(defineComponent({ expose: [],
                render: () => h('div', { style: { width: '900px', height: '800px' } }, [h(VideoAnalyzer, {
                    source,
                    config: config.value,
                    'onUpdate:config': (value) => {
                        config.value = value;
                    },
                    probabilityColorScheme: { colors: ['#000', '#fff'], thresholds: [50] },
                })]) }), { global: { plugins: [i18n],
                mixins: [captureAnalyzerState((value) => {
                    state = value;
                })] } }).then(() => {
                const counters = state.preparedCounters.value;
                const events = state.preparedEvents.value;
                const frame = state.frame.value;
                cy.get('.video-analyzer-board__global-toggle').click();
                cy.get('.video-analyzer-board__global-toggle').should('have.attr', 'aria-pressed', 'true');
                cy.get('.video-analyzer-board__probability-toggle').click();
                cy.get('.video-analyzer-board__probability-toggle').should('have.attr', 'aria-pressed', 'false');
                cy.get('.video-analyzer-board__cursor-toggle').click();
                cy.get('.video-analyzer-board__cursor-toggle').should('have.attr', 'aria-pressed', 'false');
                cy.get('.video-analyzer-board__trace-toggle').click();
                cy.get('.video-analyzer-board__trace-toggle').should('have.attr', 'aria-pressed', 'true');
                cy.get('.video-analyzer-board__global-control .board-settings-control__handle').click();
                cy.get('.board-layer-control__opacity:visible').invoke('val', 0.4).trigger('input');
                cy.get('.board-layer-control__opacity:visible').trigger('keydown', { key: 'Escape' });
                cy.then(() => {
                    expect(config.value).to.eq(originalConfig);
                    expect(config.value.globalVisible).to.eq(true);
                    expect(config.value.probabilityVisible).to.eq(false);
                    expect(config.value.traceVisible).to.eq(true);
                    expect(config.value.cursorVisible).to.eq(false);
                    expect(config.value.globalOpacity).to.eq(0.4);
                    expect(state.preparedCounters.value).to.eq(counters);
                    expect(state.preparedEvents.value).to.eq(events);
                    expect(state.frame.value).to.eq(frame);
                    expect(state.config.value).to.eq(originalConfig);
                });
            });
        });
    });

    it('accepts bytes without site requests, keeps instance settings separate and omits absent information', () => {
        cy.viewport(1280, 1000);
        cy.intercept('GET', '**/api/video/**', { statusCode: 500 }).as('siteReplay');
        cy.fixture('52200.evf', 'binary').then((binary: string) => {
            const source = shallowRef<ReplaySource>({ data: Uint8Array.from(binary, (character) => character.charCodeAt(0)).buffer, filename: 'local.evf', software: 'e' });
            const colors = { colors: ['#000', '#fff'], thresholds: [50] };
            cy.mount(defineComponent({ expose: [],
                render: () => h('div', { class: 'local-analyzer-test' }, [
                    h('div', { style: { width: '900px', height: '480px' } }, [h(VideoAnalyzer, { source: source.value, probabilityColorScheme: colors, title: 'Local replay' })]),
                    h('div', { style: { width: '900px', height: '480px' } }, [h(VideoAnalyzer, { source: source.value, probabilityColorScheme: colors }, { info: () => [h('span', 'Custom file details')] })]),
                ]) }), { global: { plugins: [i18n] } });
            cy.get('.analyzer-progress-bar__slider').should('have.length', 2).each(($slider) => {
                cy.wrap($slider).should('have.attr', 'max', '10732');
            });
            cy.get('.video-analyzer-view').first().find('.video-analyzer-info').should('not.exist');
            cy.get('.video-analyzer-info').should('have.length', 1).and('have.text', 'Custom file details');
            cy.get('.video-analyzer-view__toolbar').should('not.exist');
            cy.get('.video-analyzer-view h1').should('not.exist');
            cy.get('.video-analyzer-view').first().find('.video-analyzer-board__layout-control button').click();
            cy.get('.video-analyzer-view__layout-select:visible').select('counter-top');
            cy.get('.video-analyzer-view').last().find('.video-analyzer-board__layout-control button').click();
            cy.get('.video-analyzer-view__layout-select:visible').should('have.value', 'auto').trigger('keydown', { key: 'Escape' });
            cy.get('.video-analyzer-counter__settings').first().click();
            cy.get('.video-analyzer-counter__label-width').clear();
            cy.get('.video-analyzer-counter__label-width').type('120');
            cy.get('.video-analyzer-counter__apply').click();
            cy.get('.video-analyzer-counter').first().find('col').first().should('have.css', 'width', '120px');
            cy.get('.video-analyzer-counter').last().find('col').first().should('have.css', 'width', '80px');
            cy.get('.analyzer-progress-bar__slider').first().invoke('val', 5000).trigger('input');
            cy.get('.analyzer-progress-bar__range-start').first().click();
            cy.get('.analyzer-progress-bar__slider').last().should('have.value', '0');
            cy.then(() => {
                source.value = { ...source.value };
            });
            cy.get('.analyzer-progress-bar__slider').first().should('have.value', '0');
            cy.get('.analyzer-progress-bar__range-time').first().should('have.text', '[0.000, 10.732] s');
            cy.get('@siteReplay.all').should('have.length', 0);
        });
    });
});
