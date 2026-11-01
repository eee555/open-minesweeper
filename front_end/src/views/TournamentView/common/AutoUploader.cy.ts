
import { defineComponent, h, ref } from 'vue';

import AutoUploader from './AutoUploader.vue';
import type { AutoUploadVideo } from './utils';

import i18n from '@/i18n';
import { MS_State } from '@/utils/ms_const';
import { TournamentParticipant } from '@/utils/tournaments';
import { FakeDirectoryHandle, setDirectoryPicker, setPollInterval } from '@cy/support/autoUploader';
import { binaryStringToUint8Array } from '@cy/support/stupidCypress';

const UploaderHost = defineComponent({
    props: { participant: { type: TournamentParticipant, required: true } },
    setup: (props) => () => h(AutoUploader, { participant: props.participant, filter: () => true }),
});

function addReplay(directory: FakeDirectoryHandle, filename: string) {
    cy.fixture('standard_gsc.evf', 'binary').then((content) => {
        const bytes = binaryStringToUint8Array(content);
        const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
        directory.addFile(new File([buffer], filename));
    });
}

describe('<Common AutoUploader />', () => {
    afterEach(() => {
        setDirectoryPicker();
    });

    it('disables folder selection and shows the unavailable state without browser folder access', () => {
        const participant = new TournamentParticipant({ start_time: new Date('2000-01-01'), end_time: new Date('2099-01-01') });
        setDirectoryPicker();
        cy.mount(UploaderHost, { props: { participant }, global: { plugins: [i18n] } });
        cy.contains('.auto-uploader__label', 'Minesweeper replay folder').should('be.visible');
        cy.contains('Folder access is unavailable in this browser').should('be.visible');
        cy.contains('button', 'Select folder').should('be.disabled');
        cy.get('.auto-uploader [role=status]').should('contain.text', 'Auto-upload is off');
    });

    it('renders a custom filter control and uses the caller filter for each new replay', () => {
        const directory = new FakeDirectoryHandle();
        const participant = new TournamentParticipant({
            start_time: new Date('2000-01-01T00:00:00Z'),
            end_time: new Date('2099-01-01T00:00:00Z'),
        });
        const enabled = ref(false);
        const filter = cy.stub().callsFake((video: AutoUploadVideo) => {
            expect(video.tokens).to.deep.equal(['G11479']);
            expect(video.identifier).to.be.a('string');
            expect(video.stat).to.include({ level: 'e', timems: 41021 });
            return enabled.value;
        }).as('filter');
        const TestHost = defineComponent({
            setup() {
                return () => h(AutoUploader, { participant, filter }, {
                    filter: () => h('label', [
                        h('input', {
                            type: 'checkbox',
                            checked: enabled.value,
                            onChange: () => {
                                enabled.value = !enabled.value;
                            },
                        }),
                        'Accept new replays',
                    ]),
                });
            },
        });
        setDirectoryPicker(directory);
        cy.intercept('POST', '/common/uploadvideo/', {
            body: { type: 'success', object: 'videomodel', category: 'upload', data: { id: 901, state: MS_State.Official } },
        }).as('upload');
        cy.mount(TestHost, { global: { plugins: [i18n] } });
        cy.contains('label', 'Accept new replays').should('be.visible');
        cy.get('.el-select').should('not.exist');
        setPollInterval(1);
        cy.contains('button', 'Select folder').click();
        cy.contains('.el-dialog', 'Choose upload scope').should('be.visible');
        cy.contains('.el-dialog button', 'Include existing replays').should('be.visible');
        cy.contains('.el-dialog button', 'Upload new replays only').click();
        cy.contains('Auto-upload active: videos').should('be.visible');

        addReplay(directory, 'skipped.evf');
        cy.contains('Skipped: 100%(1)').should('be.visible');
        cy.get('@filter').should('have.been.calledOnce');
        cy.get('@upload.all').should('have.length', 0);

        cy.contains('label', 'Accept new replays').find('input').check();
        addReplay(directory, 'accepted.evf');
        cy.wait('@upload').its('response.statusCode').should('eq', 200);
        cy.contains('Uploaded: 50%(1)').should('be.visible');
        cy.get('@filter').should('have.been.calledTwice');
        cy.then(() => {
            expect(participant.videos).to.have.length(1);
            expect(participant.videos?.[0].id).to.equal(901);
        });
    });

    it('skips incomplete replays before calling the tournament filter or uploading', () => {
        const directory = new FakeDirectoryHandle();
        const participant = new TournamentParticipant({ start_time: new Date('2000-01-01'), end_time: new Date('2099-01-01') });
        const filter = cy.stub().as('filter');
        filter.returns(true);
        const TestHost = defineComponent({ setup: () => () => h(AutoUploader, { participant, filter }) });
        setDirectoryPicker(directory);
        cy.intercept('POST', '/common/uploadvideo/', { statusCode: 500 }).as('upload');
        cy.mount(TestHost, { global: { plugins: [i18n] } });
        setPollInterval(1);
        cy.contains('button', 'Select folder').click();
        cy.contains('.el-dialog button', 'Upload new replays only').click();
        cy.contains('Auto-upload active: videos').should('be.visible');

        cy.fixture('c_10_39.832_24_0.477_Pu Tian Yi(Hu Bei)_fail.evf', 'binary').then((content) => {
            const bytes = binaryStringToUint8Array(content);
            const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
            directory.addFile(new File([buffer], 'incomplete.evf'));
        });

        cy.contains('Skipped: 100%(1)').should('be.visible');
        cy.get('@filter').should('not.have.been.called');
        cy.get('@upload.all').should('have.length', 0);
        cy.then(() => {
            expect(participant.videos).to.be.undefined;
        });
    });

    it('resumes with files added while paused, without uploading the baseline or previous files again', () => {
        const directory = new FakeDirectoryHandle();
        const participant = new TournamentParticipant({ start_time: new Date('2000-01-01'), end_time: new Date('2099-01-01') });
        addReplay(directory, 'baseline.evf');
        setDirectoryPicker(directory);
        cy.intercept('POST', '/common/uploadvideo/', { body: { type: 'success', object: 'videomodel', category: 'upload', data: { id: 901, state: MS_State.Official } } }).as('upload');
        cy.mount(UploaderHost, { props: { participant }, global: { plugins: [i18n] } });
        setPollInterval(1);
        cy.contains('button', 'Select folder').click();
        cy.contains('.el-dialog', '1 files in this folder').should('be.visible');
        cy.contains('.el-dialog button', 'Upload new replays only').click();
        cy.contains('button', 'Pause').click();
        cy.contains('Auto-upload paused: videos').should('be.visible');
        addReplay(directory, 'paused.evf');
        cy.contains('button', 'Resume').click();
        cy.wait('@upload');
        cy.contains('Uploaded: 100%(1)').should('be.visible');
        cy.contains('button', 'Pause').click();
        cy.contains('button', 'Resume').should('be.enabled').click();
        cy.contains('Auto-upload active: videos').should('be.visible');
        cy.get('@upload.all').should('have.length', 1);
        cy.get('@showDirectoryPicker').should('have.been.calledOnce');
    });

    it('cancels the full scan queue while allowing an in-flight upload to finish for its original participant', () => {
        const directory = new FakeDirectoryHandle();
        const participant = new TournamentParticipant({ id: 1, start_time: new Date('2000-01-01'), end_time: new Date('2099-01-01') });
        const replacement = new TournamentParticipant({ id: 2, start_time: participant.start_time, end_time: participant.end_time });
        const started = cy.stub().as('uploadStarted');
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
            release = resolve;
        });
        addReplay(directory, 'first.evf');
        addReplay(directory, 'second.evf');
        setDirectoryPicker(directory);
        cy.intercept('POST', '/common/uploadvideo/', (req) => {
            started();
            return gate.then(() => {
                req.reply({ body: { type: 'success', object: 'videomodel', category: 'upload', data: { id: 901, state: MS_State.Official } } });
            });
        }).as('upload');
        cy.mount(UploaderHost, { props: { participant }, global: { plugins: [i18n] } });
        cy.contains('button', 'Select folder').click();
        cy.contains('.el-dialog', '2 files in this folder').should('be.visible');
        cy.contains('.el-dialog button', 'Include existing replays').click();
        cy.get('@uploadStarted').should('have.been.calledOnce');
        cy.get('.el-dialog .el-progress').should('be.visible');
        cy.contains('.el-dialog button', 'Cancel').click();
        cy.get<ComponentWrapper<typeof UploaderHost>>('@vue').then((wrapper) => wrapper.setProps({ participant: replacement }));
        cy.then(() => {
            release();
        });
        cy.wait('@upload');
        cy.contains('button', 'Select folder').should('be.enabled');
        cy.contains('button', 'Resume').should('not.exist');
        cy.get('@upload.all').should('have.length', 1);
        cy.then(() => {
            expect(participant.videos).to.have.length(1);
            expect(replacement.videos).to.be.undefined;
        });
    });

    it('counts skipped files in full scan progress and clears the app badge when idle', () => {
        const directory = new FakeDirectoryHandle();
        const participant = new TournamentParticipant({ start_time: new Date('2000-01-01'), end_time: new Date('2099-01-01') });
        directory.addFile(new File(['invalid'], 'invalid.txt'));
        setDirectoryPicker(directory);
        cy.window().then((win) => {
            Object.defineProperty(win.navigator, 'setAppBadge', { configurable: true, value: cy.stub().as('setBadge').resolves() });
            Object.defineProperty(win.navigator, 'clearAppBadge', { configurable: true, value: cy.stub().as('clearBadge').resolves() });
        });
        cy.mount(UploaderHost, { props: { participant }, global: { plugins: [i18n] } });
        cy.contains('button', 'Select folder').click();
        cy.contains('.el-dialog button', 'Include existing replays').click();
        cy.contains('Skipped: 100%(1)').should('be.visible');
        cy.contains('.el-dialog', 'Choose upload scope').should('not.be.visible');
        cy.contains('Auto-upload active: videos').should('be.visible');
        cy.get('@setBadge').should('have.been.calledWithExactly');
        cy.get('@clearBadge').should('have.been.called');
    });
});
