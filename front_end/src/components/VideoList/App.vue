<template>
    <DataTable
        v-model:first="first" v-model:rows="effectiveRows" v-model:sort-field="sortField" v-model:sort-order="sortOrder" :filters="externalFiltering ? emptyFilters : filters" :value="videos"
        :filter-display="externalFiltering ? undefined : 'menu'" row-hover data-key="rowKey"
        style="min-width: 50em"
        size="small" :filter-button-props="{
            filter: {
                severity: 'secondary',
                text: true,
                rounded: false,
                size: 'small',
                style: { borderRadius: '0', padding: '0', width: '1rem' }
            }
        }"
        :paginator="paginator"
        paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown JumpToPageInput CurrentPageReport"
        :rows-per-page-options="[5, 10, 25, 50, 100]"
        @row-click="handleRowClick"
        @update:filters="filters = $event"
    >
        <component
            :is="componentConfig(column).component" v-for="column in columns" :key="column"
            :column-key="column"
            :sortable="componentConfig(column).sortable ? sortable : undefined"
            :stat="componentConfig(column).isStat ? column : undefined"
            :show-filter-menu="!externalFiltering"
        />
        <Column v-if="$slots.rowActions" column-key="rowActions" :header="t('prop.action')" style="width: 5rem">
            <template #body="{ data }: { data: VideoAbstract }">
                <div v-if="!data.isLocal" @click.stop>
                    <Tippy interactive trigger="click" placement="bottom-end" :append-to="appendToBody">
                        <button type="button" class="base-button square-button" :aria-label="t('prop.action')" data-cy="video-row-actions" :data-video-id="data.id">
                            <i class="pi pi-ellipsis-h" aria-hidden="true" />
                        </button>
                        <template #content="{ hide }">
                            <div class="card card-small" @click.stop>
                                <slot name="rowActions" :video="data" :close="hide" />
                            </div>
                        </template>
                    </Tippy>
                </div>
            </template>
        </Column>
    </DataTable>
</template>

<script setup lang="ts">
import '@/styles/button.css';
import '@/styles/cards.css';

import { FilterMatchMode } from '@primevue/core/api';
import { Column, DataTable } from 'primevue';
import type { DataTableFilterMeta } from 'primevue/datatable';
import 'primeicons/primeicons.css';
import { computed, defineAsyncComponent, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import { preview } from '@/utils/common/PlayerDialog';
import type { ColumnChoice } from '@/utils/ms_const';
import { MS_Mode, MS_Softwares, MS_State } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    videos: { type: Array<VideoAbstract>, default: () => [] },
    columns: { type: Array<ColumnChoice>, default: () => [] },
    paginator: { type: Boolean, default: false },
    paginatorRows: { type: Number, default: 25 },
    sortable: { type: Boolean, default: false },
    externalFiltering: { type: Boolean, default: false },
});
const first = defineModel<number>('first', { default: 0 });
const rows = defineModel<number>('rows');
const sortField = defineModel<string>('sortField', { default: 'upload_time' });
const sortOrder = defineModel<number | undefined>('sortOrder', { default: -1 });
const effectiveRows = computed({ get: () => rows.value ?? props.paginatorRows,
    set: (value: number) => {
        rows.value = value;
    } });
defineSlots<{
    rowActions?: (props: { video: VideoAbstract; close: () => void }) => unknown;
}>();
const { t } = useI18n();
const appendToBody = () => document.body;
const emptyFilters: DataTableFilterMeta = {};

const ColumnEndTime = defineAsyncComponent(() => import('./ColumnEndTime.vue'));
const ColumnFileSize = defineAsyncComponent(() => import('./ColumnFileSize.vue'));
const ColumnLevel = defineAsyncComponent(() => import('./ColumnLevel.vue'));
const ColumnMode = defineAsyncComponent(() => import('./ColumnMode.vue'));
const ColumnPlayerName = defineAsyncComponent(() => import('./ColumnPlayerName.vue'));
const ColumnStat = defineAsyncComponent(() => import('./ColumnStat.vue'));
const ColumnState = defineAsyncComponent(() => import('./ColumnState.vue'));
const ColumnSoftware = defineAsyncComponent(() => import('./ColumnSoftware.vue'));
const ColumnUploadTime = defineAsyncComponent(() => import('./ColumnUploadTime.vue'));

function handleRowClick(event: { data: VideoAbstract }) {
    if (event.data.isLocal) return;
    void preview(event.data.id, event.data.software);
}

function componentConfig(choice: ColumnChoice) {
    switch (choice) {
        case 'level': return { component: ColumnLevel, sortable: false, isStat: false };
        case 'mode': return { component: ColumnMode, sortable: false, isStat: false };
        case 'player': return { component: ColumnPlayerName, sortable: false, isStat: false };
        case 'software': return { component: ColumnSoftware, sortable: false, isStat: false };
        case 'state': return { component: ColumnState, sortable: false, isStat: false };
        case 'upload_time': return { component: ColumnUploadTime, sortable: true, isStat: false };
        case 'end_time': return { component: ColumnEndTime, sortable: true, isStat: false };
        case 'file_size': return { component: ColumnFileSize, sortable: true, isStat: false };
        default: return { component: ColumnStat, sortable: true, isStat: true };
    }
}

const filters = ref<DataTableFilterMeta>({
    state: { value: Object.values(MS_State), matchMode: FilterMatchMode.IN },
    software: { value: [...MS_Softwares], matchMode: FilterMatchMode.IN },
    level: { value: null, matchMode: FilterMatchMode.EQUALS },
    mode: { value: Object.values(MS_Mode), matchMode: FilterMatchMode.IN },
});
</script>
