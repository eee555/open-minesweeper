import { defineComponent, h, ref, shallowRef, watch } from 'vue';

import { defaultAnalyzerConfig } from './config';
import { counterVariables, defaultCounterConfig } from './counter';
import type { CounterConfig, CounterEvent, CounterValues } from './counter';
import CounterPanel from './CounterPanel.vue';
import { provideAnalyzerState } from './useAnalyzerState';
import type { AnalyzerState } from './useAnalyzerState';
import { usePlayback } from './usePlayback';

import i18n from '@/i18n';
import { createAnalyzerTestState } from '@cy/support/analyzerState';

function singleCounterConfig(): CounterConfig {
    return { ...defaultCounterConfig(), rows: [{ key: 'bvs', expression: 'bbbv_solved / time', format: '.3f', samplingMode: 'button' as const }] };
}

function mountCounter(config = singleCounterConfig(), slotNames: string[] = []) {
    const events: CounterEvent[] = [0, 1, 2].map((index) => ({ timeMs: index * 1000,
        eventIndex: index,
        button: true,
        boardChanged: true,
        values: { ...Object.fromEntries(counterVariables.map((key) => [key, index * 4])) as CounterValues, time: index } }));
    const update = cy.spy().as('update');
    let state: AnalyzerState;
    return cy.mount(defineComponent({
        setup() {
            const settings = ref(defaultAnalyzerConfig());
            settings.value.counter = config;
            settings.value.timeline = { slots: slotNames.map(() => []), slotSettings: slotNames.map((name) => ({ name, height: 160 })) };
            const playback = usePlayback(2000);
            playback.seek(1000);
            state = createAnalyzerTestState({ config: settings, counterEvents: shallowRef(events), playback });
            provideAnalyzerState(state);
            watch(() => settings.value.counter, (value) => {
                update(value);
            });
            return () => h(CounterPanel);
        },
    }), { global: { plugins: [i18n], stubs: { transition: false } } }).then((mounted) => {
        cy.get('.video-analyzer-counter').parent().invoke('css', { height: '240px', width: '220px' });
        // This fixture fits six rows per column. The initial RAF reflow can remount row menus.
        cy.get('.video-analyzer-counter__column').should('have.length', Math.ceil(config.rows.length / 6));
        cy.get('.video-analyzer-counter__column').first().find('tr').should('have.length', Math.min(6, config.rows.length));
        return cy.wrap({ ...mounted, state });
    });
}

function openRowMenu(key: string) {
    const label = `.video-analyzer-counter__label > span[title="${key}"]`;
    cy.get(label).parent().find('.video-analyzer-counter__handle').scrollIntoView();
    cy.get(label).parent().find('.video-analyzer-counter__handle').click();
    cy.get('.video-analyzer-counter__menu:visible').should('have.length', 1);
}

describe('<CounterPanel />', () => {
    it('sends the original key to the selected slot every time without editing counter configuration', () => {
        mountCounter(singleCounterConfig(), ['First', 'Second']).then(({ state }) => {
            for (const slot of ['1', '1', '0']) {
                openRowMenu('bvs');
                cy.get('.video-analyzer-counter__send-to-slot:visible').should('have.attr', 'aria-label', 'Send to plot').select(slot);
            }
            cy.then(() => {
                expect(state.config.value.timeline.slots.map((slot) => slot.map((track) => track.key))).to.deep.eq([['bvs'], ['bvs', 'bvs']]);
            });
            cy.get('@update').should('not.have.been.called');
        });
    });

    it('disables sending when no slot exists', () => {
        mountCounter();
        openRowMenu('bvs');
        cy.get('.video-analyzer-counter__send-to-slot:visible').should('be.disabled');
    });

    it('fills columns downwards, scrolls horizontally, and keeps the footer outside the scroll area', () => {
        const config = singleCounterConfig();
        config.rows = Array.from({ length: 20 }, (_, index) => ({ ...config.rows[0], key: `row-${index}`, expression: 'left' }));
        mountCounter(config);
        cy.get('.video-analyzer-counter__column').should('have.length.greaterThan', 1);
        cy.get('.video-analyzer-counter tr').should('have.length', 20).and(($rows) => {
            expect([...$rows].map((entry) => entry.querySelector('.video-analyzer-counter__label > span:last-child')?.textContent?.trim())).to.deep.eq(config.rows.map((row) => row.key));
        });
        cy.get('.video-analyzer-counter__rows').should(($rows) => {
            expect($rows[0].scrollWidth).to.be.greaterThan($rows[0].clientWidth);
            expect($rows[0].scrollHeight).to.be.at.most($rows[0].clientHeight);
        });
        cy.get('.video-analyzer-counter__actions').should('be.visible').and(($actions) => {
            expect($actions.closest('.video-analyzer-counter__rows')).to.have.length(0);
        }).and('have.css', 'border-top-width', '0px');
        cy.get('.video-analyzer-counter').parent().invoke('css', 'height', '400px');
        cy.get('.video-analyzer-counter__column').first().find('tr').should('have.length.greaterThan', 8);
    });

    it('updates with time and shows expression errors instead of fallback values', () => {
        const config = singleCounterConfig();
        config.rows[0].expression = 'left';
        mountCounter(config).then(({ state }) => {
            cy.get('.video-analyzer-counter__value').should('have.text', '4.000');
            cy.then(() => {
                state.playback.seek(1500);
            });
            cy.get('.video-analyzer-counter__value').should('have.text', '6.000');
            cy.then(() => {
                state.config.value.counter = { ...config, rows: [{ ...config.rows[0], expression: 'bbbv_s' }] };
            });
            cy.get('.video-analyzer-counter__value').should('have.class', 'text-danger').and('contain.text', 'Unknown variable: bbbv_s');
        });
    });

    it('edits column widths without bounds and does not commit cancelled changes', () => {
        mountCounter();
        cy.get('.video-analyzer-counter__settings').click();
        cy.get('.video-analyzer-counter__label-width').clear();
        cy.get('.video-analyzer-counter__label-width').type('0');
        cy.get('.video-analyzer-counter__cancel').click();
        cy.get('.video-analyzer-counter__form').should('not.exist');
        cy.get('@update').should('not.have.been.called');
        cy.get('.video-analyzer-counter__settings').click();
        cy.get('.video-analyzer-counter__label-width').clear();
        cy.get('.video-analyzer-counter__label-width').type('123');
        cy.get('.video-analyzer-counter__value-width').clear();
        cy.get('.video-analyzer-counter__value-width').type('64');
        cy.get('.video-analyzer-counter__apply').click();
        cy.get('@update').should('have.been.calledOnceWithExactly', { ...singleCounterConfig(), thWidth: 123, tdWidth: 64 });
    });

    it('preserves failed import drafts and imports key-only rows with original sampling modes', () => {
        const config = singleCounterConfig();
        config.rows.push({ key: 'path', expression: 'path', format: '.2e', samplingMode: 'continuous' });
        mountCounter();
        cy.get('.video-analyzer-counter__import').click();
        cy.get('.video-analyzer-counter__json').type('[,]');
        cy.get('.video-analyzer-counter__apply').click();
        cy.get('.video-analyzer-counter__json').should('have.value', '[,]');
        cy.get('.video-analyzer-counter__form [role="alert"]').should('contain.text', 'Invalid JSON');
        cy.get('@update').should('not.have.been.called');
        cy.get('.video-analyzer-counter__json').invoke('val', JSON.stringify(config)).trigger('input');
        cy.get('.video-analyzer-counter__apply').click();
        cy.get('@update').should('have.been.calledOnceWithExactly', config);
    });

    it('moves a row by a clamped offset and keeps other fields unchanged', () => {
        const config = singleCounterConfig();
        config.rows = ['a', 'b', 'c'].map((key) => ({ ...config.rows[0], key }));
        mountCounter(config);
        openRowMenu('b');
        cy.get('.video-analyzer-counter__move:visible').click();
        cy.get('.video-analyzer-counter__offset').clear();
        cy.get('.video-analyzer-counter__offset').type('-100');
        cy.get('.video-analyzer-counter__apply').click();
        cy.get('@update').should('have.been.calledOnceWithExactly', { ...config, rows: [config.rows[1], config.rows[0], config.rows[2]] });
    });

    for (const [direction, targetIndex] of [['above', 0], ['below', 11], ['above', 6], ['below', 5]] as const) {
        it(`adds ${direction} row ${targetIndex} in logical order, including endpoints and column boundaries`, () => {
            const config = singleCounterConfig();
            config.rows = Array.from({ length: 12 }, (_, index) => ({ ...config.rows[0], key: `row-${index}` }));
            const added = { key: 'new-row', expression: 'path', format: '.3f', samplingMode: 'button' as const };
            const expectedRows = [...config.rows];
            expectedRows.splice(targetIndex + Number(direction === 'below'), 0, added);
            mountCounter(config);
            cy.get('.video-analyzer-counter__column').should('have.length.greaterThan', 1);
            openRowMenu(`row-${targetIndex}`);
            cy.get(`.video-analyzer-counter__add-${direction}:visible`).click();
            cy.get('.counter-row-editor__format').should('have.value', '.3f');
            cy.get('.counter-row-editor__sampling').should('have.value', 'button');
            cy.get('.counter-row-editor__key').type(added.key);
            cy.get('.counter-row-editor__expression').type(added.expression);
            cy.get('.counter-row-editor__preview').should('have.text', '4.000');
            cy.get('@update').should('not.have.been.called');
            cy.get('.counter-row-editor__save').click();
            cy.get('@update').should('have.been.calledOnceWithExactly', { ...config, rows: expectedRows }).and(() => {
                expect(config.rows.map((entry) => entry.key)).to.deep.eq(Array.from({ length: 12 }, (_, index) => `row-${index}`));
            });
            cy.get('.counter-row-editor').should('not.exist');
        });
    }

    it('cancels adding without inserting a row and reopens a fresh draft', () => {
        mountCounter();
        openRowMenu('bvs');
        cy.get('.video-analyzer-counter__add-above:visible').click();
        cy.get('.counter-row-editor__key').type('cancelled');
        cy.get('.counter-row-editor__expression').type('left');
        cy.get('.counter-row-editor__cancel').click();
        cy.get('.counter-row-editor').should('not.exist');
        cy.get('@update').should('not.have.been.called');
        openRowMenu('bvs');
        cy.get('.video-analyzer-counter__add-below:visible').click();
        cy.get('.counter-row-editor__key').should('have.value', '');
        cy.get('.counter-row-editor__expression').should('have.value', '');
        cy.get('.counter-row-editor__cancel').click();
    });

    it('opens the selected row editor and updates only that stable key', () => {
        const config = singleCounterConfig();
        config.rows.push({ ...config.rows[0], key: 'second' });
        mountCounter(config);
        openRowMenu('second');
        cy.get('.video-analyzer-counter__edit:visible').click();
        cy.get('.el-dialog__title').should('have.text', 'Edit: second');
        cy.get('.counter-row-editor__expression').clear();
        cy.get('.counter-row-editor__expression').type('path');
        cy.get('.counter-row-editor__save').click();
        cy.get('@update').should('have.been.calledOnceWithExactly', { ...config, rows: [config.rows[0], { ...config.rows[1], expression: 'path' }] });
    });

    it('copies only ordered configuration, not live values or replay state', () => {
        mountCounter();
        cy.window().then((win) => {
            const copy = cy.stub(win.navigator.clipboard, 'writeText').as('copy');
            copy.resolves();
        });
        cy.get('.video-analyzer-counter__export').click();
        cy.get('@copy').should('have.been.calledOnceWithExactly', JSON.stringify(singleCounterConfig(), null, 2));
        cy.closeElNotifications();
        cy.get('@update').should('not.have.been.called');
    });
});
