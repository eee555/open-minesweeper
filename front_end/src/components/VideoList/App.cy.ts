import { defineComponent, h, ref } from 'vue';

import VideoList from './App.vue';
import type { VideoListFilters } from './videoListData';
import { createVideoListFilters } from './videoListData';

import $axios from '@/http';
import i18n from '@/i18n';
import type { ColumnChoice } from '@/utils/ms_const';
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
    columns?: ColumnChoice[];
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
    const sortField = ref<string>('upload_time');
    const sortOrder = ref<number>(-1);
    const filters = ref<VideoListFilters>(createVideoListFilters());
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
            columns: options.columns ?? ['state', 'upload_time', 'time', 'bv'],
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
            'onUpdate:sortField': (value: string) => {
                sortField.value = value;
            },
            'onUpdate:sortOrder': (value: number | undefined) => {
                sortOrder.value = value ?? 0;
            },
        }, slots),
    }), { global: { plugins: [i18n], config: { globalProperties: { $axios } } } });
    return { first, rows, sortField, sortOrder, filters };
}

describe('<VideoList />', () => {
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
            expect(sortField.value).to.equal('upload_time');
            expect(sortOrder.value).to.equal(0);
        });
        cy.get('[data-cy=video-sort-upload_time]').click();
        cy.get(TABLE).contains('th', 'Upload Time').should('have.attr', 'aria-sort', 'ascending').and('have.class', 'video-list__th--sorted');
        cy.get('[data-cy=video-sort-upload_time] i').should('have.class', 'pi-sort-amount-down-alt').and('not.have.class', 'video-list__sort-icon--inactive');
        cy.then(() => {
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
        cy.get(TABLE).contains('td', '—').should('exist');
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
