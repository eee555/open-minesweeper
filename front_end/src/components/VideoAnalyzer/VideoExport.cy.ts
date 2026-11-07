import { ALL_FORMATS, BlobSource, CanvasSink, Input } from 'mediabunny';
import { defineComponent, h, ref } from 'vue';

import App from './App.vue';
import { defaultAnalyzerConfig } from './config';
import type { ReplaySource } from './replayParser';

import i18n from '@/i18n';

function mountAnalyzer() {
    cy.viewport(1000, 700);
    cy.fixture('c_10_129.073_24_0.186_Pu Tian Yi(Hu Bei).evf', 'binary').then((binary: string) => {
        const source: ReplaySource = { data: Uint8Array.from(binary, (character) => character.charCodeAt(0)).buffer, filename: 'replay.evf', software: 'e' };
        const config = ref(defaultAnalyzerConfig());
        config.value.cellSizeMode = 'fixed';
        config.value.fixedCellSize = 32;
        config.value.globalVisible = true;
        config.value.globalOpacity = 0.5;
        config.value.traceVisible = true;
        const probabilityColorScheme = { colors: ['#15803d', '#dc2626'], thresholds: [50] };
        cy.mount(defineComponent({ expose: [],
            render: () => h('div', { style: { width: '900px', height: '600px' } }, [h(App, { source,
                config: config.value,
                probabilityColorScheme,
                'onUpdate:config': (value) => {
                    config.value = value;
                } })]) }), { global: { plugins: [i18n] } });
    });
    cy.get('.analyzer-progress-bar__slider', { timeout: 10000 }).should('have.attr', 'max', '129073');
    cy.get<HTMLCanvasElement>('canvas.video-analyzer-board__background').should(($canvas) => {
        expect($canvas[0].getContext('2d')?.getImageData(0, 0, 1, 1).data[3]).to.eq(255);
    });
}

function seek(ms: number) {
    cy.get('.analyzer-progress-bar__slider').invoke('val', ms).trigger('input');
}

describe('Analyzer video export', () => {
    for (const format of ['mp4', 'webm'] as const) {
        it(`encodes and decodes a cropped ${format} at the selected speed`, () => {
            mountAnalyzer();
            seek(3000);
            cy.get('.analyzer-progress-bar__range-start').click();
            seek(5000);
            cy.get('.analyzer-progress-bar__range-end').click();
            cy.get('.analyzer-progress-bar__rate').invoke('val', 2).trigger('input');
            let downloaded: Blob | undefined;
            cy.window().then((win) => {
                const create = win.URL.createObjectURL.bind(win.URL);
                cy.stub(win.URL, 'createObjectURL').callsFake((blob: Blob) => {
                    if (blob.type.startsWith('video/')) downloaded = blob;
                    return create(blob);
                });
                cy.stub(win.HTMLAnchorElement.prototype, 'click').as('download');
            });
            cy.get('.video-export__open').click();
            cy.get('.video-export__scope').select('range');
            cy.get('.video-export__format').select(format);
            cy.get('.video-export__fps').clear();
            cy.get('.video-export__fps').type('10');
            cy.get('.video-export__bottom').clear();
            cy.get('.video-export__bottom').type('3');
            cy.get('.video-export__right').clear();
            cy.get('.video-export__right').type('3');
            cy.get('.video-export__start').click();
            cy.wrap(null, { timeout: 30000 }).should(() => {
                expect(downloaded?.size).to.be.greaterThan(0);
            }).then({ timeout: 30000 }, async () => {
                if (!downloaded) throw new Error('Expected an exported video');
                const input = new Input({ source: new BlobSource(downloaded), formats: ALL_FORMATS });
                try {
                    expect(await input.computeDuration()).to.be.closeTo(1, 0.01);
                    const track = await input.getPrimaryVideoTrack();
                    if (!track) throw new Error('Expected a video track');
                    expect(await track.getDisplayWidth()).to.eq(128);
                    expect(await track.getDisplayHeight()).to.eq(128);
                    const sink = new CanvasSink(track);
                    let frames = 0;
                    for await (const frame of sink.canvases()) {
                        const pixels = frame.canvas.getContext('2d')?.getImageData(0, 0, 128, 128).data;
                        expect(pixels?.some((value, index) => index % 4 !== 3 && value > 30)).to.eq(true);
                        frames++;
                    }
                    expect(frames).to.eq(10);
                } finally {
                    input.dispose();
                }
            });
            cy.get('.video-export').should('not.be.visible');
            cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
            cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
            cy.get('.board-size-controls__auto-toggle').click();
            cy.get('.video-analyzer-board__viewport').should('have.class', 'video-analyzer-board__viewport--auto');
        });
    }

    it('cancels whole-replay export without downloading and resumes playback', () => {
        mountAnalyzer();
        seek(5000);
        cy.get('.analyzer-progress-bar__play').click();
        cy.window().then((win) => {
            cy.stub(win.HTMLAnchorElement.prototype, 'click').as('download');
        });
        cy.get('.video-export__open').click();
        cy.get('.video-export__start').click();
        cy.get('.video-export__cancel').should('be.visible');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Play');
        let frozenMs = '';
        cy.get('.analyzer-progress-bar__slider').invoke('val').then((value) => {
            frozenMs = String(value);
        });
        cy.get('.video-export__progress').should(($progress) => {
            expect(Number($progress.attr('value'))).to.be.greaterThan(0);
        });
        cy.get('.analyzer-progress-bar__slider').should(($slider) => {
            expect(String($slider.val())).to.eq(frozenMs);
        });
        cy.get('.video-export__cancel').click();
        cy.get('.video-export', { timeout: 30000 }).should('not.be.visible');
        cy.get('@download').should('not.have.been.called');
        cy.get('.analyzer-progress-bar__play').should('have.attr', 'aria-label', 'Pause').click();
        cy.get('.analyzer-progress-bar__slider').should(($slider) => {
            expect(Number($slider.val())).to.be.greaterThan(5000);
        });
    });

    it('rejects reversed crop bounds and disables an empty interval', () => {
        mountAnalyzer();
        seek(5000);
        cy.get('.analyzer-progress-bar__range-start').click();
        cy.get('.analyzer-progress-bar__range-end').click();
        cy.get('.video-export__open').click();
        cy.get('.video-export__scope option[value="range"]').should('be.disabled');
        cy.get('.video-export__top').clear();
        cy.get('.video-export__top').type('5');
        cy.get('.video-export__bottom').clear();
        cy.get('.video-export__bottom').type('2');
        cy.get('.video-export__start').click();
        cy.get('.video-export [role="alert"]').should('contain', 'Invalid board export region');
        cy.get('.analyzer-progress-bar__slider').should('have.value', '5000');
        cy.get('.video-export__close').click();
    });
});
