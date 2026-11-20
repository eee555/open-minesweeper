import { defineComponent, h, ref } from 'vue';

import VideoList from './App.vue';
import { columnKey } from './columns';
import type { VideoColumn } from './columns';
import { presetColumn } from './presets';
import type { VideoListFilters } from './videoListData';
import { createVideoListFilters } from './videoListData';

import $axios from '@/http';
import i18n from '@/i18n';
import { MS_Levels, MS_Mode } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';

const TABLE = '[data-cy=video-list-table] table';

function makeVideos(count: number): VideoAbstract[] {
    return Array.from({ length: count }, (_, index) => new VideoAbstract({
        id: index + 1,
        level: 'e',
        mode: MS_Mode.Standard,
        timems: 40000 + index * 1000,
        bv: 100 + index,
        software: index % 2 === 0 ? 'e' : 'a',
        state: 'a',
        upload_time: new Date(2026, 0, 1 + index),
    }));
}

interface MountOptions {
    videos?: VideoAbstract[];
    columns?: (string | VideoColumn)[];
    paginator?: boolean;
    sortable?: boolean;
    externalFiltering?: boolean;
    displayOnly?: boolean;
    first?: number;
    rowActions?: boolean;
}

function mountList(options: MountOptions = {}) {
    const first = ref<number>(options.first ?? 0);
    const rows = ref<number>(25);
    const sortField = ref<string>(columnKey(presetColumn('upload_time')));
    const sortOrder = ref<number>(-1);
    const filters = ref<VideoListFilters>(createVideoListFilters());
    const columns = ref((options.columns ?? ['state', 'upload_time', 'time', 'bv']).map((column) => (typeof column === 'string' ? presetColumn(column) : column)));
    const slots = options.rowActions === true
        ? {
            rowActions: ({ video, close }: { video: VideoAbstract; close: () => void }) => h('button', {
                'data-cy': 'row-action',
                onClick: close,
            }, String(video.id)),
        }
        : {};
    cy.mount(defineComponent({
        expose: [],
        render: () => h(VideoList, {
            videos: options.videos ?? makeVideos(30),
            columns: columns.value,
            paginator: options.paginator ?? true,
            sortable: options.sortable ?? true,
            externalFiltering: options.externalFiltering ?? false,
            displayOnly: options.displayOnly ?? false,
            filters: filters.value,
            'onUpdate:filters': (value: VideoListFilters) => {
                filters.value = value;
            },
            first: first.value,
            rows: rows.value,
            sortField: sortField.value,
            sortOrder: sortOrder.value,
            'onUpdate:first': (value: number) => {
                first.value = value;
            },
            'onUpdate:rows': (value: number | undefined) => {
                rows.value = value ?? 25;
            },
            'onUpdate:sortField': (value: string | undefined) => {
                sortField.value = value ?? '';
            },
            'onUpdate:sortOrder': (value: number | undefined) => {
                sortOrder.value = value ?? 0;
            },
        }, slots),
    }), { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    return { first, rows, sortField, sortOrder, filters, columns };
}

describe('<VideoList />', () => {
    it('renders configured names literally even when they match translated fields', () => {
        mountList({ columns: [{ id: 'literal', type: 'data', key: 'time', expr: 'bv' }] });
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows[0]).to.deep.equal(['time']);
        });
    });

    it('renders a native table with the default sort and a 25-row page', () => {
        mountList();
        cy.get(TABLE).contains('th', 'Upload Time').should('have.attr', 'aria-sort', 'descending');
        cy.get(`${TABLE} tbody tr`).should('have.length', 25);
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '1-25 / 30');
    });

    it('toggles sorting from a native header button and resets the page', () => {
        const { first, sortField, sortOrder } = mountList({ first: 25 });
        cy.get(TABLE).contains('th', 'Upload Time').should('have.class', 'video-list__th--sorted');
        cy.get('[data-cy=video-sort-upload_time] i').should('have.class', 'pi-sort-amount-down').and('not.have.class', 'video-list__sort-icon--inactive');
        cy.get('[data-cy=video-sort-bv] i').should('have.class', 'pi-sort-alt').and('have.class', 'video-list__sort-icon--inactive');
        cy.get('[data-cy=video-sort-upload_time]').click();
        cy.get(TABLE).contains('th', 'Upload Time').should('have.attr', 'aria-sort', 'none').and('not.have.class', 'video-list__th--sorted');
        cy.get('[data-cy=video-sort-upload_time] i').should('have.class', 'pi-sort-alt').and('have.class', 'video-list__sort-icon--inactive');
        cy.then(() => {
            expect(first.value).to.equal(0);
            expect(sortField.value).to.equal(columnKey(presetColumn('upload_time')));
            expect(sortOrder.value).to.equal(0);
        });
        cy.get('[data-cy=video-sort-upload_time]').click();
        cy.get(TABLE).contains('th', 'Upload Time').should('have.attr', 'aria-sort', 'ascending').and('have.class', 'video-list__th--sorted');
        cy.get('[data-cy=video-sort-upload_time] i').should('have.class', 'pi-sort-amount-down-alt').and('not.have.class', 'video-list__sort-icon--inactive');
        cy.then(() => {
            expect(sortField.value).to.equal(columnKey(presetColumn('upload_time')));
            expect(sortOrder.value).to.equal(1);
        });
    });

    it('keeps icon columns label-less and titles their filter buttons', () => {
        mountList({ columns: ['state', 'software', 'mode', 'level', 'upload_time'] });
        const head = `${TABLE} thead`;
        cy.get(head).should('not.contain.text', 'State').and('not.contain.text', 'Software');
        cy.get(head).should('not.contain.text', 'Mode').and('not.contain.text', 'Level').and('contain.text', 'Upload Time');
        cy.get(`${head} th`).first().should('have.attr', 'aria-label', 'State');
        cy.get('[data-cy=video-filter-state]').should('have.attr', 'title', 'Filter State');
        cy.get('[data-cy=video-filter-software]').should('have.attr', 'title', 'Filter Software');
        cy.get('[data-cy=video-filter-mode]').should('have.attr', 'title', 'Filter Mode');
        cy.get('[data-cy=video-filter-level]').should('have.attr', 'title', 'Filter Level');
    });

    it('keeps mode column cells on a single line', () => {
        mountList({ columns: ['mode'] });
        cy.get(`${TABLE} thead .table-col-mode`).should('have.css', 'white-space', 'nowrap');
        cy.get(`${TABLE} tbody .table-col-mode`).first().should('have.css', 'white-space', 'nowrap');
    });

    it('sorts custom data and date expressions by unformatted results', () => {
        const videos = makeVideos(3);
        mountList({ videos,
            columns: [
                { id: 'id', type: 'data', key: 'ID', expr: 'id' },
                { id: 'inverse', type: 'data.0f', key: 'Inverse BV', expr: '-bv / 100' },
                { id: 'shifted', type: 'date', key: 'Shifted date', expr: 'upload_time + 86400000' },
            ] });
        cy.contains(`${TABLE} th button`, 'Inverse BV').click();
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[0])).to.deep.equal(['3', '2', '1']);
            expect(rows.slice(1).map((row) => row[1])).to.deep.equal(['-1', '-1', '-1']);
        });
        cy.contains(`${TABLE} th`, 'Inverse BV').should('have.attr', 'aria-sort', 'ascending');
        cy.contains(`${TABLE} th button`, 'Shifted date').click();
        cy.contains(`${TABLE} th`, 'Shifted date').should('have.attr', 'aria-sort', 'ascending');
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[0])).to.deep.equal(['1', '2', '3']);
        });
    });

    it('filters bool expressions before paging, forwards shared state and clears active filters', () => {
        const { first, filters } = mountList({ first: 25,
            columns: [
                { id: 'bv', type: 'data', key: 'Bv', expr: 'bv' },
                { id: 'Large', type: 'bool', key: 'Large', expr: 'bv >= 120' },
            ] });
        cy.get('[data-cy="video-sort-bv"]').should('exist');
        cy.get(`${TABLE} th[aria-label=Large]`).should('have.class', 'video-list__col-icon').find('.video-list__sort').should('not.exist');
        cy.get('[data-cy="video-filter-bool:Large"]').should('have.attr', 'title', 'Filter Large').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-bool-options] input[value=true]').check();
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[0])).to.deep.equal(Array.from({ length: 10 }, (_, index) => String(120 + index)));
        });
        cy.then(() => {
            expect(first.value).to.equal(0);
            expect(filters.value.bool).to.deep.equal({ 'bool:Large': { expr: 'bv >= 120', value: true } });
        });
        cy.get('[data-tippy-root] [data-cy=video-filter-bool-options] input[value=false]').check();
        cy.get(`${TABLE} tbody tr`).should('have.length', 20);
        cy.get('[data-cy="video-filter-bool:Large"]').click();
        cy.get('[data-cy=video-clear-filters]').click();
        cy.get(`${TABLE} tbody tr`).should('have.length', 25);
        cy.get('[data-cy=video-clear-filters]').should('not.exist');
    });

    it('preserves active sorting, boolean filtering and pagination when columns are renamed or inserted', () => {
        const { first, sortField, sortOrder, filters, columns } = mountList({ videos: makeVideos(60),
            columns: [
                { id: 'metric', type: 'data', key: 'Bv', expr: 'bv' },
                { id: 'large', type: 'bool', key: 'Large', expr: 'bv >= 120' },
            ] });
        cy.get('[data-cy="video-filter-bool:large"]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-bool-options] input[value=true]').check();
        cy.get('[data-cy="video-filter-bool:large"]').click();
        cy.contains(`${TABLE} th button`, 'Bv').click();
        cy.then(() => {
            first.value = 5;
        });
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '6-30 / 40');
        cy.then(() => {
            columns.value = [
                { id: 'another', type: 'data', key: 'Same expression', expr: 'bv' },
                { id: 'metric', type: 'data.1f', key: 'Renamed BV', expr: 'bv' },
                { id: 'large', type: 'bool', key: 'Renamed Large', expr: 'bv >= 120' },
            ];
        });
        cy.contains(`${TABLE} th`, 'Renamed BV').should('have.attr', 'aria-sort', 'ascending');
        cy.contains(`${TABLE} th`, 'Same expression').should('have.attr', 'aria-sort', 'none');
        cy.get('[data-cy="video-filter-bool:large"]').should('have.attr', 'title', 'Filter Renamed Large').find('i').should('have.class', 'pi-filter-fill');
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows.slice(1).map((row) => row[0])).to.deep.equal(Array.from({ length: 25 }, (_, index) => String(125 + index)));
        });
        cy.then(() => {
            expect(first.value).to.equal(5);
            expect(sortField.value).to.equal('data:metric');
            expect(sortOrder.value).to.equal(1);
            expect(filters.value.bool).to.deep.equal({ 'bool:large': { expr: 'bv >= 120', value: true } });
            columns.value = [{ id: 'metric', type: 'data.1f', key: 'Renamed BV', expr: '-bv' }];
        });
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '1-25 / 60');
        cy.get(TABLE).extractTableData().should((rows) => {
            expect(rows[1]).to.deep.equal(['-159.0']);
        });
        cy.then(() => {
            expect(filters.value.bool).to.deep.equal({});
            columns.value = [];
        });
        cy.then(() => {
            expect(sortField.value).to.equal('');
            expect(sortOrder.value).to.equal(0);
        });
    });

    it('filters from a header popover, resets the page and restores the defaults', () => {
        const { first } = mountList({ first: 25 });
        cy.get('[data-cy=video-filter-state] i').should('have.class', 'pi-filter');
        cy.get('[data-cy=video-filter-state]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-menu] input[value=a]').should('be.checked').uncheck();
        cy.get('[data-cy=video-filter-state] i').should('have.class', 'pi-filter-fill');
        cy.get(`${TABLE} .base-table-empty`).should('exist');
        cy.then(() => {
            expect(first.value).to.equal(0);
        });
        cy.get('[data-tippy-root] [data-cy=video-filter-menu] input[value=a]').check();
        cy.get('[data-cy=video-filter-state] i').should('have.class', 'pi-filter');
        cy.get(`${TABLE} tbody tr`).should('have.length', 25);
    });

    it('offers level choices as a radio button group without a reset control', () => {
        mountList({ columns: ['state', 'software', 'mode', 'level', 'upload_time'] });
        cy.get('[data-cy=video-filter-level]').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-level-options] input[type=radio]').should('have.length', MS_Levels.length + 2);
        cy.get('[data-tippy-root] [data-cy=video-filter-level-options] input[value=e]').check();
        cy.get('[data-cy=video-filter-level] i').should('have.class', 'pi-filter-fill');
        cy.get('[data-tippy-root] [data-cy=video-filter-reset]').should('not.exist');
    });

    it('keeps header filters visible and forwards changes under external filtering', () => {
        const { filters } = mountList({ externalFiltering: true });
        cy.get('[data-cy=video-filter-state]').should('exist').click();
        cy.get('[data-tippy-root] [data-cy=video-filter-menu] input[value=a]').should('be.checked').uncheck();
        cy.then(() => {
            expect(filters.value.state).to.not.include('a');
        });
        cy.get(`${TABLE} tbody tr`).should('have.length', 25);
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '1-25 / 30');
    });

    it('paginates by start index and clamps an out-of-range external model', () => {
        const { first } = mountList();
        cy.get('[data-cy=video-list-pagination] [data-cy=jump]').clear();
        cy.get('[data-cy=video-list-pagination] [data-cy=jump]').type('13{enter}');
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '13-30 / 30');
        cy.then(() => {
            expect(first.value).to.equal(12);
            first.value = 50;
        });
        cy.get('[data-cy=video-list-pagination] [data-cy=report]').should('have.text', '30-30 / 30');
        cy.get(`${TABLE} tbody tr`).should('have.length', 1);
        cy.then(() => {
            expect(first.value).to.equal(29);
        });
    });

    it('keeps row actions off local CSV rows', () => {
        const videos = [
            ...makeVideos(2),
            VideoAbstract.fromArbiterCsv({ level: 'e', mode: MS_Mode.Standard, timems: 35000, bv: 90, software: 'a', end_time: new Date(2026, 1, 1) }),
        ];
        mountList({ videos, rowActions: true });
        cy.get('[data-cy=video-row-actions]').should('have.length', 2);
        cy.get(`${TABLE} tbody tr`).should('have.length', 3);
        cy.get(TABLE).contains('td', '35.000').should('exist');
    });

    it('displays pageRows as-is without sorting, filtering or a second paginator', () => {
        const videos = makeVideos(3);
        mountList({ videos, displayOnly: true, first: 1 });
        cy.get('[data-cy=video-filter-state]').should('not.exist');
        cy.get(`${TABLE} thead .pi-filter-slash`).should('exist').and('have.attr', 'title', 'Filter disabled');
        cy.get('[data-cy=video-sort-upload_time]').should('not.exist');
        cy.get('[data-cy=video-list-pagination]').should('not.exist');
        cy.get(`${TABLE} tbody tr`).first().should('contain.text', '40.000');
    });
});
