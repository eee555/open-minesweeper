<template>
    <div v-if="data.length > 0" class="upload-table">
        <BaseTable :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="12" data-cy="upload-table">
            <template #columns>
                <col class="upload-col-action"><col class="upload-col-action"><col class="upload-col-software">
            </template>
            <template #head>
                <tr>
                    <th scope="col" class="table-col-center upload-col-action" />
                    <th scope="col" class="table-col-center upload-col-action">
                        <label class="checkbox">
                            <input class="checkbox-input" type="checkbox" :checked="!selectedNone && selectedAll" :indeterminate.prop="!selectedAll && !selectedNone" :aria-label="t('local.selectAll')" data-cy="select-all" @change="handleSelectAllChange">
                        </label>
                    </th>
                    <th scope="col" class="table-col-center upload-col-software" />
                    <th v-for="column in columns" :key="column.key" scope="col" :class="column.cellClass" :aria-sort="column.sortField === null ? undefined : sortState(sortOrder, sortField === column.sortField)">
                        <span class="upload-head">
                            <button v-if="column.sortField !== null" type="button" class="upload-head__sort" :data-cy="`sort-${column.key}`" @click="toggleColumnSort(column.sortField)">
                                <span>{{ column.label }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === column.sortField)" class="upload-head__sort-icon" :class="{ 'upload-head__sort-icon--inactive': !isSortedColumn(column) }" />
                            </button>
                            <span v-else>{{ column.label }}</span>
                            <Tippy v-if="column.filterField !== null" interactive trigger="click" placement="bottom-start" :append-to="appendToBody">
                                <button type="button" class="upload-head__filter" :aria-label="column.filterLabel" :title="column.filterLabel" :data-cy="`filter-${column.key}-trigger`">
                                    <i class="pi" :class="filterIsClear(column.filterField) ? 'pi-filter' : 'pi-filter-fill'" aria-hidden="true" />
                                </button>
                                <template #content="{ hide }">
                                    <div class="card card-small upload-filter-menu" @click.stop @keydown.esc="hide()">
                                        <BaseListbox :model-value="filterValue(column.filterField)" :options="column.options" :aria-label="column.filterLabel" :data-cy="`filter-${column.key}`" @update:model-value="applyFilter(column.filterField, $event); hide()" />
                                        <BaseButton size="small" text :data-cy="`filter-${column.key}-clear`" @click="resetFilter(column.filterField); hide()">
                                            {{ t('local.clearFilter') }}
                                        </BaseButton>
                                    </div>
                                </template>
                            </Tippy>
                        </span>
                    </th>
                </tr>
            </template>
            <template v-for="row in pageRows" :key="row.hash">
                <tr>
                    <td class="table-col-center upload-col-action">
                        <BaseButton class="upload-icon-button" size="small" text :aria-label="t('local.expandRow')" :aria-expanded="expandedRows.includes(row.hash)" data-cy="expand-row" @click="toggleExpanded(row.hash)">
                            <i class="pi" :class="expandedRows.includes(row.hash) ? 'pi-chevron-down' : 'pi-chevron-right'" aria-hidden="true" />
                        </BaseButton>
                    </td>
                    <td class="table-col-center upload-col-action">
                        <label class="checkbox">
                            <input class="checkbox-input" type="checkbox" :checked="selectedRows.includes(row)" :aria-label="t('local.selectVideo', { filename: row.file.name })" @change="(event) => handleSelectOneChange(event, row)">
                        </label>
                    </td>
                    <td class="table-col-center upload-col-software">
                        <SoftwareIcon v-if="row.stat" :software="row.stat.software" />
                    </td>
                    <td>{{ t(`local.${row.status}`) }}</td>
                    <td class="table-col-datetime">
                        {{ formatEndTime(row.stat) }}
                    </td>
                    <td class="table-col-mode">
                        {{ row.stat ? formatLevel(row.stat.level) : '' }}
                    </td>
                    <td class="table-col-mode">
                        {{ row.stat ? t(`mode.code${row.stat.mode}`) : '' }}
                    </td>
                    <td class="table-col-number">
                        {{ row.stat ? row.stat.displayStat('time') : '' }}
                    </td>
                    <td class="table-col-bv">
                        {{ row.stat ? row.stat.bv : '' }}
                    </td>
                    <td class="table-col-number">
                        {{ row.stat ? row.stat.displayStat('bvs') : '' }}
                    </td>
                    <td class="table-col-number">
                        {{ formatStat(row.stat, 'pluck') }}
                    </td>
                    <td class="table-col-number">
                        {{ formatStat(row.stat, 'thrp') }}
                    </td>
                </tr>
                <tr v-if="expandedRows.includes(row.hash)" class="upload-expansion" data-cy="upload-expansion">
                    <td :colspan="12">
                        <div class="description-layout">
                            <dl class="descriptions">
                                <div class="description-item description-wide">
                                    <dt>{{ t('prop.fileName') }}</dt>
                                    <dd>
                                        {{ row.file.name }}
                                    </dd>
                                </div>
                                <template v-if="row.stat">
                                    <div class="description-item">
                                        <dt>{{ t('prop.cl') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('cl') }}
                                        </dd>
                                    </div>
                                    <div class="description-item description-span-2">
                                        <dt>{{ t('prop.ce') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('ce') }}
                                        </dd>
                                    </div>
                                    <div class="description-item">
                                        <dt>{{ t('prop.cl_s') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('cls') }}
                                        </dd>
                                    </div>
                                    <div class="description-item description-span-2">
                                        <dt>{{ t('prop.ce_s') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('ces') }}
                                        </dd>
                                    </div>
                                    <div class="description-item">
                                        <dt>{{ t('prop.ioe') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('ioe') }}
                                        </dd>
                                    </div>
                                    <div class="description-item">
                                        <dt>{{ t('prop.thrp') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('thrp') }}
                                        </dd>
                                    </div>
                                    <div class="description-item">
                                        <dt>{{ t('prop.corr') }}</dt>
                                        <dd>
                                            {{ row.stat.displayStat('corr') }}
                                        </dd>
                                    </div>
                                </template>
                            </dl>
                        </div>
                    </td>
                </tr>
            </template>
        </BaseTable>
        <BasePagination
            v-model:current-start="currentStart" v-model:page-size="pageSize"
            :total="total" :page-size-options="[5, 10, 25, 50, 100]" data-cy="upload-pagination"
        />
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/descriptions.css';
import type { PropType } from 'vue';
import { computed, nextTick, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import type { UploadFilterField, UploadFilters, UploadSortField } from './uploadTableData';
import { createUploadFilters, filterUploadTable, sliceUploadTable, sortUploadTable } from './uploadTableData';
import type { UploadEntry } from './utils';
import { UploadStatus } from './utils';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseListbox from '@/components/common/BaseListbox.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import { CustomLevel } from '@/utils/customlevel';
import { toISODateTimeString } from '@/utils/datetime';
import { MS_Levels, MS_Mode } from '@/utils/ms_const';

interface UploadFilterOption {
    value: string;
    label: string;
}

interface UploadColumn {
    key: string;
    label: string;
    cellClass: string;
    sortField: UploadSortField | null;
    filterField: UploadFilterField | null;
    filterLabel: string;
    options: UploadFilterOption[];
}

const props = defineProps({
    data: {
        type: Array as PropType<UploadEntry[]>,
        default: () => [],
    },
});

const selectedRows = defineModel<UploadEntry[]>(
    'selected-rows',
    { default: () => [] },
);

const appendToBody = () => document.body;
const filters = reactive<UploadFilters>(createUploadFilters());
const currentStart = ref(1);
const pageSize = ref(25);
const sortField = ref<UploadSortField | null>(null);
const sortOrder = ref<number | undefined>(undefined);
const expandedRows = ref<string[]>([]);

const filteredData = computed(() => filterUploadTable(props.data, filters));
const processed = computed(() => sortUploadTable(filteredData.value, sortField.value, sortOrder.value));
const total = computed(() => processed.value.length);
const first = computed(() => Math.max(0, Math.min(currentStart.value, total.value) - 1));
const pageRows = computed(() => sliceUploadTable(processed.value, first.value, pageSize.value));

const selectedAll = computed(() => selectedRows.value.length === filteredData.value.length);
const selectedNone = computed(() => selectedRows.value.length === 0);

watch(filters, () => {
    currentStart.value = 1;
});

watch(filteredData, (newVal) => {
    selectedRows.value = selectedRows.value.filter((entry) => newVal.includes(entry));
});

function clearFilter(field: UploadFilterField) {
    filters[field] = null;
}

function filterIsClear(field: UploadFilterField | null): boolean {
    return field === null || filters[field] === null;
}

function filterValue(field: UploadFilterField | null): string | null {
    return field === null ? null : filters[field];
}

function applyFilter(field: UploadFilterField | null, value: string | null) {
    if (field !== null) filters[field] = value;
}

function resetFilter(field: UploadFilterField | null) {
    if (field !== null) clearFilter(field);
}

function toggleColumnSort(field: UploadSortField | null) {
    if (field !== null) toggleSort(field);
}

function isSortedColumn(column: UploadColumn): boolean {
    return sortState(sortOrder.value, column.sortField !== null && sortField.value === column.sortField) !== 'none';
}

function formatEndTime(stat: UploadEntry['stat']): string {
    const end = stat?.end_time;
    return end === undefined ? '' : toISODateTimeString(end);
}

function formatStat(stat: UploadEntry['stat'], field: 'pluck' | 'thrp'): string {
    if (stat === undefined) return '';
    return Number.isFinite(stat[field]) ? stat.displayStat(field) : '—';
}

function toggleSort(field: UploadSortField) {
    const active = sortField.value === field;
    sortField.value = field;
    sortOrder.value = nextSortOrder(sortOrder.value, active, -1);
    currentStart.value = 1;
}

function toggleExpanded(hash: string) {
    const index = expandedRows.value.indexOf(hash);
    if (index === -1) expandedRows.value.push(hash);
    else expandedRows.value.splice(index, 1);
}

async function handleSelectAllChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    if (!selectedNone.value) {
        selectedRows.value.length = 0;
    } else {
        selectedRows.value = [...filteredData.value];
    }
    // Activation changes the DOM even when the derived checked value stays false.
    await nextTick();
    input.checked = !selectedNone.value && selectedAll.value;
    input.indeterminate = !selectedAll.value && !selectedNone.value;
}

function handleSelectOneChange(event: Event, entry: UploadEntry) {
    if ((event.currentTarget as HTMLInputElement).checked) {
        selectedRows.value.push(entry);
    } else {
        const index = selectedRows.value.indexOf(entry);
        selectedRows.value.splice(index, 1);
    }
}

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        censorship: '标识未通过',
        collision: '录像已存在',
        custom: '暂不支持此自定义配置',
        fail: '不通过',
        fileext: '无法识别的文件类型',
        filename: '文件名超过了100字节',
        filesize: '文件大小超过了5MB',
        identifier: '新标识',
        incomplete: '游戏未完成',
        mode: '暂不支持此模式',
        needApprove: '需要人工审核',
        parse: '录像解析失败',
        pass: '通过',
        process: '上传中',
        identity: '需要先完成实名或玩家认证',
        quota: '录像额度已满',
        selectAll: '全选录像',
        selectVideo: '选择录像：{filename}',
        success: '上传成功',
        upload: '上传失败',
        filterStatus: '筛选状态',
        filterLevel: '筛选等级',
        filterMode: '筛选模式',
        clearFilter: '清除筛选',
        expandRow: '展开录像详情',
        empty: '没有匹配的录像',
    } },
    en: { local: {
        censorship: 'Identifier blocked',
        collision: 'Video already exists',
        custom: 'This custom board is currently not supported',
        fail: 'Fail',
        fileext: 'Invalid file extension',
        filename: 'File name exceeds 100 bytes',
        filesize: 'File size exceeds 5MB',
        identifier: 'New identifier',
        incomplete: 'Game not finished',
        mode: 'Unsupported game mode',
        needApprove: 'Need manual approval',
        parse: 'Cannot parse the file',
        pass: 'Pass',
        process: 'Uploading',
        identity: 'Real name or player verification required',
        quota: 'Video quota reached',
        selectAll: 'Select all videos',
        selectVideo: 'Select video: {filename}',
        success: 'Success',
        upload: 'Upload fail',
        filterStatus: 'Filter status',
        filterLevel: 'Filter level',
        filterMode: 'Filter mode',
        clearFilter: 'Clear',
        expandRow: 'Expand video details',
        empty: 'No matching videos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

function formatLevel(level: string | CustomLevel): string {
    if (level instanceof CustomLevel) {
        return t('level.c', {
            column: level.column,
            mine: level.mine,
            row: level.row,
        });
    }
    return t(`level.${level}`);
}

const columns = computed<UploadColumn[]>(() => [
    { key: 'status', label: t('prop.status'), cellClass: '', sortField: null, filterField: 'status', filterLabel: t('local.filterStatus'), options: UploadStatus.map((status) => ({ value: status, label: t(`local.${status}`) })) },
    { key: 'end-time', label: t('prop.end_time'), cellClass: 'table-col-datetime', sortField: 'stat.end_time', filterField: null, filterLabel: '', options: [] },
    { key: 'level', label: t('prop.level'), cellClass: 'table-col-mode', sortField: null, filterField: 'stat.level', filterLabel: t('local.filterLevel'), options: MS_Levels.map((level) => ({ value: level, label: formatLevel(level) })) },
    { key: 'mode', label: t('prop.mode'), cellClass: 'table-col-mode', sortField: null, filterField: 'stat.mode', filterLabel: t('local.filterMode'), options: Object.values(MS_Mode).map((mode) => ({ value: mode, label: t(`mode.code${mode}`) })) },
    { key: 'time', label: t('prop.time'), cellClass: 'table-col-number', sortField: 'stat.timems', filterField: null, filterLabel: '', options: [] },
    { key: 'bv', label: t('prop.bv'), cellClass: 'table-col-bv', sortField: 'stat.bv', filterField: null, filterLabel: '', options: [] },
    { key: 'bvs', label: t('prop.bvs'), cellClass: 'table-col-number', sortField: 'stat.bvs', filterField: null, filterLabel: '', options: [] },
    { key: 'pluck', label: t('prop.pluck'), cellClass: 'table-col-number', sortField: null, filterField: null, filterLabel: '', options: [] },
    { key: 'thrp', label: t('prop.thrp'), cellClass: 'table-col-number', sortField: null, filterField: null, filterLabel: '', options: [] },
]);
</script>

<style scoped>
.upload-table .upload-icon-button {
    color: inherit;
    font: inherit;
}

.upload-head {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.upload-head__sort,
.upload-head__filter {
    margin: 0;
    border: 0;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
}

.upload-head__sort {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.upload-head__sort .upload-head__sort-icon {
    font-size: 0.75em;
}

.upload-head__sort .upload-head__sort-icon--inactive {
    opacity: 0.45;
}

.upload-head__sort:focus-visible,
.upload-head__filter:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

.upload-head__filter {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    font-size: 0.75em;
}

.upload-head__filter:hover {
    color: var(--ui-color-primary);
}

:is(.upload-col-action, .upload-col-software) {
    width: 2.5em;
    min-width: 2.5em;
    max-width: 2.5em;
    padding-inline: 0;
    white-space: nowrap;
}

.upload-filter-menu {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: fit-content;
    max-width: calc(100vw - 2rem);
    padding: 6px;
}

.upload-expansion > td {
    padding: 0.5em;
    background: var(--ui-table-header-background);
    white-space: normal;
}
</style>
