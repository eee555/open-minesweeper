import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue';
import PrimeVue from 'primevue/config';

import NativePlayer from './NativePlayer.vue';
import { customCounterConfig } from './store';
import { cloneCustomCounterTable, defaultCustomCounterTable } from './types';

import { binaryStringToUint8Array } from '@/../cypress/support/stupidCypress';
import i18n from '@/i18n';
import { videoPlayerConfig } from '@/store';

const fixture = {
    filename: 'c_10_129.073_24_0.186_Pu Tian Yi(Hu Bei).evf',
    src: '/api/video/preview?id=c_10_129.073_24_0.186_Pu%20Tian%20Yi%28Hu%20Bei%29.evf',
};

function mountOptions(src: string) {
    return {
        props: { src },
        global: {
            plugins: [i18n, PrimeVue],
            components: { ArrowLeft, ArrowRight },
        },
    };
}

function mockVideoFixture(headers: Record<string, string> = {}, filename = fixture.filename) {
    cy.intercept('GET', '**/api/video/preview**', {
        statusCode: 200,
        headers: { 'content-type': 'application/octet-stream', 'x-replay-container-version': '0', ...headers },
        // Load raw bytes on the Cypress server instead of sending an ArrayBuffer through request.reply().
        fixture: `${filename},null`,
    }).as('getVideo');
}

function dynamicParamCell(label: string, options?: Partial<Cypress.Timeoutable>) {
    return cy.contains('.custom-counter-wrap th', new RegExp(`^${label}$`), options).parents('tr').find('td');
}

function waitForLoadedPlayer() {
    cy.get('.native-player', { timeout: 10000 }).should(($player) => {
        expect($player.find('.native-player__content'), $player.text()).to.have.length(1);
    });
}

describe('<NativePlayer />', () => {
    it('decodes a Python-generated MSRC replay using the local fallback', () => {
        cy.intercept('GET', 'https://cdn.jsdelivr.net/npm/@putianyi888/msrc@0.2.0/**', { forceNetworkError: true });
        mockVideoFixture({ 'x-replay-container-version': '1', 'content-disposition': 'attachment; filename="52200.evf.msrc"' }, '52200.evf.msrc');
        cy.mount(NativePlayer, mountOptions('/api/video/preview?id=52200.evf'));
        waitForLoadedPlayer();
        cy.get('.native-player__content').should('be.visible');
    });

    beforeEach(() => {
        cy.clearLocalStorage('custom-counter-config');
        cy.clearLocalStorage('video-player-config');
        customCounterConfig.value = {
            table: cloneCustomCounterTable(defaultCustomCounterTable),
            thWidth: 90,
            tdWidth: 130,
            fontSize: 12,
        };
        videoPlayerConfig.value = {
            cellSize: 16,
            showProbability: true,
            probabilityColorScheme: {
                colors: ['#15803d', '#0f766e', '#2563eb', '#b45309', '#dc2626', '#7f1d1d'],
                thresholds: [10, 25, 50, 75, 90],
            },
        };
    });

    it('loads and renders an EVF replay from fixtures', () => {
        mockVideoFixture();
        cy.mount(NativePlayer, mountOptions(fixture.src));

        cy.wait('@getVideo');
        waitForLoadedPlayer();
        cy.get('.native-player__content').should('be.visible');
        cy.get('.player-main').should('be.visible');
        cy.get('.custom-counter-wrap').should('exist').and('contain', 'cl');
        dynamicParamCell('bvs').should('contain', '/24');
        cy.get('.custom-counter-wrap').should('contain', 'time');
        cy.get('.custom-counter-wrap').should('contain', 'mov');
    });

    it('advances the replay when playing', () => {
        mockVideoFixture();
        cy.mount(NativePlayer, mountOptions(fixture.src));

        cy.wait('@getVideo');
        waitForLoadedPlayer();
        cy.get('.native-player .pi-play').closest('button').click();
        dynamicParamCell('time').should(($time) => {
            expect($time.text()).to.contain('/');
        });
        dynamicParamCell('bvs').should(($bvs) => {
            const match = (/^(\d+)\/(\d+)~/).exec($bvs.text());
            expect(match, $bvs.text()).not.to.equal(null);
            if (match === null) return;
            expect(Number(match[1])).to.be.lessThan(Number(match[2]));
        });
    });

    it('includes the final click when playing, seeking or stepping to the end of replay 52200', () => {
        cy.viewport(1000, 800);
        mockVideoFixture({}, '52200.evf');
        let animationCallback: FrameRequestCallback | undefined;
        cy.window().then((win) => {
            cy.stub(win, 'requestAnimationFrame').callsFake((callback: FrameRequestCallback) => {
                animationCallback = callback;
                return 1;
            });
            cy.stub(win, 'cancelAnimationFrame');
        });
        cy.mount(NativePlayer, mountOptions('/api/video/preview?id=52200.evf'));
        cy.wait('@getVideo');
        waitForLoadedPlayer();

        cy.get('.native-player .pi-play').closest('button').click();
        cy.window().then((win) => {
            if (animationCallback === undefined) throw new Error('Expected playback to start.');
            animationCallback(win.performance.now() + 10733);
        });
        dynamicParamCell('bvs').should('contain', '52/52');
        dynamicParamCell('cl').invoke('text').should('match', /^63@/);
        cy.get('.native-player .pi-pause').should('not.exist');

        cy.get('.native-player .pi-play').closest('button').click();
        dynamicParamCell('bvs').invoke('text').should('match', /^1\/52~/);
        cy.window().then((win) => {
            if (animationCallback === undefined) throw new Error('Expected playback to restart.');
            animationCallback(win.performance.now() + 100);
        });
        cy.get('.native-player .pi-pause').should('exist');
        dynamicParamCell('bvs').should('not.contain', '52/52');

        cy.get('.native-player .pi-replay').closest('button').click();
        dynamicParamCell('bvs').invoke('text').should('match', /^1\/52~/);
        cy.get('.progress-bar__slider .el-slider__button-wrapper').trigger('keydown', { code: 'End', key: 'End' });
        dynamicParamCell('bvs').should('contain', '52/52');
        cy.get('.progress-bar__slider .el-slider__button-wrapper').trigger('keydown', { code: 'ArrowLeft', key: 'ArrowLeft' });
        dynamicParamCell('bvs').should('contain', '51/52');
        cy.get('.progress-bar__step').click();
        dynamicParamCell('bvs').should('contain', '52/52');
        dynamicParamCell('cl').invoke('text').should('match', /^63@/);
    });

    it('keeps the two editors independent and persists probability visibility', () => {
        cy.viewport(1000, 800);
        mockVideoFixture();
        cy.mount(NativePlayer, mountOptions(fixture.src));
        cy.wait('@getVideo');
        waitForLoadedPlayer();

        cy.contains('label', 'Main settings').click();
        cy.contains('label', 'Main settings').find('input').should('be.checked');
        cy.get('.player-main-settings').should('be.visible');
        cy.get('.custom-counter-wrap').should('not.exist');
        cy.get('.player-main').should('be.visible');
        cy.get('.player-main-settings .color-scheme-setting__import-toggle').click();
        cy.get('.player-main-settings .color-scheme-setting__json').should('be.visible');
        cy.get('.player-main-settings .color-scheme-setting__cancel').click();
        cy.get('.player-main-settings .color-scheme-setting__json').should('not.exist');

        cy.contains('label', 'Show Probability').find('input').should('be.checked').focus();
        cy.realPress('Space');
        cy.contains('label', 'Show Probability').find('input').should('not.be.checked');
        cy.get('.player-main-settings__color-scheme').should('not.exist');
        cy.window().its('localStorage').invoke('getItem', 'video-player-config').should((value: string | null) => {
            const config = JSON.parse(value ?? '{}') as { showProbability?: boolean };
            expect(config.showProbability).to.equal(false);
        });

        cy.contains('label', 'Edit counter').click();
        cy.contains('label', 'Main settings').find('input').should('be.checked');
        cy.contains('label', 'Edit counter').find('input').should('be.checked');
        cy.get('.player-main-settings').should('be.visible');
        cy.get('.custom-counter-settings').should('be.visible');
        cy.get('.player-main').should('not.exist');
        cy.contains('label', 'Main settings').click();
        cy.get('.player-main-settings').should('not.exist');
        cy.get('.custom-counter-wrap').should('be.visible');
        cy.get('.custom-counter-settings').should('be.visible');
    });

    for (const responseFilename of ['original replay.evf', undefined]) {
        it(`downloads the original bytes with the ${responseFilename === undefined ? 'URL' : 'response'} filename`, () => {
            mockVideoFixture(responseFilename === undefined
                ? {}
                : {
                    'content-disposition': `attachment; filename="${encodeURIComponent(responseFilename)}"`,
                });
            cy.mount(NativePlayer, mountOptions(fixture.src));
            cy.wait('@getVideo');
            waitForLoadedPlayer();

            let downloadedBlob: Blob | undefined;
            const objectUrl = 'blob:http://localhost/native-player-download';
            cy.window().then((win) => {
                cy.stub(win.URL, 'createObjectURL').callsFake((blob: Blob) => {
                    downloadedBlob = blob;
                    return objectUrl;
                });
                cy.stub(win.URL, 'revokeObjectURL').as('revokeDownloadUrl');
                cy.stub(win.HTMLAnchorElement.prototype, 'click').callsFake(function (this: HTMLAnchorElement) {
                    expect(this.download).to.equal(responseFilename ?? fixture.filename);
                    expect(this.href).to.equal(objectUrl);
                }).as('downloadFile');
            });

            cy.get('.native-player .pi-download').closest('button').click();
            cy.get('@downloadFile').should('have.been.calledOnce');
            cy.get('@revokeDownloadUrl').should('have.been.calledOnceWith', objectUrl);
            cy.get('@getVideo.all').should('have.length', 1);
            cy.fixture(fixture.filename, 'binary').then((fileContent) => {
                if (downloadedBlob === undefined) throw new Error('Expected a downloaded video.');
                return downloadedBlob.arrayBuffer().then((buffer) => {
                    expect(new Uint8Array(buffer)).to.deep.equal(binaryStringToUint8Array(fileContent));
                });
            });
        });
    }

    it('reports fetch response errors from the backend', () => {
        cy.intercept('GET', '**/videos/**', {
            statusCode: 404,
            statusMessage: 'Not Found',
            body: '',
        }).as('getVideo');
        cy.mount(NativePlayer, mountOptions('/videos/'));

        cy.wait('@getVideo');
        cy.get('.native-player').should('contain', '404');
        cy.get('.native-player .pi-download').should('not.exist');
    });
});
