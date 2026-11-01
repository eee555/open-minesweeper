import { defineComponent, h } from 'vue';

import type { KeyframeNavigation } from './keyframes';
import ProgressBar from './ProgressBar.vue';
import { provideAnalyzerState } from './useAnalyzerState';
import { usePlayback } from './usePlayback';

import i18n from '@/i18n';
import { createAnalyzerTestState } from '@cy/support/analyzerState';

function mountProgress(durationMs = 1000, width = 600, keyframeNavigation: KeyframeNavigation | null = null) {
    let now = 0;
    let frameId = 0;
    const frames = new Map<number, FrameRequestCallback>();
    cy.window().then((win) => {
        cy.stub(win.performance, 'now').callsFake(() => now);
        cy.stub(win, 'requestAnimationFrame').callsFake((callback: FrameRequestCallback) => {
            const id = ++frameId;
            frames.set(id, callback);
            return id;
        });
        cy.stub(win, 'cancelAnimationFrame').callsFake((id: number) => frames.delete(id));
    });
    cy.mount(defineComponent({
        expose: [],
        setup() {
            const playback = usePlayback(durationMs);
            provideAnalyzerState(createAnalyzerTestState({ playback, keyframeNavigation }));
            return () => h('div', { style: { width: `${width}px` } }, [h(ProgressBar)]);
        },
    }), { global: { plugins: [i18n] } });

    return (ms: number) => {
        cy.then(() => {
            now += ms;
            const pending = [...frames.values()];
            frames.clear();
            for (const callback of pending) callback(now);
        });
    };
}

function seek(ms: number) {
    cy.get('.analyzer-progress-bar__slider').invoke('val', ms).trigger('input');
}

function assertTime(ms: number) {
    cy.get('.analyzer-progress-bar__time').should('contain.text', `${(ms / 1000).toFixed(3)} /`);
}

function assertRange(startMs: number, endMs: number) {
    cy.get('.analyzer-progress-bar__range-time').should('have.text', `[${(startMs / 1000).toFixed(3)}, ${(endMs / 1000).toFixed(3)}] s`);
}

function assertMarker(endpoint: 'start' | 'end', fraction: number) {
    cy.get(`.analyzer-progress-bar__marker--${endpoint}`).should('be.visible').and(($marker) => {
        const input = $marker[0].closest('.analyzer-progress-bar__track')?.querySelector('input');
        if (!input) throw new Error('Range marker has no slider');
        const slider = input.getBoundingClientRect();
        const thumbSize = parseFloat(getComputedStyle(input).getPropertyValue('--thumb-size'));
        const marker = $marker[0].getBoundingClientRect();
        expect(marker.left + marker.width / 2).to.be.closeTo(slider.left + thumbSize / 2 + (slider.width - thumbSize) * fraction, 1);
        expect(getComputedStyle($marker[0]).pointerEvents).to.equal('none');
    });
}

describe('<AnalyzerProgressBar />', () => {
    it('joins buttons within functional groups while preserving spacing between groups', () => {
        cy.viewport(1000, 720);
        mountProgress(1000, 900);
        cy.get('.analyzer-progress-bar__controls > .button-group').should('have.length', 4).and(($groups) => {
            for (const group of $groups) {
                expect(getComputedStyle(group).gap).to.eq('0px');
                const controls = [...group.children];
                for (let index = 1; index < controls.length; index++) expect(controls[index].getBoundingClientRect().left).to.be.closeTo(controls[index - 1].getBoundingClientRect().right, 0.5);
            }
            for (let index = 1; index < $groups.length; index++) expect($groups[index].getBoundingClientRect().left - $groups[index - 1].getBoundingClientRect().right).to.be.closeTo(4, 0.5);
        });
        cy.get('.analyzer-progress-bar__controls').should(($controls) => {
            const [controls] = $controls;
            const range = controls.querySelector('.analyzer-progress-bar__range-time');
            if (!range) throw new Error('Missing selected range text');
            const loop = controls.querySelector('.analyzer-progress-bar__loop');
            if (!loop) throw new Error('Missing loop controls');
            expect(range.getBoundingClientRect().right).to.be.closeTo(controls.getBoundingClientRect().right, 0.5);
            expect(range.getBoundingClientRect().top).to.be.lessThan(controls.getBoundingClientRect().bottom);
            expect(range.getBoundingClientRect().left).to.be.at.least(loop.getBoundingClientRect().right);
        });
    });

    it('delegates keyframe navigation without changing playback state itself', () => {
        const previous = cy.spy().as('previous');
        const next = cy.spy().as('next');
        mountProgress(1000, 600, { previous: () => {
            previous();
        },
        next: () => {
            next();
        } });
        cy.get('.analyzer-progress-bar__previous-keyframe').click();
        cy.get('@previous').should('have.been.calledOnce');
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.analyzer-progress-bar__next-keyframe').click();
        cy.get('@next').should('have.been.calledOnce');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
    });

    it('seeks to both endpoints, plays from the end, and pauses', () => {
        const advance = mountProgress();
        seek(500);
        assertTime(500);
        cy.get('.analyzer-progress-bar__start').click();
        assertTime(0);
        cy.get('.analyzer-progress-bar__end').click();
        assertTime(1000);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play').click();
        assertTime(0);
        advance(100);
        assertTime(100);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause').click();
        advance(2000);
        assertTime(100);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('preserves playback while seeking and stops naturally without looping', () => {
        const advance = mountProgress();
        cy.get('.analyzer-progress-bar__play').click();
        advance(100);
        seek(500);
        advance(100);
        assertTime(600);
        cy.get('.analyzer-progress-bar__start').click();
        advance(100);
        assertTime(100);
        cy.get('.analyzer-progress-bar__end').click();
        assertTime(1000);
        advance(1);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        assertTime(1000);
    });

    it('holds the dragged position and resumes on release outside the slider', () => {
        const advance = mountProgress();
        cy.get('.analyzer-progress-bar__play').click();
        advance(100);
        cy.get('.analyzer-progress-bar__slider').trigger('pointerdown', { button: 0, eventConstructor: 'PointerEvent' });
        seek(750);
        advance(2000);
        assertTime(750);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
        cy.window().then((win) => win.dispatchEvent(new win.PointerEvent('pointerup')));
        advance(50);
        assertTime(800);
    });

    it('keeps paused dragging paused, including a cancelled drag', () => {
        const advance = mountProgress();
        cy.get('.analyzer-progress-bar__slider').trigger('pointerdown', { button: 0, eventConstructor: 'PointerEvent' });
        seek(600);
        cy.window().then((win) => win.dispatchEvent(new win.PointerEvent('pointercancel')));
        advance(1000);
        assertTime(600);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('uses preset speeds, stops at their limits, and restores normal speed', () => {
        const advance = mountProgress(10000);
        for (const rate of [1.5, 2, 4, 8]) {
            cy.get('.analyzer-progress-bar__faster').click();
            cy.get('.analyzer-progress-bar__normal').should('contain.text', `${rate}x`);
        }
        cy.get('.analyzer-progress-bar__faster').should('be.disabled');
        for (const rate of [4, 2, 1.5, 1, 0.75, 0.5, 0.25]) {
            cy.get('.analyzer-progress-bar__slower').click();
            cy.get('.analyzer-progress-bar__normal').should('contain.text', `${rate}x`);
        }
        cy.get('.analyzer-progress-bar__slower').should('be.disabled');
        cy.get('.analyzer-progress-bar__normal').click();
        cy.get('.analyzer-progress-bar__normal').should('contain.text', '1x');
        cy.get('.analyzer-progress-bar__play').click();
        advance(100);
        assertTime(100);
        cy.get('.analyzer-progress-bar__faster').click();
        advance(100);
        assertTime(250);
    });

    it('loops the full recording and stops after looping is disabled', () => {
        const advance = mountProgress();
        cy.get('.analyzer-progress-bar__loop-none').should('have.attr', 'aria-pressed', 'true');
        cy.get('.analyzer-progress-bar__loop-all').click();
        cy.get('.analyzer-progress-bar__loop-all').should('have.attr', 'aria-pressed', 'true');
        cy.get('.analyzer-progress-bar__play').click();
        advance(1250);
        assertTime(250);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
        cy.get('.analyzer-progress-bar__loop button').should('have.length', 3).each(($button) => {
            cy.wrap($button).should('be.disabled');
        });
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.analyzer-progress-bar__loop-none').should('not.be.disabled').click();
        cy.get('.analyzer-progress-bar__loop-all').should('have.attr', 'aria-pressed', 'false');
        cy.get('.analyzer-progress-bar__play').click();
        advance(1000);
        assertTime(1000);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('loops the selected range, locks editing while playing and resumes after out-of-range dragging', () => {
        const advance = mountProgress();
        seek(200);
        cy.get('.analyzer-progress-bar__range-start').click();
        seek(600);
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.get('.analyzer-progress-bar__loop-range').click();
        cy.get('.analyzer-progress-bar__loop-range').should('have.attr', 'aria-pressed', 'true');
        seek(0);
        assertTime(0);
        cy.get('.analyzer-progress-bar__play').click();
        assertTime(200);
        cy.get('.analyzer-progress-bar__range-start, .analyzer-progress-bar__range-end, .analyzer-progress-bar__loop button').each(($control) => {
            cy.wrap($control).should('be.disabled');
        });
        advance(400);
        assertTime(600);
        advance(1);
        assertTime(200);
        cy.get('.analyzer-progress-bar__slider').trigger('pointerdown', { button: 0, eventConstructor: 'PointerEvent' });
        seek(800);
        assertTime(200);
        advance(2000);
        assertTime(200);
        cy.window().then((win) => win.dispatchEvent(new win.PointerEvent('pointerup')));
        advance(100);
        assertTime(300);
        cy.get('.analyzer-progress-bar__play').click();
        cy.get('.analyzer-progress-bar__range-start, .analyzer-progress-bar__range-end, .analyzer-progress-bar__loop button').each(($control) => {
            cy.wrap($control).should('not.be.disabled');
        });
        cy.get('.analyzer-progress-bar__range-start').click();
        assertRange(300, 600);
    });

    it('disables play for an empty loop range without blocking corrections or other loop modes', () => {
        const advance = mountProgress();
        seek(300);
        cy.get('.analyzer-progress-bar__range-start').click();
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.get('.analyzer-progress-bar__loop-range').click();
        cy.get('.analyzer-progress-bar__play').should('be.disabled');
        cy.get('.analyzer-progress-bar__slider').should('not.be.disabled');
        assertMarker('start', 0.3);
        assertMarker('end', 0.3);
        for (const mode of ['none', 'all']) {
            cy.get(`.analyzer-progress-bar__loop-${mode}`).click();
            cy.get('.analyzer-progress-bar__play').should('not.be.disabled');
        }
        cy.get('.analyzer-progress-bar__loop-range').click();
        seek(500);
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.get('.analyzer-progress-bar__play').should('not.be.disabled').click();
        advance(1);
        assertTime(300);
    });

    it('disables playback and seeking without a duration', () => {
        mountProgress(0);
        cy.get('.analyzer-progress-bar__start, .analyzer-progress-bar__end, .analyzer-progress-bar__previous-keyframe, .analyzer-progress-bar__next-keyframe, .analyzer-progress-bar__play, .analyzer-progress-bar__slider, .analyzer-progress-bar__range-start, .analyzer-progress-bar__range-end').each(($control) => {
            cy.wrap($control).should('be.disabled');
        });
        assertTime(0);
        assertRange(0, 0);
        cy.get('.analyzer-progress-bar__marker').should('not.exist');
    });

    it('marks both range endpoints and restores the opposite default on reversed order', () => {
        mountProgress();
        assertRange(0, 1000);
        cy.get('.analyzer-progress-bar__marker').should('not.exist');
        seek(300);
        cy.get('.analyzer-progress-bar__range-start').click();
        assertRange(300, 1000);
        assertMarker('start', 0.3);
        cy.get('.analyzer-progress-bar__marker--end').should('not.exist');
        seek(800);
        cy.get('.analyzer-progress-bar__range-end').click();
        assertRange(300, 800);
        assertMarker('start', 0.3);
        assertMarker('end', 0.8);
        assertTime(800);
        seek(200);
        cy.get('.analyzer-progress-bar__range-end').click();
        assertRange(0, 200);
        cy.get('.analyzer-progress-bar__marker--start').should('not.exist');
        assertMarker('end', 0.2);
        seek(700);
        cy.get('.analyzer-progress-bar__range-start').click();
        assertRange(700, 1000);
        assertMarker('start', 0.7);
        cy.get('.analyzer-progress-bar__marker--end').should('not.exist');
        assertTime(700);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
    });

    it('allows equal endpoints rather than resetting an endpoint at equality', () => {
        mountProgress();
        seek(300);
        cy.get('.analyzer-progress-bar__range-start').click();
        cy.get('.analyzer-progress-bar__range-end').click();
        assertRange(300, 300);
        assertMarker('start', 0.3);
        assertMarker('end', 0.3);
        seek(1000);
        cy.get('.analyzer-progress-bar__range-start').click();
        assertRange(1000, 1000);
        assertMarker('start', 1);
        cy.get('.analyzer-progress-bar__marker--end').should('not.exist');
        seek(0);
        cy.get('.analyzer-progress-bar__range-end').click();
        assertRange(0, 0);
        cy.get('.analyzer-progress-bar__marker--start').should('not.exist');
        assertMarker('end', 0);
    });

    it('marks the displayed current time while playing without enabling interval playback', () => {
        const advance = mountProgress();
        cy.get('.analyzer-progress-bar__play').click();
        advance(100);
        cy.get('.analyzer-progress-bar__range-start').click();
        assertRange(100, 1000);
        assertTime(100);
        advance(200);
        cy.get('.analyzer-progress-bar__range-end').click();
        assertRange(100, 300);
        advance(500);
        assertTime(800);
        assertRange(100, 300);
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause');
    });

    it('keeps controls inside a narrow container', () => {
        mountProgress(1000, 240);
        seek(250);
        cy.get('.analyzer-progress-bar__range-start').click();
        seek(750);
        cy.get('.analyzer-progress-bar__range-end').click();
        assertMarker('start', 0.25);
        assertMarker('end', 0.75);
        cy.get('.analyzer-progress-bar').should(($bar) => {
            const bounds = $bar[0].getBoundingClientRect();
            for (const control of $bar.find('button, input, output')) {
                const rect = control.getBoundingClientRect();
                expect(rect.left).to.be.at.least(bounds.left);
                expect(rect.right).to.be.at.most(bounds.right + 1);
            }
            const [controls] = $bar.find('.analyzer-progress-bar__controls');
            const [range] = $bar.find('.analyzer-progress-bar__range-time');
            expect(range.getBoundingClientRect().right).to.be.closeTo(controls.getBoundingClientRect().right, 0.5);
        });
    });
});
