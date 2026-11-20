<template>
    <div class="video-list" data-cy="video-list">
        <BaseTextButton v-if="showFilters && filtersActive" data-cy="video-clear-filters" @click="handleFilterChange(createVideoListFilters())">
            {{ t('local.clearFilters') }}
        </BaseTextButton>
        <BaseTable
            :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="colCount"
            table-class="video-list__table" data-cy="video-list-table"
        >
            <template #head>
                <tr>
                    <th
                        v-for="entry in columnConfigs" :key="entry.id" scope="col"
                        :class="[entry.config.cellClass, { 'video-list__th--sorted': isSortedColumn(entry.config) }]"
                        :aria-sort="showSort && entry.config.sortable ? sortState(sortOrder, sortField === entry.config.sortField) : undefined" :aria-label="entry.config.headLabel ? undefined : videoColumnLabel(entry.column)"
                    >
                        <span class="video-list__head">
                            <button v-if="showSort && entry.config.sortable" type="button" class="video-list__sort" :data-cy="`video-sort-${'expr' in entry.column ? entry.column.expr : entry.column.type}`" @click="toggleSort(entry.config.sortField)">
                                {{ videoColumnLabel(entry.column) }}
                                <SortIcon :state="sortState(sortOrder, sortField === entry.config.sortField)" class="video-list__sort-icon" :class="{ 'video-list__sort-icon--inactive': !isSortedColumn(entry.config) }" />
                            </button>
                            <span v-else-if="entry.config.headLabel">
                                {{ videoColumnLabel(entry.column) }}
                            </span>
                            <VideoListFilter
                                v-if="showFilters && entry.config.filterable" :column="entry.column" :filters="filters"
                                :include-local="hasLocalVideos" @change="handleFilterChange"
                            />
                            <i v-else-if="entry.config.filterable" class="pi pi-filter-slash video-list__filter-off" :title="t('local.filterOff')" aria-hidden="true" />
                        </span>
                    </th>
                    <th v-if="$slots.rowActions" scope="col" class="table-col-center">
                        {{ t('prop.action') }}
                    </th>
                </tr>
            </template>
            <tr
                v-for="video in pageRows" :key="video.rowKey" :tabindex="previewable ? 0 : undefined"
                @click="handleRowClick(video, $event)"
                @keydown.enter.prevent="handleRowKeydown(video, $event)"
                @keydown.space.prevent="handleRowKeydown(video, $event)"
            >
                <td v-for="entry in columnConfigs" :key="entry.id" :class="entry.config.cellClass">
                    <VideoListCell v-if="isFixedColumn(entry.column)" :video="video" :choice="entry.column.type" />
                    <ExpressionValue v-else :result="visibleValues.get(video)?.get(entry.id) ?? invalidValue" />
                </td>
                <td v-if="$slots.rowActions" class="table-col-center" @click.stop @keydown.stop>
                    <div v-if="!video.isLocal">
                        <Tippy interactive trigger="click" placement="bottom-end" :append-to="appendToBody">
                            <button type="button" class="base-button square-button" :aria-label="t('prop.action')" data-cy="video-row-actions" :data-video-id="video.id">
                                <i class="pi pi-ellipsis-h" aria-hidden="true" />
                            </button>
                            <template #content="{ hide }">
                                <div class="card card-small" @click.stop>
                                    <slot name="rowActions" :video="video" :close="hide" />
                                </div>
                            </template>
                        </Tippy>
                    </div>
                </td>
            </tr>
        </BaseTable>
        <BasePagination
            v-if="paginator && !displayOnly" v-model:current-start="currentStart" v-model:page-size="effectiveRows"
            :total="total" class="video-list__pagination" data-cy="video-list-pagination"
        />
    </div>
</template>

<script setup lang="ts">
import '@/styles/videoList.css';
import '@/styles/button.css';
import '@/styles/cards.css';
import 'primeicons/primeicons.css';

import { computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import { columnKey, defaultVideoSortField, evaluateVideoColumn, isFixedColumn, prepareVideoColumn, videoColumnLabel } from './columns';
import type { VideoColumn, VideoColumnResult } from './columns';
import ExpressionValue from './ExpressionValue.vue';
import VideoListCell from './VideoListCell.vue';
import type { VideoListColumnConfig, VideoListFilters } from './videoListData';
import { columnConfig, createVideoListFilters, filterVideos, isColumnFilterActive, sliceVideos, sortVideos } from './videoListData';
import VideoListFilter from './VideoListFilter.vue';

import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import { preview } from '@/utils/common/PlayerDialog';
import type { VideoAbstract } from '@/utils/videoabstract';
import { createVideoExpressionContext } from '@/utils/videoExpression';

const props = defineProps({
    videos: { type: Array<VideoAbstract>, default: () => [] },
    columns: { type: Array<VideoColumn>, default: () => [] },
    paginator: { type: Boolean, default: false },
    paginatorRows: { type: Number, default: 25 },
    sortable: { type: Boolean, default: false },
    externalFiltering: { type: Boolean, default: false },
    displayOnly: { type: Boolean, default: false },
    previewable: { type: Boolean, default: true },
    includeLocal: { type: Boolean, default: undefined },
});
const first = defineModel<number>('first', { default: 0 });
const rows = defineModel<number>('rows');
const sortField = defineModel<string>('sortField');
sortField.value ??= defaultVideoSortField(props.columns);
const sortOrder = defineModel<number | undefined>('sortOrder', { default: -1 });
const slots = defineSlots<{
    rowActions?: (props: { video: VideoAbstract; close: () => void }) => unknown;
}>();

const filters = defineModel<VideoListFilters>('filters', { default: () => createVideoListFilters() });
const appendToBody = () => document.body;
const effectiveRows = computed<number>({
    get: () => rows.value ?? props.paginatorRows,
    set: (value) => {
        rows.value = value;
    },
});
const currentStart = computed<number>({
    get: () => first.value + 1,
    set: (value) => {
        first.value = value - 1;
    },
});
const columnConfigs = computed(() => props.columns.map((column) => ({ ...prepareVideoColumn(column), config: columnConfig(column) })));
const colCount = computed(() => props.columns.length + (slots.rowActions ? 1 : 0));
const showFilters = computed(() => !props.displayOnly);
const showSort = computed(() => props.sortable && !props.displayOnly);
const hasLocalVideos = computed(() => props.includeLocal ?? props.videos.some((video) => video.isLocal));
const activeSortField = computed(() => (showSort.value && sortOrder.value !== undefined && sortOrder.value !== 0 ? sortField.value ?? '' : ''));
const filtersActive = computed(() => Object.keys(filters.value.bool).length > 0 || (['state', 'software', 'mode', 'level'] as const).some((field) => isColumnFilterActive(field, filters.value, hasLocalVideos.value)));
const sortColumn = computed(() => columnConfigs.value.find((entry) => entry.config.sortable && entry.id === sortField.value));
const activeColumn = computed(() => (activeSortField.value === '' ? undefined : sortColumn.value));
const filtered = computed(() => (props.displayOnly || props.externalFiltering ? [...props.videos] : filterVideos(props.videos, filters.value)));
const sortValues = computed(() => {
    const entry = activeColumn.value;
    return new Map(entry === undefined ? [] : filtered.value.map((video) => [video, evaluateVideoColumn(entry, createVideoExpressionContext(video))]));
});
const invalidValue: VideoColumnResult = { text: 'NaN', sortValue: NaN, error: '' };

const processed = computed<VideoAbstract[]>(() => {
    if (props.displayOnly || activeColumn.value === undefined) return filtered.value;
    return sortVideos(filtered.value, sortOrder.value, (video) => sortValues.value.get(video)?.sortValue);
});
const total = computed(() => processed.value.length);
const pageRows = computed<VideoAbstract[]>(() => {
    if (props.displayOnly || !props.paginator) return processed.value;
    return sliceVideos(processed.value, first.value, effectiveRows.value);
});
const visibleValues = computed(() => new Map(pageRows.value.map((video) => {
    const context = createVideoExpressionContext(video);
    return [video, new Map(columnConfigs.value.filter((entry) => !isFixedColumn(entry.column)).map((entry) => [entry.id, entry.id === activeSortField.value ? sortValues.value.get(video) ?? invalidValue : evaluateVideoColumn(entry, context)]))];
})));

watch(() => (sortColumn.value === undefined ? undefined : { id: sortColumn.value.id, expr: 'expr' in sortColumn.value.column ? sortColumn.value.column.expr : '' }), (next, previous) => {
    if (previous === undefined) return;
    if (next === undefined) {
        sortField.value = ''; sortOrder.value = 0; first.value = 0;
    } else if (next.id !== previous.id || next.expr !== previous.expr) first.value = 0;
});

watch(() => props.columns.filter((column) => column.type === 'bool'), (columns) => {
    const bool: VideoListFilters['bool'] = {};
    let changed = false;
    for (const [key, filter] of Object.entries(filters.value.bool)) {
        const column = columns.find((item) => columnKey(item) === key);
        if (column?.type !== 'bool') changed = true;
        else {
            bool[key] = { ...filter, expr: column.expr };
            changed ||= column.expr !== filter.expr;
        }
    }
    if (changed) handleFilterChange({ bool });
}, { immediate: true });

function handleFilterChange(patch: Partial<VideoListFilters>) {
    filters.value = { ...filters.value, ...patch };
    first.value = 0;
}

function toggleSort(field: string) {
    const active = sortField.value === field;
    sortField.value = field;
    sortOrder.value = nextSortOrder(sortOrder.value, active);
    first.value = 0;
}

function isSortedColumn(config: VideoListColumnConfig): boolean {
    return activeSortField.value !== '' && config.sortable && activeSortField.value === config.sortField;
}

function handleRowClick(video: VideoAbstract, event: MouseEvent) {
    if (!props.previewable || video.isLocal) return;
    const { target } = event;
    if (target instanceof HTMLElement && target.closest('button, a, input, select, label')) return;
    preview(video.id);
}

function handleRowKeydown(video: VideoAbstract, event: KeyboardEvent) {
    if (!props.previewable || video.isLocal || event.target !== event.currentTarget) return;
    preview(video.id);
}

const i18nMessages = {
    'zh-cn': { local: {
        empty: '暂无录像',
        filterOff: '筛选已关闭',
        clearFilters: '清空筛选',
    } },
    en: { local: {
        empty: 'No videos',
        filterOff: 'Filter disabled',
        clearFilters: 'Clear filters',
    } },
    es: { local: {
        empty: 'Sin repeticiones',
        filterOff: 'Filtro desactivado',
        clearFilters: 'Borrar filtros',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
