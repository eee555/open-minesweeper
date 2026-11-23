import { createI18n } from 'vue-i18n';

import { counterVariables, defaultCounterConfig } from './counter';
import type { CounterEvent, CounterValues } from './counter';
import CounterRowEditor from './CounterRowEditor.vue';

import i18n from '@/i18n';

function singleCounterConfig() {
    return { ...defaultCounterConfig(), rows: [{ key: 'bvs', expression: 'bbbv_solved / time', format: '.3f', samplingMode: 'button' as const }] };
}

function mountEditor(creating = false) {
    const row = creating ? { key: '', expression: '', format: '.3f', samplingMode: 'button' as const } : singleCounterConfig().rows[0];
    const events: CounterEvent[] = [{ timeMs: 1000,
        eventIndex: 0,
        button: true,
        boardChanged: true,
        values: { ...Object.fromEntries(counterVariables.map((key) => [key, 6])) as CounterValues, time: 2 } }];
    cy.mount(CounterRowEditor, { props: { row, events, currentMs: 1000, creating, existingKeys: ['bvs'], onSave: cy.spy().as('save'), onClose: cy.spy().as('close') }, global: { plugins: [i18n], stubs: { transition: false } } });
}

describe('<CounterRowEditor />', () => {
    it('links to the expression reference without changing the draft', () => {
        mountEditor();
        cy.get('.counter-expression-help__link').should('be.visible').and('contain.text', 'Expression reference').and('have.attr', 'target', '_blank').and('have.attr', 'rel', 'noopener noreferrer');
        cy.get('.counter-expression-help__link').should('have.attr', 'href').and('match', /\/docs\/guide\/replay-expressions$/);
        cy.get('.counter-row-editor details').should('not.exist');
        cy.get('.counter-row-editor__expression').should('have.value', 'bbbv_solved / time');
        cy.get('.counter-row-editor__preview').should('have.text', '3.000');
        cy.get('@save').should('not.have.been.called');
    });

    it('keeps the reference URL language-neutral for a Chinese interface', () => {
        cy.mount(CounterRowEditor, { props: { row: singleCounterConfig().rows[0], events: [], currentMs: 0 }, global: { plugins: [createI18n({ legacy: false, locale: 'zh-cn' })] } });
        cy.get('.counter-expression-help__link').should('be.visible').and('contain.text', '表达式参考文档');
        cy.get('.counter-expression-help__link').should('have.attr', 'href').and('match', /\/docs\/guide\/replay-expressions$/);
    });

    it('previews continuous millisecond fallback through replay end without advancing source time', () => {
        const row = { ...singleCounterConfig().rows[0], expression: 'time', samplingMode: 'continuous' as const };
        const events: CounterEvent[] = [0, 1].map((index) => ({ timeMs: index * 1000, eventIndex: index, button: true, boardChanged: true, values: { ...Object.fromEntries(counterVariables.map((key) => [key, index])) as CounterValues } }));
        cy.mount(CounterRowEditor, { props: { row, events, currentMs: 1500, durationMs: 2000 }, global: { plugins: [i18n] } });
        cy.get('.counter-row-editor__preview').should('have.text', '1.000');
        cy.get('.counter-row-editor__expression').clear();
        cy.get('.counter-row-editor__expression').type('d(time)');
        cy.get('.counter-row-editor__preview').should('have.text', '0.000');
    });

    it('edits only the target formula, format and sampling mode and previews the final number', () => {
        mountEditor();
        cy.get('.counter-row-editor__key, .counter-row-editor__label').should('not.exist');
        cy.get('.el-dialog__title').should('have.text', 'Edit: bvs');
        cy.get('.counter-row-editor__sampling option').should(($options) => {
            expect([...$options].map((option) => option.getAttribute('value'))).to.deep.eq(['continuous', 'button', 'board']);
        });
        cy.get('.counter-row-editor__preview').should('have.text', '3.000');
        cy.get('.counter-row-editor__expression').clear();
        cy.get('.counter-row-editor__expression').type('(left + right) / bbbv');
        cy.get('.counter-row-editor__format').clear();
        cy.get('.counter-row-editor__format').type('.1f');
        cy.get('.counter-row-editor__sampling').select('board');
        cy.get('.counter-row-editor__preview').should('have.text', '2.0');
        cy.get('.counter-row-editor__save').click();
        cy.get('@save').should('have.been.calledOnceWithExactly', { key: 'bvs', expression: '(left + right) / bbbv', format: '.1f', samplingMode: 'board' });
        cy.get('@close').should('have.been.calledOnce');
    });

    it('shows unknown variables and nonnumeric results without substituting zero, and cancellation emits no changes', () => {
        mountEditor();
        cy.get('.counter-row-editor__expression').clear();
        cy.get('.counter-row-editor__expression').type('bbbv_s');
        cy.get('.counter-row-editor__preview').should('have.class', 'text-danger').and('contain.text', 'Unknown variable: bbbv_s');
        cy.get('.counter-row-editor__expression').clear();
        cy.get('.counter-row-editor__expression').type('"3"');
        cy.get('.counter-row-editor__preview').should('contain.text', 'Expression must return a single number');
        cy.get('.counter-row-editor__cancel').click();
        cy.get('@close').should('have.been.calledOnce');
        cy.get('@save').should('not.have.been.called');
    });

    it('previews and saves sample expressions at the shared playback position', () => {
        const [row] = singleCounterConfig().rows;
        const events: CounterEvent[] = [1, 3, 8].map((value, index) => ({ timeMs: index * 1000,
            eventIndex: index,
            button: true,
            boardChanged: true,
            values: { ...Object.fromEntries(counterVariables.map((key) => [key, value])) as CounterValues, time: index } }));
        cy.mount(CounterRowEditor, { props: { row, events, currentMs: 2000, onSave: cy.spy().as('save') }, global: { plugins: [i18n] } }).then(({ wrapper }) => {
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('d(left + right) / d(time)');
            cy.get('.counter-row-editor__preview').should('have.text', '10.000');
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('d(d(left))');
            cy.get('.counter-row-editor__preview').should('have.text', '3.000');
            cy.then(() => wrapper.setProps({ currentMs: 0 }));
            cy.get('.counter-row-editor__preview').should('have.text', 'NaN').and('not.have.class', 'text-danger');
            cy.then(() => wrapper.setProps({ currentMs: 2000 }));
            cy.get('.counter-row-editor__preview').should('have.text', '3.000');
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('s(left)');
            cy.get('.counter-row-editor__preview').should('have.text', '12.000');
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('s(left, 2)');
            cy.get('.counter-row-editor__preview').should('have.text', '11.000');
            cy.then(() => wrapper.setProps({ currentMs: 0 }));
            cy.get('.counter-row-editor__preview').should('have.text', '1.000');
            cy.then(() => wrapper.setProps({ currentMs: 2000 }));
            cy.get('.counter-row-editor__preview').should('have.text', '11.000');
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('d(left, 0)');
            cy.get('.counter-row-editor__preview').should('have.class', 'text-danger').and('contain.text', 'positive integer sample step');
            cy.get('.counter-row-editor__expression').clear();
            cy.get('.counter-row-editor__expression').type('d(left, 2)');
            cy.get('.counter-row-editor__preview').should('have.text', '7.000');
            cy.then(() => wrapper.setProps({ currentMs: 1000 }));
            cy.get('.counter-row-editor__preview').should('have.text', 'NaN').and('not.have.class', 'text-danger');
            cy.then(() => wrapper.setProps({ currentMs: 2000 }));
            cy.get('.counter-row-editor__preview').should('have.text', '7.000');
            cy.get('.counter-row-editor__save').click();
            cy.get('@save').should('have.been.calledOnceWithExactly', { ...row, expression: 'd(left, 2)' });
        });
    });

    it('requires a unique key when adding and keeps the draft after validation fails', () => {
        mountEditor(true);
        cy.get('.counter-row-editor__label').should('not.exist');
        cy.get('.counter-row-editor__save').click();
        cy.get('@save').should('not.have.been.called');
        cy.get('.counter-row-editor__key').type('bvs');
        cy.get('.counter-row-editor__expression').type('path');
        cy.get('.counter-row-editor__format').clear();
        cy.get('.counter-row-editor__format').type('.1f');
        cy.get('.counter-row-editor__sampling').select('continuous');
        cy.get('.counter-row-editor__save').click();
        cy.get('.counter-row-editor [role="alert"]').should('contain.text', 'Row keys must be unique');
        cy.get('.counter-row-editor__expression').should('have.value', 'path');
        cy.get('@save').should('not.have.been.called');
        cy.get('.counter-row-editor__key').clear();
        cy.get('.counter-row-editor__key').type('path');
        cy.get('.counter-row-editor [role="alert"]').should('not.exist');
        cy.get('.counter-row-editor__save').click();
        cy.get('@save').should('have.been.calledOnceWithExactly', { key: 'path', expression: 'path', format: '.1f', samplingMode: 'continuous' });
        cy.get('@close').should('have.been.calledOnce');
    });
});
