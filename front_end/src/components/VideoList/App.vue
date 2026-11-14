<template>
    <div class="video-list" data-cy="video-list">
        <BaseTable
            :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="colCount"
            table-class="video-list__table" data-cy="video-list-table"
        >
            <template #head>
                <tr>
                    <th
                        v-for="entry in columnConfigs" :key="entry.choice" scope="col"
                        :class="[entry.config.cellClass, { 'video-list__th--sorted': isSortedColumn(entry.config) }]"
                        :aria-sort="ariaSort(entry.config)" :aria-label="entry.config.headLabel ? undefined : t(`prop.${entry.choice}`)"
                    >
                        <span class="video-list__head">
                            <button v-if="showSort && entry.config.sortable" type="button" class="video-list__sort" :data-cy="`video-sort-${entry.choice}`" @click="toggleSort(entry.config.sortField)">
                                {{ t(`prop.${entry.choice}`) }}
                                <i class="pi video-list__sort-icon" :class="[sortIcon(entry.config), { 'video-list__sort-icon--inactive': !isSortedColumn(entry.config) }]" aria-hidden="true" />
                            </button>
                            <span v-else-if="entry.config.headLabel">
                                {{ t(`prop.${entry.choice}`) }}
                            </span>
                            <VideoListFilter
                                v-if="showFilters && entry.config.filterable" :choice="entry.choice" :filters="filters"
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
                v-for="video in pageRows" :key="video.rowKey" tabindex="0"
                @click="handleRowClick(video, $event)"
                @keydown.enter.prevent="handleRowKeydown(video, $event)"
                @keydown.space.prevent="handleRowKeydown(video, $event)"
            >
                <td v-for="entry in columnConfigs" :key="entry.choice" :class="entry.config.cellClass">
                    <VideoListCell :video="video" :choice="entry.choice" />
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

import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import VideoListCell from './VideoListCell.vue';
import type { VideoListColumnConfig, VideoListFilters } from './videoListData';
import { columnConfig, createVideoListFilters, filterVideos, sliceVideos, sortVideos } from './videoListData';
import VideoListFilter from './VideoListFilter.vue';

import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { preview } from '@/utils/common/PlayerDialog';
import type { ColumnChoice } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    videos: { type: Array<VideoAbstract>, default: () => [] },
    columns: { type: Array<ColumnChoice>, default: () => [] },
    paginator: { type: Boolean, default: false },
    paginatorRows: { type: Number, default: 25 },
    sortable: { type: Boolean, default: false },
    externalFiltering: { type: Boolean, default: false },
    displayOnly: { type: Boolean, default: false },
    includeLocal: { type: Boolean, default: undefined },
});
const first = defineModel<number>('first', { default: 0 });
const rows = defineModel<number>('rows');
const sortField = defineModel<string>('sortField', { default: 'upload_time' });
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
const columnConfigs = computed(() => props.columns.map((choice) => ({ choice, config: columnConfig(choice) })));
const colCount = computed(() => props.columns.length + (slots.rowActions ? 1 : 0));
const showFilters = computed(() => !props.displayOnly);
const showSort = computed(() => props.sortable && !props.displayOnly);
const hasLocalVideos = computed(() => props.includeLocal ?? props.videos.some((video) => video.isLocal));
const activeSortField = computed(() => (showSort.value && sortOrder.value !== undefined && sortOrder.value !== 0 ? sortField.value : ''));
const activeSortIcon = computed(() => (sortOrder.value !== undefined && sortOrder.value < 0 ? 'pi-sort-amount-down' : 'pi-sort-amount-down-alt'));

const processed = computed<VideoAbstract[]>(() => {
    if (props.displayOnly) return [...props.videos];
    const filtered = props.externalFiltering ? [...props.videos] : filterVideos(props.videos, filters.value);
    return sortVideos(filtered, sortField.value, sortOrder.value);
});
const total = computed(() => processed.value.length);
const pageRows = computed<VideoAbstract[]>(() => {
    if (props.displayOnly || !props.paginator) return processed.value;
    return sliceVideos(processed.value, first.value, effectiveRows.value);
});

function handleFilterChange(patch: Partial<VideoListFilters>) {
    filters.value = { ...filters.value, ...patch };
    first.value = 0;
}

function toggleSort(field: string) {
    if (sortField.value !== field) {
        sortField.value = field;
        sortOrder.value = 1;
    } else if (sortOrder.value === 1) {
        sortOrder.value = -1;
    } else if (sortOrder.value === -1) {
        sortOrder.value = 0;
    } else {
        sortOrder.value = 1;
    }
    first.value = 0;
}

function isSortedColumn(config: VideoListColumnConfig): boolean {
    return activeSortField.value !== '' && config.sortable && activeSortField.value === config.sortField;
}

function sortIcon(config: VideoListColumnConfig): string {
    return isSortedColumn(config) ? activeSortIcon.value : 'pi-sort-alt';
}

function ariaSort(config: VideoListColumnConfig): 'ascending' | 'descending' | 'none' | undefined {
    if (props.displayOnly || !config.sortable) return undefined;
    if (sortField.value !== config.sortField || sortOrder.value === undefined || sortOrder.value === 0) return 'none';
    return sortOrder.value < 0 ? 'descending' : 'ascending';
}

function handleRowClick(video: VideoAbstract, event: MouseEvent) {
    if (video.isLocal) return;
    const { target } = event;
    if (target instanceof HTMLElement && target.closest('button, a, input, select, label')) return;
    preview(video.id);
}

function handleRowKeydown(video: VideoAbstract, event: KeyboardEvent) {
    if (video.isLocal || event.target !== event.currentTarget) return;
    preview(video.id);
}

const i18nMessages = {
    'zh-cn': { local: {
        empty: '暂无录像',
        filterOff: '筛选已关闭',
    } },
    en: { local: {
        empty: 'No videos',
        filterOff: 'Filter disabled',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
