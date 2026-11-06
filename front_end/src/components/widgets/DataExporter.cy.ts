import { defineComponent, h, ref } from 'vue';
import type { Component, PropType } from 'vue';

import DataExporter from './DataExporter.vue';

import i18n from '@/i18n';

interface TestRecord {
    id: number;
    name: string;
    score: number;
}

type FetchData = () => TestRecord[] | Promise<TestRecord[]>;

interface DownloadRecorder {
    anchors: HTMLAnchorElement[];
    blobs: Blob[];
    objectUrls: string[];
    revokedObjectUrls: string[];
}

interface ExpectedDownload {
    content: string;
    filename: string;
    type: string;
}

const TypedDataExporter = DataExporter as unknown as Component;

const existingRecords: TestRecord[] = [
    { id: 1, name: 'Alpha', score: 10 },
    { id: 2, name: 'Bravo, Jr.', score: 20 },
];

const fetchedRecords: TestRecord[] = [
    { id: 3, name: 'Charlie', score: 30 },
    { id: 4, name: 'Delta', score: 40 },
];

const existingRecordsCsv = 'id,name,score\r\n1,Alpha,10\r\n2,"Bravo, Jr.",20';
const fetchedRecordsCsv = 'id,name,score\r\n3,Charlie,30\r\n4,Delta,40';

const TestHost = defineComponent({
    props: {
        initialData: {
            type: Array as PropType<TestRecord[]>,
            default: () => [],
        },
        fetchData: {
            type: Function as PropType<FetchData>,
            default: undefined,
        },
        filename: {
            type: String,
            default: 'records',
        },
        lazy: {
            type: Boolean,
            default: false,
        },
    },
    expose: [],
    setup(props) {
        const data = ref<TestRecord[]>(props.initialData);
        return { data };
    },
    render() {
        return h('div', {}, [
            h(TypedDataExporter, {
                modelValue: this.data,
                'onUpdate:modelValue': (value: TestRecord[]) => {
                    this.data = value;
                },
                fetchData: this.fetchData,
                filename: this.filename,
                lazy: this.lazy,
            }, {
                default: () => 'Export records',
            }),
            h('output', { 'data-cy': 'model-count' }, String(this.data.length)),
        ]);
    },
});

function mountDataExporter(options: {
    fetchData?: FetchData;
    filename?: string;
    initialData?: TestRecord[];
    lazy?: boolean;
} = {}) {
    cy.mount(TestHost as never, {
        props: {
            fetchData: options.fetchData,
            filename: options.filename ?? 'records',
            initialData: options.initialData ?? [],
            lazy: options.lazy ?? false,
        },
        global: { plugins: [i18n] },
    } as never);
}

function stubDownloads(): DownloadRecorder {
    const downloads: DownloadRecorder = {
        anchors: [],
        blobs: [],
        objectUrls: [],
        revokedObjectUrls: [],
    };

    cy.window().then((win) => {
        cy.stub(win.URL, 'createObjectURL').callsFake((blob: Blob | MediaSource) => {
            expect(blob).to.be.instanceOf(win.Blob);
            const objectUrl = `blob:${win.location.origin}/data-exporter-${downloads.objectUrls.length + 1}`;
            downloads.blobs.push(blob as Blob);
            downloads.objectUrls.push(objectUrl);
            return objectUrl;
        });
        cy.stub(win.URL, 'revokeObjectURL').callsFake((objectUrl: string) => {
            downloads.revokedObjectUrls.push(objectUrl);
        });
        cy.stub(win.HTMLAnchorElement.prototype, 'click').callsFake(function (this: HTMLAnchorElement) {
            downloads.anchors.push(this);
        });
    });

    return downloads;
}

function clickExportButton() {
    cy.contains('button', 'Export records').click();
}

function selectFormat(format: 'CSV' | 'JSON') {
    cy.get('select[aria-label="Format"]').focus();
    cy.get('select[aria-label="Format"]').should('have.focus').select(format.toLowerCase());
}

function expectDownload(downloads: DownloadRecorder, index: number, expected: ExpectedDownload) {
    cy.wrap(downloads, { log: false }).should(() => {
        expect(downloads.anchors[index]).not.to.equal(undefined);
        expect(downloads.blobs[index]).not.to.equal(undefined);
        expect(downloads.objectUrls[index]).not.to.equal(undefined);
        expect(downloads.revokedObjectUrls[index]).not.to.equal(undefined);
    });

    cy.then(() => {
        const anchor = downloads.anchors[index];
        const blob = downloads.blobs[index];
        const objectUrl = downloads.objectUrls[index];

        if (anchor === undefined || blob === undefined || objectUrl === undefined) {
            throw new Error(`Expected download at index ${index}.`);
        }

        expect(anchor.download).to.equal(expected.filename);
        expect(anchor.href).to.equal(objectUrl);
        expect(blob.type).to.equal(expected.type);
        expect(downloads.revokedObjectUrls[index]).to.equal(objectUrl);
        return blob.text();
    }).should('equal', expected.content);
}

describe('<DataExporter />', () => {
    it('exports existing model data as CSV by default', () => {
        const downloads = stubDownloads();
        mountDataExporter({
            filename: 'scores.csv',
            initialData: existingRecords,
        });

        clickExportButton();

        expectDownload(downloads, 0, {
            content: existingRecordsCsv,
            filename: 'scores.csv',
            type: 'text/csv;charset=utf-8',
        });
    });

    it('exports existing model data as JSON after selecting JSON format', () => {
        const downloads = stubDownloads();
        mountDataExporter({
            filename: 'scores',
            initialData: existingRecords,
        });

        selectFormat('JSON');
        clickExportButton();

        expectDownload(downloads, 0, {
            content: JSON.stringify(existingRecords, null, 2),
            filename: 'scores.json',
            type: 'application/json;charset=utf-8',
        });
    });

    it('fetches lazy data once and reuses the model cache', () => {
        const downloads = stubDownloads();
        let fetchCount = 0;
        const fetchData: FetchData = () => {
            fetchCount += 1;
            return Promise.resolve(fetchedRecords);
        };

        mountDataExporter({
            fetchData,
            filename: 'fetched',
            lazy: true,
        });

        cy.get('[data-cy=model-count]').should('have.text', '0');
        clickExportButton();
        cy.get('[data-cy=model-count]').should('have.text', '2');
        cy.then(() => {
            expect(fetchCount).to.equal(1);
        });
        expectDownload(downloads, 0, {
            content: fetchedRecordsCsv,
            filename: 'fetched.csv',
            type: 'text/csv;charset=utf-8',
        });

        clickExportButton();
        cy.then(() => {
            expect(fetchCount).to.equal(1);
        });
        expectDownload(downloads, 1, {
            content: fetchedRecordsCsv,
            filename: 'fetched.csv',
            type: 'text/csv;charset=utf-8',
        });
    });

    it('does not download when export data is empty', () => {
        const downloads = stubDownloads();
        mountDataExporter();

        clickExportButton();

        cy.then(() => {
            expect(downloads.anchors).to.have.length(0);
            expect(downloads.blobs).to.have.length(0);
            expect(downloads.objectUrls).to.have.length(0);
            expect(downloads.revokedObjectUrls).to.have.length(0);
        });
    });
});
