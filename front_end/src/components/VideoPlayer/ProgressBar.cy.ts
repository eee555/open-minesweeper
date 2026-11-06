import ProgressBar from './ProgressBar.vue';

import i18n from '@/i18n';

function mountProgressBar(current = 0, duration = 1000) {
    cy.mount(ProgressBar, {
        props: {
            modelValue: current,
            durationMs: duration,
        },
        global: {
            plugins: [i18n],
        },
    }).then(({ wrapper }) => {
        return wrapper.setProps({
            'onUpdate:modelValue': (value: number) => {
                void wrapper.setProps({ modelValue: value });
            },
        });
    });
}

function modelUpdate(index: number) {
    return cy.get('@vue').then((wrapper: ComponentWrapper<typeof ProgressBar>) => {
        return wrapper.emitted('update:modelValue')?.[index]?.[0];
    });
}

function lastModelUpdate() {
    return cy.get<ComponentWrapper<typeof ProgressBar>>('@vue').invoke('emitted', 'update:modelValue').invoke('at', -1).its('0');
}

describe('<ProgressBar />', () => {
    afterEach(() => {
        // Release window-level drag listeners even when an assertion interrupts the drag.
        cy.window().trigger('mouseup', { eventConstructor: 'MouseEvent' });
        cy.get('.progress-bar__slider .el-slider__button-wrapper').should('not.have.class', 'dragging');
    });

    it('emits bounded step and restart updates', () => {
        mountProgressBar(950, 1000);

        cy.get('button[aria-label="Step 0.1 seconds"]').focus();
        cy.realPress('Enter');
        modelUpdate(0).should('eq', 1000);

        cy.get('button[aria-label="Restart"]').focus();
        cy.realPress('Space');
        modelUpdate(1).should('eq', 0);
    });

    it('emits a clamped update when duration shrinks', () => {
        mountProgressBar(100, 1000);

        cy.get('@vue').then((wrapper: ComponentWrapper<typeof ProgressBar>) => {
            return wrapper.setProps({ durationMs: 50 });
        });

        modelUpdate(0).should('eq', 50);
    });

    it('accepts custom rates, steps by 0.1 within bounds and changes speed without jumping', () => {
        let animationCallback: FrameRequestCallback | undefined = undefined;
        let now = 1000;

        cy.window().then((win) => {
            cy.stub(win.performance, 'now').callsFake(() => now);
            cy.stub(win, 'requestAnimationFrame').callsFake((callback: FrameRequestCallback) => {
                animationCallback = callback;
                return 1;
            });
            cy.stub(win, 'cancelAnimationFrame');
        });
        mountProgressBar(0, 1000);

        cy.get('input[aria-label="Playback speed"]').should('have.value', '1').and('have.attr', 'type', 'number');
        cy.get('.progress-bar__speed').should('have.attr', 'step', '0.1');
        for (const rate of ['1.1', '1.2', '1.3']) {
            cy.get('.progress-bar__faster').click();
            cy.get('.progress-bar__speed').should('have.value', rate);
        }
        cy.get('.progress-bar__slower').click();
        cy.get('.progress-bar__speed').should('have.value', '1.2');
        cy.get('.progress-bar__speed').invoke('val', 0.65).trigger('input');
        cy.get('.progress-bar .pi-play').closest('button').click();
        cy.then(() => {
            expect(animationCallback).not.to.equal(undefined);
            now = 1250;
            animationCallback?.(now);
        });
        lastModelUpdate().should('eq', 162.5);

        cy.get('.progress-bar__speed').invoke('val', 1.35).trigger('input');
        lastModelUpdate().should('eq', 162.5);
        cy.get('.progress-bar .pi-pause').should('exist');
        cy.then(() => {
            now = 1500;
            animationCallback?.(now);
        });
        lastModelUpdate().should('eq', 500);
        cy.get('.progress-bar .pi-pause').closest('button').click();
        cy.get('.progress-bar__speed').invoke('val', 3.95).trigger('input');
        cy.get('.progress-bar__faster').click();
        cy.get('.progress-bar__speed').should('have.value', '4');
        cy.get('.progress-bar__faster').should('be.disabled');
        cy.get('.progress-bar__speed').invoke('val', 0.55).trigger('input');
        cy.get('.progress-bar__slower').click();
        cy.get('.progress-bar__speed').should('have.value', '0.5');
        cy.get('.progress-bar__slower').should('be.disabled');
    });

    for (const { playing, fraction, expected, fromTrack } of [
        { playing: true, fraction: 0.75, expected: 850, fromTrack: false },
        { playing: false, fraction: 0.75, expected: 750, fromTrack: false },
        { playing: true, fraction: 1, expected: 1000, fromTrack: false },
        { playing: true, fraction: 0.75, expected: 850, fromTrack: true },
    ]) {
        it(`drags the ${fromTrack ? 'track' : 'handle'} to ${fraction * 100}% while ${playing ? 'playing' : 'paused'} and ${expected === 850 ? 'continues playback' : 'stays paused'}`, () => {
            let animationCallback: FrameRequestCallback | undefined;
            let targetX = 0;
            let targetY = 0;

            cy.window().then((win) => {
                cy.stub(win.performance, 'now').returns(1000);
                cy.stub(win, 'requestAnimationFrame').callsFake((callback: FrameRequestCallback) => {
                    animationCallback = callback;
                    return 1;
                });
                cy.stub(win, 'cancelAnimationFrame');
            });
            mountProgressBar(0, 1000);
            if (playing) {
                cy.get('.progress-bar .pi-play').closest('button').click();
                cy.then(() => animationCallback?.(1100));
                lastModelUpdate().should('eq', 100);
            }
            cy.get('.progress-bar__slider .el-slider__button-wrapper').should('have.attr', 'aria-valuenow', playing ? '100' : '0');

            cy.get('.progress-bar__slider .el-slider__runway').then(($runway) => {
                const bounds = $runway[0].getBoundingClientRect();
                targetX = bounds.left + bounds.width * fraction;
                targetY = bounds.top + bounds.height / 2;
            });
            cy.get(`.progress-bar__slider .${fromTrack ? 'el-slider__runway' : 'el-slider__button-wrapper'}`).then(($handle) => {
                const bounds = $handle[0].getBoundingClientRect();
                const position = { button: 0, clientX: bounds.left + bounds.width * (fromTrack ? 0.25 : 0.5), clientY: targetY };
                cy.wrap($handle).trigger('pointerdown', { ...position, eventConstructor: 'PointerEvent', scrollBehavior: false });
                cy.wrap($handle).trigger('mousedown', { ...position, eventConstructor: 'MouseEvent', scrollBehavior: false });
            });
            cy.get('.progress-bar__slider .el-slider__button-wrapper').should('have.class', 'dragging');
            if (playing) {
                cy.then(() => animationCallback?.(2000));
                lastModelUpdate().should('eq', fromTrack ? 250 : 100);
            }
            cy.window().then((win) => {
                cy.wrap(win).trigger('mousemove', { clientX: targetX, clientY: targetY, buttons: 1, eventConstructor: 'MouseEvent' });
            });
            lastModelUpdate().should('eq', fraction * 1000);
            if (playing) {
                cy.then(() => animationCallback?.(3000));
                lastModelUpdate().should('eq', fraction * 1000);
            }
            cy.window().trigger('mouseup', { eventConstructor: 'MouseEvent' });
            cy.get(`.progress-bar .${expected === 850 ? 'pi-pause' : 'pi-play'}`).should('exist');
            cy.get('@vue').should((wrapper: ComponentWrapper<typeof ProgressBar>) => {
                const slider = wrapper.findComponent({ name: 'ElSlider' });
                expect(slider.emitted('change')).to.have.length(1);
            });
            cy.then(() => animationCallback?.(1100));
            lastModelUpdate().should('eq', expected);
        });
    }
});
